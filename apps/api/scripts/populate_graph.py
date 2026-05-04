"""Knowledge Graph population script — loads external biomedical databases into Neo4j.

Estimated record counts (approximate, depends on filter thresholds):
  KEGG     : ~550 pathways, ~7,500 gene-pathway edges, ~18,000 compound nodes
  Reactome : ~2,500 reactions, ~10,000 participant edges
  STRING   : ~1.1M protein pairs (confidence ≥ 700, filtered from 11M total)
  UniProt  : ~560,000 reviewed human proteins

Node labels created  : Gene, Protein, Pathway, Drug, Disease, Variant, ClinicalTrial
Relationship types   : INTERACTS_WITH, PARTICIPATES_IN, TARGETS,
                       ASSOCIATED_WITH, MANIFESTS_AS, ENCODES, REGULATES

Usage:
  python apps/api/scripts/populate_graph.py
  python apps/api/scripts/populate_graph.py --sources kegg reactome
  python apps/api/scripts/populate_graph.py --batch-size 500 --dry-run

The script is resumable: MERGE queries skip nodes/edges that already exist.
Progress is printed to stdout; structured logs go to structlog.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

# ---------------------------------------------------------------------------
# Path setup: make apps/api importable
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_API_DIR = _SCRIPT_DIR.parent
sys.path.insert(0, str(_API_DIR))

import structlog

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Node / edge MERGE helpers
# ---------------------------------------------------------------------------

async def _merge_node(
    session,
    label: str,
    node_id: str,
    properties: Dict[str, Any],
) -> None:
    """MERGE a node by `id`, then SET non-null extra properties."""
    props = {k: v for k, v in properties.items() if v is not None}
    await session.run(
        f"MERGE (n:{label} {{id: $id}}) SET n += $props",
        id=node_id,
        props=props,
    )


async def _merge_edge(
    session,
    src_label: str,
    src_id: str,
    rel: str,
    dst_label: str,
    dst_id: str,
    properties: Optional[Dict[str, Any]] = None,
) -> None:
    """MERGE an edge between two existing nodes."""
    props = {k: v for k, v in (properties or {}).items() if v is not None}
    await session.run(
        f"""
        MATCH (a:{src_label} {{id: $src_id}})
        MATCH (b:{dst_label} {{id: $dst_id}})
        MERGE (a)-[r:{rel}]->(b)
        SET r += $props
        """,
        src_id=src_id,
        dst_id=dst_id,
        props=props,
    )


async def _batch_merge(
    driver,
    items: Iterable[Any],
    process_fn,
    label: str,
    batch_size: int = 500,
    dry_run: bool = False,
) -> int:
    """Process items in batches, calling `process_fn(session, item)` for each."""
    count = 0
    async with driver.session() as session:
        for item in items:
            if dry_run:
                count += 1
                continue
            await process_fn(session, item)
            count += 1
            if count % batch_size == 0:
                print(f"  [{label}] {count} records processed…")
    return count


# ---------------------------------------------------------------------------
# KEGG
# ---------------------------------------------------------------------------

async def populate_kegg(driver, batch_size: int, dry_run: bool) -> None:
    """Load KEGG pathways, genes, compounds.

    Creates:
      - (Pathway) nodes
      - (Gene)-[:PARTICIPATES_IN]->(Pathway)
      - (Drug)-[:PARTICIPATES_IN]->(Pathway)
    """
    print("\n── KEGG ──────────────────────────────────")
    try:
        from connectors.kegg import KEGGConnector
        conn = KEGGConnector()
        pathways_raw = await conn.get_pathways()
    except Exception as exc:
        log.warning("kegg_fetch_failed", error=str(exc))
        print(f"  [WARN] KEGG fetch failed: {exc}")
        return

    pathway_count = 0
    edge_count = 0

    async with driver.session() as session:
        for pw in pathways_raw:
            pw_id = pw.get("id") or pw.get("pathway_id") or pw.get("entry", "")
            if not pw_id:
                continue
            if not dry_run:
                await _merge_node(session, "Pathway", pw_id, {
                    "name": pw.get("name") or pw.get("title", ""),
                    "source_db": "KEGG",
                    "species": pw.get("species", "hsa"),
                })
            pathway_count += 1

            for gene_sym in pw.get("genes", []):
                gene_id = f"gene:{gene_sym}"
                if not dry_run:
                    await _merge_node(session, "Gene", gene_id, {"name": gene_sym, "symbol": gene_sym})
                    await _merge_edge(session, "Gene", gene_id, "PARTICIPATES_IN", "Pathway", pw_id)
                edge_count += 1

            for cpd in pw.get("compounds", []):
                cpd_id = cpd if isinstance(cpd, str) else cpd.get("id", "")
                cpd_name = cpd if isinstance(cpd, str) else cpd.get("name", cpd_id)
                if not cpd_id:
                    continue
                if not dry_run:
                    await _merge_node(session, "Drug", cpd_id, {"name": cpd_name, "source_db": "KEGG"})
                    await _merge_edge(session, "Drug", cpd_id, "PARTICIPATES_IN", "Pathway", pw_id)
                edge_count += 1

            if (pathway_count % batch_size) == 0:
                print(f"  [KEGG] {pathway_count} pathways, {edge_count} edges…")

    print(f"  [KEGG] Done — {pathway_count} pathways, {edge_count} edges {'(dry-run)' if dry_run else ''}")


# ---------------------------------------------------------------------------
# Reactome
# ---------------------------------------------------------------------------

async def populate_reactome(driver, batch_size: int, dry_run: bool) -> None:
    """Load Reactome reactions and participants.

    Creates:
      - (Pathway) nodes (reaction level)
      - (Gene/Protein)-[:PARTICIPATES_IN]->(Pathway)
    """
    print("\n── Reactome ──────────────────────────────")
    try:
        from connectors.reactome import ReactomeConnector
        conn = ReactomeConnector()
        reactions = await conn.get_reactions()
    except Exception as exc:
        log.warning("reactome_fetch_failed", error=str(exc))
        print(f"  [WARN] Reactome fetch failed: {exc}")
        return

    rxn_count = 0
    edge_count = 0

    async with driver.session() as session:
        for rxn in reactions:
            rxn_id = rxn.get("id") or rxn.get("stId", "")
            if not rxn_id:
                continue
            if not dry_run:
                await _merge_node(session, "Pathway", rxn_id, {
                    "name": rxn.get("name") or rxn.get("displayName", ""),
                    "source_db": "Reactome",
                    "species": rxn.get("species", "Homo sapiens"),
                    "top_level_pathway": rxn.get("topLevelPathway", ""),
                })
            rxn_count += 1

            for participant in rxn.get("participants", []):
                p_type = participant.get("type", "Gene")
                p_id = participant.get("id") or participant.get("accession", "")
                p_name = participant.get("name", p_id)
                if not p_id:
                    continue
                neo_label = "Protein" if p_type in ("protein", "Protein") else "Gene"
                if not dry_run:
                    await _merge_node(session, neo_label, p_id, {"name": p_name, "source_db": "Reactome"})
                    await _merge_edge(session, neo_label, p_id, "PARTICIPATES_IN", "Pathway", rxn_id)
                edge_count += 1

            if (rxn_count % batch_size) == 0:
                print(f"  [Reactome] {rxn_count} reactions, {edge_count} edges…")

    print(f"  [Reactome] Done — {rxn_count} reactions, {edge_count} edges {'(dry-run)' if dry_run else ''}")


# ---------------------------------------------------------------------------
# STRING
# ---------------------------------------------------------------------------

async def populate_string(driver, batch_size: int, dry_run: bool, min_score: int = 700) -> None:
    """Load STRING protein-protein interactions (confidence ≥ min_score).

    Creates:
      - (Protein) nodes
      - (Protein)-[:INTERACTS_WITH {score}]->(Protein)
    """
    print(f"\n── STRING (confidence ≥ {min_score}) ────────────────")
    try:
        from connectors.string_db import STRINGConnector
        conn = STRINGConnector()
        interactions = await conn.get_interactions(min_score=min_score)
    except Exception as exc:
        log.warning("string_fetch_failed", error=str(exc))
        print(f"  [WARN] STRING fetch failed: {exc}")
        return

    count = 0
    async with driver.session() as session:
        for edge in interactions:
            p1 = edge.get("protein1") or edge.get("source_entity", "")
            p2 = edge.get("protein2") or edge.get("target_entity", "")
            score = edge.get("combined_score") or edge.get("score", 0)
            if not p1 or not p2:
                continue
            if not dry_run:
                await _merge_node(session, "Protein", p1, {"name": p1, "source_db": "STRING"})
                await _merge_node(session, "Protein", p2, {"name": p2, "source_db": "STRING"})
                await _merge_edge(session, "Protein", p1, "INTERACTS_WITH", "Protein", p2, {"score": score, "source_db": "STRING"})
            count += 1
            if (count % batch_size) == 0:
                print(f"  [STRING] {count} interactions…")

    print(f"  [STRING] Done — {count} interactions {'(dry-run)' if dry_run else ''}")


# ---------------------------------------------------------------------------
# UniProt
# ---------------------------------------------------------------------------

async def populate_uniprot(driver, batch_size: int, dry_run: bool) -> None:
    """Load reviewed human proteins from UniProt.

    Creates:
      - (Protein) nodes with canonical cross-refs
      - (Gene)-[:ENCODES]->(Protein) edges
    """
    print("\n── UniProt ────────────────────────────────")
    try:
        from connectors.uniprot import UniProtConnector
        conn = UniProtConnector()
        proteins = await conn.get_human_reviewed_proteins()
    except Exception as exc:
        log.warning("uniprot_fetch_failed", error=str(exc))
        print(f"  [WARN] UniProt fetch failed: {exc}")
        return

    count = 0
    async with driver.session() as session:
        for prot in proteins:
            accession = prot.get("accession") or prot.get("uniprot_id") or prot.get("id", "")
            if not accession:
                continue
            if not dry_run:
                await _merge_node(session, "Protein", accession, {
                    "name": prot.get("name") or prot.get("protein_name", ""),
                    "uniprot_id": accession,
                    "reviewed": True,
                    "organism": prot.get("organism", "Homo sapiens"),
                    "length": prot.get("length"),
                    "ensembl_gene": prot.get("ensembl_gene", ""),
                    "source_db": "UniProt",
                })
                gene_sym = prot.get("gene_symbol") or prot.get("gene_name", "")
                if gene_sym:
                    gene_id = f"gene:{gene_sym}"
                    await _merge_node(session, "Gene", gene_id, {"name": gene_sym, "symbol": gene_sym})
                    await _merge_edge(session, "Gene", gene_id, "ENCODES", "Protein", accession)
            count += 1
            if (count % batch_size) == 0:
                print(f"  [UniProt] {count} proteins…")

    print(f"  [UniProt] Done — {count} proteins {'(dry-run)' if dry_run else ''}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

ALL_SOURCES = ["kegg", "reactome", "string", "uniprot"]


async def main_async(args: argparse.Namespace) -> int:
    sources = args.sources or ALL_SOURCES

    from config import settings
    try:
        from neo4j import AsyncGraphDatabase  # type: ignore
    except ImportError:
        print("ERROR: neo4j driver not installed. Run: pip install neo4j>=6.1.0")
        return 1

    uri = settings.neo4j_uri
    user = settings.neo4j_user
    password = settings.neo4j_password

    if not password and not args.dry_run:
        print("ERROR: NEO4J_PASSWORD not set in environment / .env")
        return 1

    print(f"Connecting to Neo4j at {uri}…")
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    try:
        # Ping
        async with driver.session() as s:
            await s.run("RETURN 1")
        print("Neo4j connection OK\n")

        t0 = time.time()
        run_map = {
            "kegg":     lambda: populate_kegg(driver, args.batch_size, args.dry_run),
            "reactome": lambda: populate_reactome(driver, args.batch_size, args.dry_run),
            "string":   lambda: populate_string(driver, args.batch_size, args.dry_run, min_score=args.string_min_score),
            "uniprot":  lambda: populate_uniprot(driver, args.batch_size, args.dry_run),
        }

        for src in sources:
            if src not in run_map:
                print(f"  [SKIP] Unknown source: {src}")
                continue
            await run_map[src]()

        elapsed = time.time() - t0
        print(f"\n{'═'*55}")
        print(f"Population complete in {elapsed:.1f}s {'(dry-run — no writes)' if args.dry_run else ''}")
    finally:
        await driver.close()

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Populate Neo4j Knowledge Graph")
    parser.add_argument(
        "--sources", nargs="+", choices=ALL_SOURCES,
        metavar="SOURCE",
        help=f"Sources to load (default: all). Choices: {ALL_SOURCES}",
    )
    parser.add_argument("--batch-size", type=int, default=500, metavar="N",
                        help="MERGE batch reporting size (default: 500)")
    parser.add_argument("--string-min-score", type=int, default=700, metavar="N",
                        help="STRING combined score threshold (default: 700)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Count records without writing to Neo4j")
    return asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
