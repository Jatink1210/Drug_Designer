"""Sync Knowledge Graph from Qdrant entity data.

Reads entities from Qdrant collections, infers relationships from shared
metadata (e.g. gene-protein, drug-target, disease-drug), and pushes them
into the GraphStore (NetworkX/SQLite in workbench mode, Neo4j in full mode).
"""

import asyncio
import logging
import sys
from typing import Any, Dict, List, Set, Tuple

from qdrant_client import AsyncQdrantClient
from config import settings
from services.graph_store import get_graph_store

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

# Qdrant collections to scan
COLLECTIONS = [
    "proteins", "genes", "diseases", "drugs",
    "variants", "pathways", "publications", "clinical_trials",
]

# Map collection name -> graph node label
COLLECTION_LABEL = {
    "proteins": "Protein",
    "genes": "Gene",
    "diseases": "Disease",
    "drugs": "Drug",
    "variants": "Variant",
    "pathways": "Pathway",
    "publications": "Publication",
    "clinical_trials": "Trial",
}


async def _scroll_all(client: AsyncQdrantClient, collection: str) -> List[Dict[str, Any]]:
    """Scroll all points from a Qdrant collection."""
    entities: List[Dict[str, Any]] = []
    offset = None
    while True:
        results, next_offset = await client.scroll(
            collection_name=collection,
            limit=100,
            offset=offset,
            with_payload=True,
        )
        for point in results:
            payload = point.payload or {}
            payload["_point_id"] = str(point.id)
            payload["_collection"] = collection
            entities.append(payload)
        if next_offset is None:
            break
        offset = next_offset
    return entities


def _infer_edges(
    entities_by_collection: Dict[str, List[Dict[str, Any]]]
) -> List[Tuple[str, str, str, str, str, Dict[str, Any]]]:
    """Infer edges between entities based on shared identifiers in payloads.

    Returns list of (src_label, src_id, rel_type, dst_label, dst_id, props).
    """
    edges: List[Tuple[str, str, str, str, str, Dict[str, Any]]] = []
    seen: Set[Tuple[str, str, str]] = set()

    def _add(src_label, src_id, rel, dst_label, dst_id, props=None):
        key = (src_id, rel, dst_id)
        if key not in seen:
            seen.add(key)
            edges.append((src_label, src_id, rel, dst_label, dst_id, props or {}))

    # Build lookup indices
    gene_by_id: Dict[str, Dict] = {}
    for g in entities_by_collection.get("genes", []):
        gid = g.get("id", "")
        if gid:
            gene_by_id[gid] = g

    protein_by_id: Dict[str, Dict] = {}
    for p in entities_by_collection.get("proteins", []):
        pid = p.get("id", "")
        if pid:
            protein_by_id[pid] = p

    disease_by_id: Dict[str, Dict] = {}
    for d in entities_by_collection.get("diseases", []):
        did = d.get("id", "")
        if did:
            disease_by_id[did] = d

    drug_by_id: Dict[str, Dict] = {}
    for dr in entities_by_collection.get("drugs", []):
        drid = dr.get("id", "")
        if drid:
            drug_by_id[drid] = dr

    # Gene -> Protein (CODES_FOR) via gene_name / protein.gene
    for pid, prot in protein_by_id.items():
        gene_refs = []
        gene_name = prot.get("gene_name") or prot.get("gene")
        if gene_name:
            gene_refs.append(gene_name)
        gene_id_ref = prot.get("gene_id") or prot.get("ensembl_gene_id")
        if gene_id_ref and gene_id_ref in gene_by_id:
            _add("Gene", gene_id_ref, "CODES_FOR", "Protein", pid, {"source": "metadata"})
        elif gene_name:
            # Try matching by name
            for gid, gene in gene_by_id.items():
                if gene.get("name", "").lower() == gene_name.lower():
                    _add("Gene", gid, "CODES_FOR", "Protein", pid, {"source": "name_match"})
                    break

    # Drug -> Protein (TARGETS) via target_id / target references
    for drid, drug in drug_by_id.items():
        targets = drug.get("targets") or drug.get("target_ids") or []
        if isinstance(targets, str):
            targets = [targets]
        for tid in targets:
            if tid in protein_by_id:
                action = drug.get("action_type", "unknown")
                _add("Drug", drid, "TARGETS", "Protein", tid,
                     {"action": action, "source": "metadata"})

    # Drug -> Disease (TREATS/INDICATED_FOR) via disease references
    for drid, drug in drug_by_id.items():
        indications = drug.get("indications") or drug.get("disease_ids") or []
        if isinstance(indications, str):
            indications = [indications]
        for ind_id in indications:
            if ind_id in disease_by_id:
                _add("Drug", drid, "INDICATED_FOR", "Disease", ind_id,
                     {"source": "metadata"})

    # Protein -> Disease (IMPLICATED_IN) via disease associations
    for pid, prot in protein_by_id.items():
        assoc_diseases = prot.get("disease_associations") or prot.get("disease_ids") or []
        if isinstance(assoc_diseases, str):
            assoc_diseases = [assoc_diseases]
        for did in assoc_diseases:
            if did in disease_by_id:
                _add("Protein", pid, "IMPLICATED_IN", "Disease", did,
                     {"source": "metadata"})

    # Clinical trials -> Disease (STUDIES) and Drug (USES)
    for trial in entities_by_collection.get("clinical_trials", []):
        trial_id = trial.get("id", "")
        if not trial_id:
            continue
        condition_ids = trial.get("condition_ids") or trial.get("disease_ids") or []
        if isinstance(condition_ids, str):
            condition_ids = [condition_ids]
        for cid in condition_ids:
            if cid in disease_by_id:
                _add("Trial", trial_id, "STUDIES", "Disease", cid, {"source": "metadata"})

        intervention_ids = trial.get("intervention_ids") or trial.get("drug_ids") or []
        if isinstance(intervention_ids, str):
            intervention_ids = [intervention_ids]
        for iid in intervention_ids:
            if iid in drug_by_id:
                _add("Trial", trial_id, "USES", "Drug", iid, {"source": "metadata"})

    # Variant -> Gene (VARIANT_OF) and Variant -> Disease (ASSOCIATED_WITH)
    for var in entities_by_collection.get("variants", []):
        vid = var.get("id", "")
        if not vid:
            continue
        gene_ref = var.get("gene_id") or var.get("gene")
        if gene_ref and gene_ref in gene_by_id:
            _add("Variant", vid, "VARIANT_OF", "Gene", gene_ref, {"source": "metadata"})
        disease_ref = var.get("disease_id") or var.get("trait_id")
        if disease_ref and disease_ref in disease_by_id:
            _add("Variant", vid, "ASSOCIATED_WITH", "Disease", disease_ref, {"source": "metadata"})

    return edges


