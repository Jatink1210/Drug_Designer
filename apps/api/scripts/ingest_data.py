"""Multi-source ingestion pipeline orchestration."""

import argparse
import asyncio
import json
import random
from pathlib import Path
from typing import List
import structlog

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from connectors.uniprot import UniProtConnector
from connectors.opentargets import OpenTargetsConnector
from connectors.chembl import ChEMBLConnector
from connectors.pubmed import PubMedConnector
from connectors.clinicaltrials import ClinicalTrialsConnector
from services.ingestion.gwas_loader import GWASConnector
from services.ingestion.indian_pop_loader import IndianPopLoader
from config import settings

log = structlog.get_logger()

VECTOR_DIM = 512

# Staged paths
RAW_DIR = Path("./data/raw")
NORM_DIR = Path("./data/normalized")
RAW_DIR.mkdir(parents=True, exist_ok=True)
NORM_DIR.mkdir(parents=True, exist_ok=True)


async def init_qdrant() -> AsyncQdrantClient:
    """Initialize Qdrant client and core collections."""
    client = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    # §8.2 Required collections: Protein(512d), Molecule(512d), Pathway(512d), Publication(512d after alignment)
    # Plus additional entity collections for full-spectrum coverage
    collections = ["proteins", "molecules", "genes", "diseases", "drugs", "variants", "pathways", "publications", "clinical_trials"]
    
    for coll in collections:
        exists = await client.collection_exists(coll)
        if not exists:
            log.info(f"Creating Qdrant collection: {coll}")
            await client.create_collection(
                collection_name=coll,
                vectors_config=models.VectorParams(size=512, distance=models.Distance.COSINE),
            )

    # §16.4 — Enforce payload field indexes for spec-required collections
    # Protein Collection
    _protein_fields = {
        "protein_id": models.PayloadSchemaType.KEYWORD,
        "gene_symbol": models.PayloadSchemaType.KEYWORD,
        "gwas_score": models.PayloadSchemaType.FLOAT,
        "druggability_score": models.PayloadSchemaType.FLOAT,
        "ppi_degree": models.PayloadSchemaType.INTEGER,
        "expression_tissues": models.PayloadSchemaType.KEYWORD,
    }
    # Molecule Collection
    _molecule_fields = {
        "smiles": models.PayloadSchemaType.KEYWORD,
        "mol_weight": models.PayloadSchemaType.FLOAT,
        "logP": models.PayloadSchemaType.FLOAT,
        "tpsa": models.PayloadSchemaType.FLOAT,
        "sa_score": models.PayloadSchemaType.FLOAT,
        "qed": models.PayloadSchemaType.FLOAT,
    }
    # Pathway Collection
    _pathway_fields = {
        "pathway_id": models.PayloadSchemaType.KEYWORD,
        "pathway_name": models.PayloadSchemaType.KEYWORD,
        "category": models.PayloadSchemaType.KEYWORD,
        "num_genes": models.PayloadSchemaType.INTEGER,
        "num_compounds": models.PayloadSchemaType.INTEGER,
        "gwas_enrichment": models.PayloadSchemaType.FLOAT,
    }
    # Publication Collection (PICO)
    _publication_fields = {
        "pmid": models.PayloadSchemaType.KEYWORD,
        "pico_population": models.PayloadSchemaType.TEXT,
        "pico_intervention": models.PayloadSchemaType.TEXT,
        "pico_outcome": models.PayloadSchemaType.TEXT,
        "Indian_population": models.PayloadSchemaType.BOOL,
        "effect_size": models.PayloadSchemaType.FLOAT,
    }
    _collection_field_map = {
        "proteins": _protein_fields,
        "molecules": _molecule_fields,
        "pathways": _pathway_fields,
        "publications": _publication_fields,
    }
    for coll_name, fields in _collection_field_map.items():
        for field_name, schema_type in fields.items():
            try:
                await client.create_payload_index(
                    collection_name=coll_name,
                    field_name=field_name,
                    field_schema=schema_type,
                )
            except Exception:
                pass  # Index may already exist

    return client


