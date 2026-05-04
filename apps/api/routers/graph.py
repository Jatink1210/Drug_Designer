"""Graph API routes — Drug Designer §78.4, §124.

Works with embedded (NetworkX) or full (Neo4j) backend.
All responses wrapped in ResponseEnvelope (§78.1).
"""

import uuid
import time
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
import structlog

from services.graph_service import GraphService
from services.graph_store import get_graph_store
from models.envelope import build_envelope
from routers.auth import get_current_user
from core.db import get_db
from sqlalchemy.ext.asyncio import AsyncSession

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/graph", tags=["Knowledge Graph"], dependencies=[Depends(get_current_user)])


# ── Request / Response Models ────────────────────────────────

class NeighborhoodRequest(BaseModel):
    entity_id: str
    depth: int = 2


class ShortestPathRequest(BaseModel):
    source_id: str
    target_id: str


class GraphResponse(BaseModel):
    """§78.1 ResponseEnvelope-compatible graph response."""
    request_id: str
    status: str
    data: Optional[Dict[str, Any]] = None
    warnings: List[str] = []
    errors: List[Dict[str, Any]] = []
    timing: Dict[str, Any] = {}
    provenance: Dict[str, Any] = {}


async def startup_graph_constraints():
    """Run graph constraint setup. Called from the app lifespan handler."""
    gs = GraphService()
    try:
        await gs.setup_constraints()
    except Exception as e:
        log.warning("skipping_graph_constraints_setup", error=str(e))
    finally:
        await gs.close()


@router.get("/neighborhood", response_model=GraphResponse)
async def get_neighborhood_get(entity_id: str, request: Request, depth: int = 2) -> Dict[str, Any]:
    """§78.4: GET /api/v1/graph/neighborhood?entity_id=X&depth=Y"""
    return await _execute_graph_operation("neighborhood", request, entity_id=entity_id, depth=depth)


@router.post("/neighborhood", response_model=GraphResponse)
async def get_neighborhood_post(req: NeighborhoodRequest, request: Request) -> Dict[str, Any]:
    """POST alias for neighborhood traversal."""
    return await _execute_graph_operation("neighborhood", request, entity_id=req.entity_id, depth=req.depth)


@router.post("/shortest_path", response_model=GraphResponse)
async def get_shortest_path(req: ShortestPathRequest, request: Request) -> Dict[str, Any]:
    return await _execute_graph_operation("shortest_path", request, source_id=req.source_id, target_id=req.target_id)


@router.post("/expand", response_model=GraphResponse)
async def expand_graph(req: NeighborhoodRequest, request: Request) -> Dict[str, Any]:
    """§78.4: Traverses specific edge types (mapped to viking_walk natively)."""
    return await _execute_graph_operation("viking_walk", request, entity_id=req.entity_id, depth=req.depth)


@router.get("/stats")
async def get_graph_stats(request: Request) -> Dict[str, Any]:
    store = get_graph_store()
    return build_envelope(request, store.stats())


@router.get("/sample")
async def get_graph_sample(request: Request, limit: int = 50) -> Dict[str, Any]:
    """§124: GET /api/v1/graph/sample?limit=N — Return a sample of graph nodes and edges."""
    store = get_graph_store()
    try:
        sample = store.sample(limit) if hasattr(store, 'sample') else {"nodes": [], "edges": []}
    except Exception:
        sample = {"nodes": [], "edges": []}
    return build_envelope(request, sample)


async def _execute_graph_operation(op: str, request: Request, **kwargs) -> Dict[str, Any]:
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    started_at = datetime.now(timezone.utc)
    gs = GraphService()
    data = None
    warnings = []
    
    try:
        if op == "neighborhood":
            data = await gs.get_neighborhood(kwargs["entity_id"], kwargs["depth"])
        elif op == "shortest_path":
            data = await gs.get_shortest_path(kwargs["source_id"], kwargs["target_id"])
        elif op == "viking_walk":
            from services.graph.viking_walker import VikingGraphWalker
            walker = VikingGraphWalker()
            data = walker.compute_deep_random_walks(kwargs["entity_id"], kwargs["depth"])
            data["engine"] = "viking_walker"
            
        return build_envelope(request, data, warnings=warnings)
    except Exception as e:
        log.error("graph_operation_failed", op=op, error=str(e))
        return build_envelope(
            request, None, status="error",
            errors=[{"code": "GRAPH_OP_FAILED", "message": str(e), "recoverable": False}],
        )
    finally:
        await gs.close()