async def sync_graph():
    """Main sync: read all Qdrant entities, infer edges, push to GraphStore."""
    log.info("Connecting to Qdrant at %s:%s", settings.qdrant_host, settings.qdrant_port)
    client = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)

    entities_by_collection: Dict[str, List[Dict[str, Any]]] = {}
    total_entities = 0

    for coll in COLLECTIONS:
        try:
            exists = await client.collection_exists(coll)
            if not exists:
                log.info("Collection '%s' does not exist, skipping", coll)
                continue
            entities = await _scroll_all(client, coll)
            entities_by_collection[coll] = entities
            total_entities += len(entities)
            log.info("Read %d entities from '%s'", len(entities), coll)
        except Exception as e:
            log.warning("Failed to read collection '%s': %s", coll, e)

    if total_entities == 0:
        log.warning("No entities found in Qdrant — graph will be empty. "
                     "Run ingest_data.py first.")
        return

    # Create nodes in graph store
    store = get_graph_store()
    node_count = 0
    for coll, entities in entities_by_collection.items():
        label = COLLECTION_LABEL.get(coll, "Entity")
        for ent in entities:
            eid = ent.get("id", ent.get("_point_id", ""))
            if not eid:
                continue
            props = {k: v for k, v in ent.items()
                     if k not in ("_point_id", "_collection") and isinstance(v, (str, int, float, bool))}
            await store.create_node(label, str(eid), props)
            node_count += 1

    log.info("Created %d nodes in graph store", node_count)

    # Infer and create edges
    edges = _infer_edges(entities_by_collection)
    edge_count = 0
    for src_label, src_id, rel, dst_label, dst_id, props in edges:
        await store.create_edge(src_label, str(src_id), rel, dst_label, str(dst_id), props)
        edge_count += 1

    log.info("Created %d edges in graph store", edge_count)
    log.info("Knowledge graph sync complete: %d nodes, %d edges", node_count, edge_count)


if __name__ == "__main__":
    asyncio.run(sync_graph())