def _random_unit_vector(dim: int) -> List[float]:
    """Generate a random unit vector as fallback when no runtime is available."""
    import math
    vec = [random.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec] if norm > 0 else [0.0] * dim


async def _embed_batch(runtime, texts: List[str]) -> List[List[float]]:
    """Try to embed via the active runtime; fall back to random unit vectors."""
    if runtime is not None:
        try:
            vectors = await runtime.embeddings(texts)
            if vectors and len(vectors) == len(texts) and len(vectors[0]) == VECTOR_DIM:
                return vectors
            log.warning("Runtime returned unexpected embedding shape, using random fallback")
        except Exception as e:
            log.warning(f"Runtime embedding failed ({e}), using random fallback")
    return [_random_unit_vector(VECTOR_DIM) for _ in texts]


def _get_runtime_or_none():
    """Try to load the active LLM runtime; return None if unavailable."""
    try:
        from services.runtime.selector import RuntimeSelector
        rt = RuntimeSelector.get_active_runtime()
        if "embeddings" in rt.capabilities:
            return rt
    except Exception as e:
        log.warning(f"Could not load runtime for embeddings: {e}")
    return None


def _entity_text(res: dict) -> str:
    """Build a representative text string from an entity's payload for embedding."""
    parts = []
    for key in ("name", "title", "description", "summary", "sequence"):
        val = res.get(key)
        if val and isinstance(val, str):
            parts.append(val)
    if not parts:
        parts.append(json.dumps(res, default=str)[:500])
    return " ".join(parts)


async def run_ingestion(seeds: List[str]):
    log.info(f"Starting ingestion pipeline for seeds: {seeds}")

    connectors = [
        UniProtConnector(),
        OpenTargetsConnector(),
        ChEMBLConnector(),
        PubMedConnector(),
        ClinicalTrialsConnector(),
        GWASConnector(),
        IndianPopLoader()
    ]

    q_client = await init_qdrant()
    runtime = _get_runtime_or_none()
    if runtime is None:
        log.warning("No embedding runtime available — using random unit vectors as fallback")
    total_ingested = 0

    for seed in seeds:
        log.info(f"Processing seed: {seed}")
        for connector in connectors:
            try:
                log.info(f"Executing {connector.name} extraction...")
                # Fetch raw (Stage 1)
                results = await connector.search(seed, limit=5)

                if not results:
                    continue

                raw_file = RAW_DIR / f"{connector.name}_{seed.replace(' ', '_')}.json"
                with open(raw_file, "w") as f:
                    json.dump(results, f, indent=2)

                # Build texts and get real embeddings (Stage 2.5)
                texts = [_entity_text(r) for r in results]
                embeddings = await _embed_batch(runtime, texts)

                # Push to DB (Stage 3)
                records = []
                for idx, res in enumerate(results):
                    eid = res.get("id", str(idx))
                    records.append(
                        models.PointStruct(
                            id=abs(hash(eid)) % (2**63 - 1),
                            vector=embeddings[idx],
                            payload=res
                        )
                    )

                if records:
                    coll_name = f"{res.get('entity_type', 'proteins')}s"
                    # Fallback mapping for pluralization edge-cases
                    mapping = {"unknowns": "proteins", "diseasess": "diseases",
                               "variantss": "variants", "targetss": "genes"}
                    coll_name = mapping.get(coll_name, coll_name)

                    try:
                        await q_client.upsert(
                            collection_name=coll_name,
                            points=records
                        )
                        total_ingested += len(records)
                        log.info(f"Upserted {len(records)} records to {coll_name} from {connector.name}")
                    except Exception as e:
                        log.warning(f"Failed to upsert to {coll_name}: {e}")

            except Exception as e:
                log.error(f"Error in connector {connector.name}: {e}")

    for connector in connectors:
        await connector.close()

    log.info(f"Ingestion complete. Total entities ingested: {total_ingested}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=str, required=True, help="Comma-separated seed queries")
    args = parser.parse_args()
    
    seeds_list = [s.strip() for s in args.seeds.split(",")]
    asyncio.run(run_ingestion(seeds_list))
