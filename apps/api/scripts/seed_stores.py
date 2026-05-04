"""Seed vector and graph stores with demo data — CC-0.3, CC-1.4.

Usage:
    python scripts/seed_stores.py

Seeds Qdrant collections (proteins, molecules, pathways, publications)
and Neo4j graph with representative entities for meaningful demos/tests.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import sys
import os

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Seed entities ─────────────────────────────────────────

SEED_PROTEINS = [
    {"id": "P04637", "name": "TP53", "organism": "Homo sapiens", "function": "Tumor suppressor"},
    {"id": "P00533", "name": "EGFR", "organism": "Homo sapiens", "function": "Receptor tyrosine kinase"},
    {"id": "P15056", "name": "BRAF", "organism": "Homo sapiens", "function": "Serine/threonine kinase"},
    {"id": "P38398", "name": "BRCA1", "organism": "Homo sapiens", "function": "DNA repair"},
    {"id": "P42336", "name": "PIK3CA", "organism": "Homo sapiens", "function": "Lipid kinase"},
    {"id": "P35354", "name": "PTGS2", "organism": "Homo sapiens", "function": "Cyclooxygenase"},
    {"id": "Q07817", "name": "BCL2L1", "organism": "Homo sapiens", "function": "Apoptosis regulator"},
    {"id": "P10275", "name": "AR", "organism": "Homo sapiens", "function": "Androgen receptor"},
]

SEED_MOLECULES = [
    {"id": "CHEMBL25", "name": "Aspirin", "smiles": "CC(=O)Oc1ccccc1C(=O)O"},
    {"id": "CHEMBL941", "name": "Ibuprofen", "smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O"},
    {"id": "CHEMBL553025", "name": "Erlotinib", "smiles": "COCCOc1cc2ncnc(Nc3cccc(c3)C#C)c2cc1OCCOC"},
    {"id": "CHEMBL1421", "name": "Vemurafenib", "smiles": "CCCS(=O)(=O)Nc1ccc(F)c(c1F)C(=O)c1cnc2cccnn12"},
    {"id": "CHEMBL1201583", "name": "Olaparib", "smiles": "O=C1C2CC3CC(C2)CC1(C3)NC(=O)c1cc2ccccc2[nH]1"},
    {"id": "CHEMBL1642", "name": "Metformin", "smiles": "CN(C)C(=N)NC(=N)N"},
]

SEED_PATHWAYS = [
    {"id": "R-HSA-1640170", "name": "Cell Cycle", "source": "Reactome"},
    {"id": "R-HSA-162582", "name": "Signal Transduction", "source": "Reactome"},
    {"id": "R-HSA-1643685", "name": "Disease", "source": "Reactome"},
    {"id": "hsa04110", "name": "Cell cycle", "source": "KEGG"},
    {"id": "hsa04151", "name": "PI3K-Akt signaling pathway", "source": "KEGG"},
    {"id": "WP4172", "name": "PI3K-Akt Signaling Pathway", "source": "WikiPathways"},
]

SEED_PUBLICATIONS = [
    {"id": "PMID:33087903", "title": "EGFR mutations in lung cancer", "journal": "Nature", "year": 2020},
    {"id": "PMID:28592505", "title": "BRAF V600E in melanoma", "journal": "NEJM", "year": 2017},
    {"id": "PMID:31562799", "title": "BRCA1 and DNA repair mechanisms", "journal": "Science", "year": 2019},
    {"id": "PMID:29625050", "title": "PI3K pathway in cancer", "journal": "Cell", "year": 2018},
    {"id": "PMID:32015507", "title": "TP53 mutations across cancer types", "journal": "Nature Reviews", "year": 2020},
]


def _deterministic_vector(seed_str: str, dim: int = 512) -> list:
    """Generate a deterministic pseudo-random vector from a seed string."""
    h = int(hashlib.sha256(seed_str.encode()).hexdigest(), 16)
    rng = random.Random(h)
    return [rng.gauss(0, 0.1) for _ in range(dim)]


async def seed_qdrant():
    """CC-0.3 / CC-1.4: Populate Qdrant collections with seed data."""
    try:
        from qdrant_client import AsyncQdrantClient
        from qdrant_client.models import Distance, VectorParams, PointStruct
        from config import settings

        client = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        log.info("Connected to Qdrant at %s:%d", settings.qdrant_host, settings.qdrant_port)

        collections = {
            "proteins": SEED_PROTEINS,
            "molecules": SEED_MOLECULES,
            "pathways": SEED_PATHWAYS,
            "publications": SEED_PUBLICATIONS,
        }

        for coll_name, items in collections.items():
            # Ensure collection exists
            try:
                await client.get_collection(coll_name)
            except Exception:
                await client.create_collection(
                    collection_name=coll_name,
                    vectors_config=VectorParams(size=512, distance=Distance.COSINE),
                )
                log.info("Created Qdrant collection: %s", coll_name)

            # Upsert seed points
            points = []
            for i, item in enumerate(items):
                vec = _deterministic_vector(f"{coll_name}:{item['id']}")
                points.append(PointStruct(
                    id=i,
                    vector=vec,
                    payload=item,
                ))

            await client.upsert(collection_name=coll_name, points=points)
            log.info("Seeded %d items into %s", len(points), coll_name)

        await client.close()
        log.info("Qdrant seeding complete")
    except ImportError:
        log.warning("qdrant_client not installed — skipping Qdrant seeding")
    except Exception as e:
        log.warning("Qdrant seeding failed (non-fatal): %s", e)


async def seed_neo4j():
    """CC-0.3: Seed Neo4j graph with representative entities and relationships."""
    try:
        from config import settings

        if not settings.neo4j_password:
            log.warning("NEO4J_PASSWORD not set — skipping Neo4j seeding")
            return

        from neo4j import AsyncGraphDatabase

        driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

        async with driver.session() as session:
            # Create protein nodes
            for p in SEED_PROTEINS:
                await session.run(
                    "MERGE (n:Protein {id: $id}) SET n.name = $name, n.organism = $organism",
                    id=p["id"], name=p["name"], organism=p["organism"],
                )

            # Create molecule nodes
            for m in SEED_MOLECULES:
                await session.run(
                    "MERGE (n:Molecule {id: $id}) SET n.name = $name, n.smiles = $smiles",
                    id=m["id"], name=m["name"], smiles=m["smiles"],
                )

            # Create pathway nodes
            for pw in SEED_PATHWAYS:
                await session.run(
                    "MERGE (n:Pathway {id: $id}) SET n.name = $name, n.source = $source",
                    id=pw["id"], name=pw["name"], source=pw["source"],
                )

            # Create some relationships
            await session.run(
                "MATCH (p:Protein {id: 'P00533'}), (m:Molecule {id: 'CHEMBL553025'}) "
                "MERGE (m)-[:TARGETS]->(p)"
            )
            await session.run(
                "MATCH (p:Protein {id: 'P15056'}), (m:Molecule {id: 'CHEMBL1421'}) "
                "MERGE (m)-[:TARGETS]->(p)"
            )
            await session.run(
                "MATCH (p:Protein {id: 'P42336'}), (pw:Pathway {id: 'hsa04151'}) "
                "MERGE (p)-[:PARTICIPATES_IN]->(pw)"
            )

            log.info("Neo4j seeding complete")

        await driver.close()
    except ImportError:
        log.warning("neo4j driver not installed — skipping Neo4j seeding")
    except Exception as e:
        log.warning("Neo4j seeding failed (non-fatal): %s", e)


async def main():
    log.info("Starting store seeding (CC-0.3, CC-1.4)...")
    await seed_qdrant()
    await seed_neo4j()
    log.info("Store seeding complete")


if __name__ == "__main__":
    asyncio.run(main())
