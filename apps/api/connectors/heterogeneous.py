"""
Heterogeneous 20-Source Orchestrator (§32).

All individual connectors now extend BaseConnector with ResilientClient,
caching, rate-limiting, circuit-breaking, and provenance.
Standalone connectors: chembl, pubchem, string_db, reactome, ensembl,
gwas_catalog, kegg, clinvar (existed), pharos, drugcentral, dbsnp, omim,
orphanet (R-001 migration).
"""

import asyncio
import structlog
from typing import Any, Dict, List

from connectors.chembl import ChEMBLConnector
from connectors.pubchem import PubChemConnector
from connectors.string_db import STRINGConnector
from connectors.reactome import ReactomeConnector
from connectors.ensembl import EnsemblConnector
from connectors.gwas_catalog import GWASCatalogConnector
from connectors.kegg import KEGGConnector
from connectors.clinvar import ClinVarConnector
from connectors.pharos import PharosConnector
from connectors.drugcentral import DrugCentralConnector
from connectors.dbsnp import DbSnpConnector
from connectors.omim import OmimConnector
from connectors.orphanet import OrphanetConnector
# Phase F new connectors
from connectors.omnipath import OmniPathConnector
from connectors.cpic import CPICConnector
from connectors.gene2phenotype import Gene2PhenotypeConnector
from connectors.lens_org import LensOrgConnector
from connectors.nih_reporter import NIHReporterConnector
from connectors.innatedb import InnateDBConnector
from connectors.signor import SIGNORConnector
from connectors.pharmvar import PharmVarConnector
from connectors.gard import GARDConnector
from connectors.clingen import ClinGenConnector
from connectors.pharmgkb import PharmGKBConnector

log = structlog.get_logger(__name__)


# Aggregate wrapper: 13 unique APIs here + existing 7 (PubMed, PMC, Trials,
# Patents, UniProt, OpenTargets, AlphaFold) = 20 total.
class Heterogeneous20SourceOrchestrator:
    """Fan-out search across all heterogeneous connectors."""

    _CONNECTOR_CLASSES = [
        ("chembl", ChEMBLConnector),
        ("pubchem", PubChemConnector),
        ("string", STRINGConnector),
        ("reactome", ReactomeConnector),
        ("ensembl", EnsemblConnector),
        ("gwas", GWASCatalogConnector),
        ("pharos", PharosConnector),
        ("kegg", KEGGConnector),
        ("drugcentral", DrugCentralConnector),
        ("clinvar", ClinVarConnector),
        ("dbsnp", DbSnpConnector),
        ("omim", OmimConnector),
        ("orphanet", OrphanetConnector),
        # Phase F additions (F-1 through F-16)
        ("omnipath", OmniPathConnector),
        ("cpic", CPICConnector),
        ("gene2phenotype", Gene2PhenotypeConnector),
        ("lens_org", LensOrgConnector),
        ("nih_reporter", NIHReporterConnector),
        ("innatedb", InnateDBConnector),
        ("signor", SIGNORConnector),
        ("pharmvar", PharmVarConnector),
        ("gard", GARDConnector),
        ("clingen", ClinGenConnector),
        ("pharmgkb", PharmGKBConnector),
    ]

    @staticmethod
    async def search_all_distinct_apis(query: str) -> Dict[str, Any]:
        connectors = [
            (name, cls()) for name, cls in Heterogeneous20SourceOrchestrator._CONNECTOR_CLASSES
        ]

        log.info("heterogeneous_dispatch", total_connectors=len(connectors), query=query)

        tasks = [c.search(query) for _, c in connectors]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        final_map: Dict[str, Any] = {}
        for idx, (name, conn) in enumerate(connectors):
            res = results[idx]
            if isinstance(res, Exception):
                final_map[name] = [{"error": str(res)}]
            else:
                final_map[name] = res

        # Close all connector HTTP clients
        for _, conn in connectors:
            try:
                await conn.close()
            except Exception:
                pass

        return final_map
