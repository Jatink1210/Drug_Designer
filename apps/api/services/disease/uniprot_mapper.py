import asyncio
import time
from typing import Dict, List

import structlog

from core.http_client import ResilientClient

log = structlog.get_logger(__name__)

UNIPROT_BASE = "https://rest.uniprot.org"


async def map_genes_to_uniprot(genes: List[str]) -> Dict[str, str]:
    """Enhanced gene to UniProt mapping with retry logic and multiple query strategies."""
    mapping: Dict[str, str] = {}

    if not genes:
        return mapping

    log.info("uniprot_mapper.start", gene_count=len(genes))
    client = ResilientClient(timeout=40.0)

    try:
        # Method 1: UniProt batch mapping (primary gene names)
        batch_mapping = await _uniprot_batch_mapping(client, genes)
        mapping.update(batch_mapping)
        log.info("uniprot_mapper.batch_done", found=len(batch_mapping))

        # Method 2: Individual lookups for unmapped genes
        unmapped = [g for g in genes if g not in mapping]
        if unmapped:
            individual = await _uniprot_individual_mapping(client, unmapped[:100])
            mapping.update(individual)
            log.info("uniprot_mapper.individual_done", found=len(individual))

        # Method 3: Alternative query formats for still-unmapped genes
        still_unmapped = [g for g in genes if g not in mapping]
        if still_unmapped:
            alt = await _uniprot_alternative_mapping(client, still_unmapped[:50])
            mapping.update(alt)
            log.info("uniprot_mapper.alternative_done", found=len(alt))
    finally:
        await client.close()

    log.info("uniprot_mapper.complete", total_mapped=len(mapping), total_genes=len(genes))
    return mapping


async def _uniprot_batch_mapping(client: ResilientClient, genes: List[str]) -> Dict[str, str]:
    """Batch mapping via UniProt ID-mapping service."""
    try:
        body, meta = await client.post(
            f"{UNIPROT_BASE}/idmapping/run",
            json_body={"from": "Gene_Name", "to": "UniProtKB", "ids": " ".join(genes[:400])},
        )
        if body is None:
            log.warning("uniprot_mapper.batch_submit_failed", meta=meta)
            return {}

        job_id = body.get("jobId")
        if not job_id:
            return {}

        # Poll for completion
        for attempt in range(15):
            await asyncio.sleep(3)
            status_body, _ = await client.get(f"{UNIPROT_BASE}/idmapping/status/{job_id}")
            if status_body is None:
                continue
            job_status = status_body.get("jobStatus")
            if job_status == "FINISHED":
                break
            if job_status == "ERROR":
                log.warning("uniprot_mapper.batch_job_error", job_id=job_id)
                return {}

        # Fetch results
        results_body, _ = await client.get(f"{UNIPROT_BASE}/idmapping/uniprotkb/results/{job_id}")
        mapping: Dict[str, str] = {}
        if results_body:
            for r in results_body.get("results", []):
                gene = r.get("from")
                acc = (r.get("to") or {}).get("primaryAccession")
                if gene and acc:
                    mapping[gene] = acc
        return mapping

    except Exception as exc:
        log.warning("uniprot_mapper.batch_error", error=str(exc))
        return {}


async def _uniprot_individual_mapping(client: ResilientClient, genes: List[str]) -> Dict[str, str]:
    """Individual search queries per gene."""
    mapping: Dict[str, str] = {}

    for gene in genes[:50]:
        queries = [
            f"gene_exact:{gene} AND organism_id:9606",
            f"gene:{gene} AND organism_id:9606",
            f"(gene_exact:{gene} OR gene_synonym:{gene}) AND organism_id:9606",
        ]
        for query in queries:
            body, _ = await client.get(
                f"{UNIPROT_BASE}/uniprotkb/search",
                params={"query": query, "fields": "accession,gene_primary,gene_synonym", "format": "json", "size": "1"},
            )
            if body and body.get("results"):
                acc = body["results"][0].get("primaryAccession")
                if acc:
                    mapping[gene] = acc
                    break
            await asyncio.sleep(0.3)
        await asyncio.sleep(0.5)

    return mapping


async def _uniprot_alternative_mapping(client: ResilientClient, genes: List[str]) -> Dict[str, str]:
    """Try mapping using alternative query formats and protein names."""
    mapping: Dict[str, str] = {}

    for gene in genes[:30]:
        queries = [
            f"(gene:{gene} OR protein_name:{gene}) AND organism_id:9606",
            f"gene_synonym:{gene} AND organism_id:9606",
            f"(gene_names:{gene} OR gene_oln:{gene}) AND organism_id:9606",
        ]
        for query in queries:
            body, _ = await client.get(
                f"{UNIPROT_BASE}/uniprotkb/search",
                params={"query": query, "fields": "accession,gene_primary,protein_name", "format": "json", "size": "1"},
            )
            if body and body.get("results"):
                acc = body["results"][0].get("primaryAccession")
                if acc:
                    mapping[gene] = acc
                    break
            await asyncio.sleep(0.4)
        await asyncio.sleep(0.2)

    return mapping