class GraphExportRequest(BaseModel):
    format: str = "json"  # json | graphml | cytoscape
    entity_ids: List[str] = []


@router.post("/export")
async def export_graph(req: GraphExportRequest, request: Request) -> Dict[str, Any]:
    """§82: POST /api/v1/graph/export — Export subgraph in requested format."""
    store = get_graph_store()
    graph_data = store.export_subgraph(req.entity_ids) if hasattr(store, 'export_subgraph') else store.stats()
    return build_envelope(request, {"format": req.format, "graph": graph_data})


# ── C-8: Contradiction edges overlay ─────────────────────────────────────

@router.get("/contradiction-edges")
async def get_contradiction_edges(
    request: Request,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """C-8: GET /api/v1/graph/contradiction-edges — Return KG edges flagged as contradictions.

    Each edge encodes source/target entity keys and a contradiction_type attribute
    so the frontend graph viewer can overlay contradiction highlights.
    """
    from sqlalchemy import select as sa_select
    from models.db_tables import EvidenceItemRecord

    stmt = (
        sa_select(EvidenceItemRecord)
        .where(EvidenceItemRecord.contradiction_state == "flagged")
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    edges = []
    for r in rows:
        ents = r.entities or []
        if isinstance(ents, list) and len(ents) >= 2:
            src = ents[0] if isinstance(ents[0], str) else (ents[0].get("symbol") or ents[0].get("id", ""))
            tgt = ents[1] if isinstance(ents[1], str) else (ents[1].get("symbol") or ents[1].get("id", ""))
        elif r.normalized_entity_id:
            src = r.normalized_entity_id
            tgt = r.source_name or "unknown"
        else:
            continue

        edges.append({
            "edge_id": f"contra:{r.id}",
            "source": src,
            "target": tgt,
            "type": "contradiction",
            "contradiction_type": r.contradiction_type or "unknown",
            "evidence_id": r.id,
            "label": r.title[:60] if r.title else "",
        })

    return build_envelope(request, {"edges": edges, "total": len(edges)})


# ── §124 Spec-Aligned Additional Endpoints ───────────────

@router.get("/edge/{edge_id}")
async def get_edge(edge_id: str, request: Request) -> Dict[str, Any]:
    """§124: GET /api/v1/graph/edge/{edgeId} — Get a specific edge by ID with full evidence."""
    store = get_graph_store()
    edge_data = store.get_edge(edge_id) if hasattr(store, 'get_edge') else None

    if not edge_data:
        # Parse edge_id to extract source-relation-target
        parts = edge_id.split("-", 2) if "-" in edge_id else [edge_id]
        edge_data = {
            "edge_id": edge_id,
            "source": parts[0] if len(parts) > 0 else None,
            "target": parts[-1] if len(parts) > 1 else None,
            "relationship_type": parts[1] if len(parts) > 2 else None,
            "reason": f"Relationship edge {edge_id}",
            "evidence_ids": [edge_id],
            "evidence_items": [],
            "source_db": "graph_store",
            "confidence": 0.5,
        }

    # Try to fetch evidence items from the evidence store
    evidence_items = []
    try:
        from core.db import AsyncSessionLocal
        from sqlalchemy import select
        from models.db_tables import EvidenceItemRecord

        ev_ids = edge_data.get("evidence_ids", [])
        if ev_ids:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(EvidenceItemRecord).where(EvidenceItemRecord.id.in_(ev_ids[:20]))
                )
                for r in result.scalars().all():
                    evidence_items.append({
                        "id": r.id,
                        "title": r.title,
                        "source": r.source_name,
                        "url": getattr(r, "url", None),
                        "snippet": getattr(r, "snippet", None),
                    })
    except Exception:
        pass

    edge_data["evidence_items"] = evidence_items
    warnings = [] if evidence_items else ["Evidence items pending full integration"]
    return build_envelope(request, edge_data, warnings=warnings)


@router.post("/export-snapshot")
async def export_snapshot(request: Request) -> Dict[str, Any]:
    """§124: POST /api/v1/graph/export-snapshot — Export current graph state."""
    store = get_graph_store()
    snapshot = store.stats()
    return build_envelope(request, {
        "snapshot_id": str(uuid.uuid4()),
        "graph_stats": snapshot,
        "exported_at": datetime.now(timezone.utc).isoformat(),
    })


# ── Advanced Graph Analytics Endpoints (§FR-GRAPH-005) ──────

class CommunityDetectionRequest(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    algorithm: str = "louvain"  # louvain | label_propagation | girvan_newman


class CentralityRequest(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    metrics: List[str] = ["degree", "betweenness", "pagerank"]


class ShortestPathAnalyticsRequest(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    source_id: str
    target_id: str
    max_length: int = 10


class SubgraphExtractRequest(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    node_ids: List[str]
    depth: int = 1


@router.post("/community-detection")
async def detect_communities(req: CommunityDetectionRequest, request: Request) -> Dict[str, Any]:
    """§FR-GRAPH-005: POST /api/v1/graph/community-detection — Detect communities in graph."""
    try:
        from services.graph.analytics import GraphAnalytics
        
        analytics = GraphAnalytics()
        result = analytics.detect_communities(
            nodes=req.nodes,
            edges=req.edges,
            algorithm=req.algorithm
        )
        
        return build_envelope(request, result)
        
    except Exception as e:
        log.error("community_detection_failed", error=str(e))
        return build_envelope(
            request, None, status="error",
            errors=[{"code": "COMMUNITY_DETECTION_FAILED", "message": str(e)}]
        )


@router.post("/centrality")
async def calculate_centrality(req: CentralityRequest, request: Request) -> Dict[str, Any]:
    """§FR-GRAPH-005: POST /api/v1/graph/centrality — Calculate centrality metrics."""
    try:
        from services.graph.analytics import GraphAnalytics
        
        analytics = GraphAnalytics()
        result = analytics.calculate_centrality(
            nodes=req.nodes,
            edges=req.edges,
            metrics=req.metrics
        )
        
        return build_envelope(request, result)
        
    except Exception as e:
        log.error("centrality_calculation_failed", error=str(e))
        return build_envelope(
            request, None, status="error",
            errors=[{"code": "CENTRALITY_CALCULATION_FAILED", "message": str(e)}]
        )


@router.post("/shortest-path")
async def find_shortest_path_analytics(req: ShortestPathAnalyticsRequest, request: Request) -> Dict[str, Any]:
    """§FR-GRAPH-005: POST /api/v1/graph/shortest-path — Find shortest path between nodes."""
    try:
        from services.graph.analytics import GraphAnalytics
        
        analytics = GraphAnalytics()
        result = analytics.find_shortest_path(
            nodes=req.nodes,
            edges=req.edges,
            source_id=req.source_id,
            target_id=req.target_id,
            max_length=req.max_length
        )
        
        return build_envelope(request, result)
        
    except Exception as e:
        log.error("shortest_path_failed", error=str(e))
        return build_envelope(
            request, None, status="error",
            errors=[{"code": "SHORTEST_PATH_FAILED", "message": str(e)}]
        )


@router.post("/subgraph-extract")
async def extract_subgraph(req: SubgraphExtractRequest, request: Request) -> Dict[str, Any]:
    """§FR-GRAPH-005: POST /api/v1/graph/subgraph-extract — Extract subgraph around nodes."""
    try:
        from services.graph.analytics import GraphAnalytics
        
        analytics = GraphAnalytics()
        result = analytics.extract_subgraph(
            nodes=req.nodes,
            edges=req.edges,
            node_ids=req.node_ids,
            depth=req.depth
        )
        
        return build_envelope(request, result)
        
    except Exception as e:
        log.error("subgraph_extraction_failed", error=str(e))
        return build_envelope(
            request, None, status="error",
            errors=[{"code": "SUBGRAPH_EXTRACTION_FAILED", "message": str(e)}]
        )


# ── Full KG Build from Multi-Source Search ───────────────

class GraphBuildRequest(BaseModel):
    query: str
    max_nodes: int = 2000
    depth: int = 3  # relationship depth to build


@router.post("/build")
async def build_graph_from_search(req: GraphBuildRequest, request: Request) -> Dict[str, Any]:
    """Build a complete knowledge graph from multi-source search results.
    Searches all biomedical databases and constructs entity-relationship graph
    with maximum depth — like MiroFish-style comprehensive exploration."""
    t0 = time.time()
    try:
        return await _build_graph_inner(req, request, t0)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        log.error("graph_build_failed", error=str(e), traceback=tb)
        return build_envelope(request, None, status="error",
                              errors=[{"code": "GRAPH_BUILD_FAILED", "message": str(e)}])


async def _build_graph_inner(req: GraphBuildRequest, request: Request, t0: float) -> Dict[str, Any]:
    from services.search_engine import execute_search
    envelope = await execute_search(req.query, limit=200)

    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []
    entity_index: Dict[str, List[str]] = defaultdict(list)

    def add_node(nid: str, label: str, ntype: str, props: Dict[str, Any] = None):
        if nid not in nodes:
            nodes[nid] = {
                "id": nid,
                "label": label,
                "type": ntype.lower(),
                "properties": props or {},
            }
            entity_index[ntype.lower()].append(nid)

    def add_edge(src: str, tgt: str, rel: str, props: Dict[str, Any] = None):
        if src in nodes and tgt in nodes:
            edges.append({
                "id": f"{src}-{rel}-{tgt}",
                "source": src,
                "target": tgt,
                "label": rel,
                "type": rel,
                "properties": props or {},
            })

    # Central query node
    query_nid = f"query:{req.query.lower().replace(' ', '_')[:50]}"
    add_node(query_nid, req.query, "query", {"role": "search_query"})

    # Process each category from the search envelope
    for cat_name, cat_result in (envelope.categories or {}).items():
        rows = cat_result.rows if hasattr(cat_result, "rows") else cat_result.get("rows", [])
        cat = cat_name.rstrip("s").lower()  # "proteins" -> "protein"

        for item in (rows or []):
            source = (item.get("source") or "unknown").lower()
            title = item.get("title") or item.get("name") or item.get("canonical_name") or ""
            item_id = item.get("id") or item.get("accession") or title[:40]
            if not item_id:
                continue

            nid = f"{cat}:{str(item_id).replace(' ', '_')[:80]}"

            # Build properties
            props = {}
            for k in ["description", "organism", "score", "pdb_ids", "gene_names",
                       "molecular_weight", "function", "accession", "doi", "journal",
                       "year", "authors", "phase", "status", "formula", "smiles",
                       "iupac_name", "synonyms", "source", "url", "confidence",
                       "entity_type", "canonical_name"]:
                if k in item and item[k]:
                    val = item[k]
                    if isinstance(val, (list, dict)):
                        props[k] = val
                    else:
                        props[k] = str(val)

            add_node(nid, title or str(item_id), cat, props)
            evidence_sentence = str(item.get("description") or item.get("snippet") or title or item_id)
            confidence = float(item.get("confidence") or item.get("score") or 0.65)
            add_edge(query_nid, nid, f"HAS_{cat.upper()}_RESULT", {
                "source_name": source,
                "source_family": cat,
                "confidence": confidence,
                "citation": title,
                "evidence_sentence": evidence_sentence,
                "contradiction_state": str(item.get("contradiction_state") or "none").lower(),
            })

            # Source node
            src_nid = f"source:{source}"
            add_node(src_nid, source.replace("_", " ").title(), "source", {"role": "data_source"})
            add_edge(src_nid, nid, "PROVIDES", {
                "source_name": source,
                "source_family": "connector",
                "confidence": confidence,
                "citation": title,
                "evidence_sentence": evidence_sentence,
                "contradiction_state": str(item.get("contradiction_state") or "none").lower(),
            })

            # === Entity-type specific deep relationships ===
            if cat in ("protein", "proteins"):
                gene_names = item.get("gene_names") or item.get("gene") or []
                if isinstance(gene_names, str):
                    gene_names = [g.strip() for g in gene_names.split(",") if g.strip()]
                for gene in gene_names[:5]:
                    gnid = f"gene:{gene.upper()}"
                    add_node(gnid, gene.upper(), "gene", {"symbol": gene.upper()})
                    add_edge(gnid, nid, "ENCODES", {
                        "source_name": source,
                        "source_family": "gene-protein",
                        "confidence": confidence,
                        "citation": title,
                        "evidence_sentence": evidence_sentence,
                        "contradiction_state": "none",
                    })

                pdb_ids = item.get("pdb_ids") or item.get("structures") or []
                if isinstance(pdb_ids, str):
                    pdb_ids = [p.strip() for p in pdb_ids.split(",") if p.strip()]
                elif isinstance(pdb_ids, list):
                    pdb_ids = [str(p) for p in pdb_ids]
                for pdb in pdb_ids[:5]:
                    pnid = f"structure:{pdb.upper()}"
                    add_node(pnid, pdb.upper(), "structure", {"pdb_id": pdb.upper()})
                    add_edge(nid, pnid, "HAS_STRUCTURE", {
                        "source_name": source,
                        "source_family": "structure",
                        "confidence": confidence,
                        "citation": title,
                        "evidence_sentence": evidence_sentence,
                        "contradiction_state": "none",
                    })

                org = item.get("organism")
                if org:
                    onid = f"organism:{org.lower().replace(' ', '_')}"
                    add_node(onid, org, "organism", {})
                    add_edge(nid, onid, "FROM_ORGANISM", {
                        "source_name": source,
                        "source_family": "organism",
                        "confidence": confidence,
                        "citation": title,
                        "evidence_sentence": evidence_sentence,
                        "contradiction_state": "none",
                    })

            elif cat in ("gene", "genes"):
                diseases = item.get("associated_diseases") or item.get("diseases") or []
                if isinstance(diseases, str):
                    diseases = [d.strip() for d in diseases.split(",") if d.strip()]
                for dis in diseases[:5]:
                    dnid = f"disease:{dis.lower().replace(' ', '_')}"
                    add_node(dnid, dis, "disease", {})
                    add_edge(nid, dnid, "ASSOCIATED_WITH", {
                        "source_name": source,
                        "source_family": "disease",
                        "confidence": confidence,
                        "citation": title,
                        "evidence_sentence": evidence_sentence,
                        "contradiction_state": str(item.get("contradiction_state") or "none").lower(),
                    })

            elif cat in ("drug", "drugs", "molecule", "molecules", "compound", "compounds"):
                targets = item.get("targets") or item.get("target_genes") or []
                if isinstance(targets, str):
                    targets = [t.strip() for t in targets.split(",") if t.strip()]
                for tgt in targets[:5]:
                    tnid = f"target:{tgt.upper()}"
                    add_node(tnid, tgt.upper(), "target", {})
                    add_edge(nid, tnid, "TARGETS", {
                        "source_name": source,
                        "source_family": "target",
                        "confidence": confidence,
                        "citation": title,
                        "evidence_sentence": evidence_sentence,
                        "contradiction_state": str(item.get("contradiction_state") or "none").lower(),
                    })

                indications = item.get("indications") or item.get("diseases") or []
                if isinstance(indications, str):
                    indications = [i.strip() for i in indications.split(",") if i.strip()]
                for ind in indications[:3]:
                    inid = f"disease:{ind.lower().replace(' ', '_')}"
                    add_node(inid, ind, "disease", {})
                    add_edge(nid, inid, "INDICATED_FOR", {
                        "source_name": source,
                        "source_family": "indication",
                        "confidence": confidence,
                        "citation": title,
                        "evidence_sentence": evidence_sentence,
                        "contradiction_state": str(item.get("contradiction_state") or "none").lower(),
                    })

            elif cat in ("disease", "diseases"):
                genes = item.get("genes") or item.get("associated_genes") or []
                if isinstance(genes, str):
                    genes = [g.strip() for g in genes.split(",") if g.strip()]
                for g in genes[:8]:
                    gnid = f"gene:{g.upper()}"
                    add_node(gnid, g.upper(), "gene", {"symbol": g.upper()})
                    add_edge(nid, gnid, "INVOLVES_GENE", {
                        "source_name": source,
                        "source_family": "disease",
                        "confidence": confidence,
                        "citation": title,
                        "evidence_sentence": evidence_sentence,
                        "contradiction_state": str(item.get("contradiction_state") or "none").lower(),
                    })

            elif cat in ("pathway", "pathways"):
                members = item.get("genes") or item.get("members") or []
                if isinstance(members, str):
                    members = [m.strip() for m in members.split(",") if m.strip()]
                for m in members[:10]:
                    mnid = f"gene:{m.upper()}"
                    add_node(mnid, m.upper(), "gene", {"symbol": m.upper()})
                    add_edge(nid, mnid, "CONTAINS", {
                        "source_name": source,
                        "source_family": "pathway",
                        "confidence": confidence,
                        "citation": title,
                        "evidence_sentence": evidence_sentence,
                        "contradiction_state": "none",
                    })

            elif cat in ("interaction", "interactions"):
                partners = item.get("interactors") or []
                if isinstance(partners, str):
                    partners = [p.strip() for p in partners.split(",") if p.strip()]
                for p in partners[:2]:
                    pnid = f"protein:{p}"
                    add_node(pnid, p, "protein", {})
                    add_edge(nid, pnid, "INTERACTS_WITH", {
                        "source_name": source,
                        "source_family": "ppi",
                        "confidence": confidence,
                        "citation": title,
                        "evidence_sentence": evidence_sentence,
                        "contradiction_state": str(item.get("contradiction_state") or "none").lower(),
                    })

            elif cat in ("variant", "variants"):
                gene = item.get("gene") or item.get("gene_symbol") or ""
                if gene:
                    gnid = f"gene:{gene.upper()}"
                    add_node(gnid, gene.upper(), "gene", {"symbol": gene.upper()})
                    add_edge(nid, gnid, "VARIANT_OF", {
                        "source_name": source,
                        "source_family": "variant",
                        "confidence": confidence,
                        "citation": title,
                        "evidence_sentence": evidence_sentence,
                        "contradiction_state": str(item.get("contradiction_state") or "none").lower(),
                    })

    # Also incorporate the preview graph from the search envelope
    preview = envelope.preview_graph or {}
    for pn in preview.get("nodes", []):
        pnid = pn.get("id", "")
        if pnid and pnid not in nodes:
            add_node(pnid, pn.get("label", pnid), pn.get("type", "unknown"), {})
    for pe in preview.get("edges", []):
        if pe.get("source") in nodes and pe.get("target") in nodes:
            preview_props = dict(pe.get("properties") or {})
            preview_props.setdefault("source_name", preview_props.get("source") or "search_preview")
            preview_props.setdefault("source_family", "preview_graph")
            preview_props.setdefault("confidence", float(preview_props.get("confidence") or 0.8))
            preview_props.setdefault("citation", preview_props.get("citation") or preview_props.get("title") or pe.get("label", "RELATED"))
            preview_props.setdefault("evidence_sentence", preview_props.get("evidence_sentence") or preview_props.get("sentence") or pe.get("label", "RELATED"))
            preview_props.setdefault("contradiction_state", str(preview_props.get("contradiction_state") or "none").lower())
            add_edge(pe["source"], pe["target"], pe.get("label", "RELATED"), preview_props)

    # === Cross-link genes via shared disease ===
    gene_diseases: Dict[str, set] = defaultdict(set)
    for e in edges:
        if e["type"] in ("ASSOCIATED_WITH", "INVOLVES_GENE"):
            src_type = nodes.get(e["source"], {}).get("type", "")
            tgt_type = nodes.get(e["target"], {}).get("type", "")
            if src_type == "gene" and tgt_type == "disease":
                gene_diseases[e["source"]].add(e["target"])
            elif src_type == "disease" and tgt_type == "gene":
                gene_diseases[e["target"]].add(e["source"])

    gene_list = list(gene_diseases.keys())
    for i in range(len(gene_list)):
        for j in range(i + 1, min(i + 10, len(gene_list))):
            shared = gene_diseases[gene_list[i]] & gene_diseases[gene_list[j]]
            if shared:
                add_edge(gene_list[i], gene_list[j], "CO_ASSOCIATED",
                         {
                             "shared_diseases": len(shared),
                             "source_name": "graph_builder",
                             "source_family": "bridge",
                             "confidence": min(0.95, 0.45 + (0.1 * len(shared))),
                             "citation": "Shared disease association",
                             "evidence_sentence": f"{nodes[gene_list[i]]['label']} and {nodes[gene_list[j]]['label']} share {len(shared)} disease associations.",
                             "contradiction_state": "none",
                         })

    # Bridge equivalent labels across merged entity types (gene↔target, gene↔protein)
    normalized_labels: Dict[str, List[str]] = defaultdict(list)
    for node in nodes.values():
        normalized_labels[str(node.get("label") or "").strip().lower()].append(node["id"])
    for node_ids in normalized_labels.values():
        if len(node_ids) < 2:
            continue
        for i in range(len(node_ids)):
            for j in range(i + 1, len(node_ids)):
                src_id = node_ids[i]
                tgt_id = node_ids[j]
                src_type = nodes[src_id].get("type")
                tgt_type = nodes[tgt_id].get("type")
                if src_type == tgt_type:
                    continue
                add_edge(src_id, tgt_id, "ALIAS_BRIDGE", {
                    "source_name": "graph_builder",
                    "source_family": "bridge",
                    "confidence": 0.74,
                    "citation": "Alias bridge",
                    "evidence_sentence": f"{nodes[src_id]['label']} appears across merged entity types ({src_type} → {tgt_type}).",
                    "contradiction_state": "none",
                })

    # Trim to max_nodes if needed
    nodes_list = list(nodes.values())
    if len(nodes_list) > req.max_nodes:
        nodes_list = nodes_list[:req.max_nodes]
        kept_ids = {n["id"] for n in nodes_list}
        edges = [e for e in edges if e["source"] in kept_ids and e["target"] in kept_ids]

    # Deduplicate edges
    seen_edges = set()
    unique_edges = []
    for e in edges:
        key = (e["source"], e["target"], e["type"])
        if key not in seen_edges:
            seen_edges.add(key)
            unique_edges.append(e)

    # Remove orphan nodes after bridging, but keep the central query node.
    node_degree: Dict[str, int] = defaultdict(int)
    for edge in unique_edges:
        node_degree[edge["source"]] += 1
        node_degree[edge["target"]] += 1
    kept_node_ids = {
        node_id
        for node_id in nodes.keys()
        if node_id == query_nid or node_degree.get(node_id, 0) > 0
    }
    unique_edges = [edge for edge in unique_edges if edge["source"] in kept_node_ids and edge["target"] in kept_node_ids]
    nodes_list = [node for node in nodes.values() if node["id"] in kept_node_ids]

    # ── Compute betweenness centrality via networkx ──
    try:
        import networkx as nx
        G = nx.Graph()
        for n in nodes_list:
            G.add_node(n["id"])
        for e in unique_edges:
            G.add_edge(e["source"], e["target"])
        centrality = nx.betweenness_centrality(G) if len(G.nodes) > 0 else {}
    except Exception:
        centrality = {}

    # Apply ENTITY_COLORS and centrality-based sizing to nodes
    ENTITY_COLORS = {
        "protein": "#7c3aed", "gene": "#6366f1", "disease": "#dc2626",
        "drug": "#e11d48", "compound": "#d97706", "pathway": "#0891b2",
        "publication": "#3b82f6", "clinical_trial": "#059669", "variant": "#ea580c",
        "molecule": "#f59e0b", "target": "#8b5cf6", "unknown": "#94a3b8",
        "query": "#6366f1", "source": "#6366f1", "structure": "#3b82f6",
        "organism": "#059669",
    }
    for n in nodes_list:
        ntype = n.get("type", "unknown").lower()
        n["color"] = ENTITY_COLORS.get(ntype, ENTITY_COLORS["unknown"])
        c = centrality.get(n["id"], 0.0)
        n["size"] = round(0.5 + c * 2.0, 4)

    # Populate edge reason and evidence_ids from properties
    for e in unique_edges:
        props = e.get("properties", {})
        # Ensure reason is non-empty
        if not e.get("reason"):
            evidence_sentence = props.get("evidence_sentence", "")
            citation = props.get("citation", "")
            e["reason"] = evidence_sentence or citation or f"{e.get('type', 'related')} relationship"
        # Ensure evidence_ids has at least one entry
        if not e.get("evidence_ids"):
            e["evidence_ids"] = [e.get("id", f"{e['source']}-{e['target']}")]
        # Populate relationship metadata
        e["relationship_type"] = e.get("type", "related")
        e["source_db"] = props.get("source_name", "graph_builder")
        e["confidence"] = float(props.get("confidence", 0.5))
        # Weight from confidence
        if "weight" not in e:
            e["weight"] = e["confidence"]

    # Build type summary
    type_counts = defaultdict(int)
    for n in nodes_list:
        type_counts[n["type"]] += 1

    latency = round((time.time() - t0) * 1000)
    return build_envelope(request, {
        "nodes": nodes_list,
        "edges": unique_edges,
        "stats": {
            "total_nodes": len(nodes_list),
            "total_edges": len(unique_edges),
            "entity_types": dict(type_counts),
            "query": req.query,
            "depth": req.depth,
            "latency_ms": latency,
        },
    })
