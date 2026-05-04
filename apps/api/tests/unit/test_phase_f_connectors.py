"""G3: Unit tests for Phase F connectors (smoke tests with mocked HTTP).

Tests that each new connector:
1. Instantiates without error
2. Returns proper entity structure from search()
3. Returns None or dict from fetch_by_id()
"""
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, patch
from typing import Any, Dict, List, Tuple, Optional


# ─── Helpers ────────────────────────────────────────────────────────────────

def _make_cached_get(return_value: Any):
    """Return an AsyncMock that simulates _cached_get((data, meta))."""
    mock = AsyncMock(return_value=(return_value, {}))
    return mock


# ─── HGNC ───────────────────────────────────────────────────────────────────

class TestHGNCConnector:
    @pytest.mark.asyncio
    async def test_search_returns_gene_entities(self):
        from connectors.hgnc import HGNCConnector
        conn = HGNCConnector()
        mock_response = {
            "response": {
                "docs": [{"hgnc_id": "HGNC:1100", "symbol": "BRCA1", "name": "BRCA1 DNA repair gene", "locus_group": "protein-coding gene"}]
            }
        }
        with patch.object(conn, "_cached_get", _make_cached_get(mock_response)):
            results = await conn.search("BRCA1")
        assert isinstance(results, list)
        assert results[0]["entity_type"] == "gene"
        assert results[0]["canonical_name"] == "BRCA1"

    @pytest.mark.asyncio
    async def test_fetch_by_id_returns_dict(self):
        from connectors.hgnc import HGNCConnector
        conn = HGNCConnector()
        mock_response = {"response": {"docs": [{"hgnc_id": "HGNC:1100", "symbol": "BRCA1"}]}}
        with patch.object(conn, "_cached_get", _make_cached_get(mock_response)):
            result = await conn.fetch_by_id("HGNC:1100")
        assert result is None or isinstance(result, dict)


# ─── Gene Ontology ───────────────────────────────────────────────────────────

class TestGeneOntologyConnector:
    @pytest.mark.asyncio
    async def test_search_returns_go_terms(self):
        from connectors.gene_ontology import GeneOntologyConnector
        conn = GeneOntologyConnector()
        mock = {"results": [{"id": "GO:0006955", "name": "immune response", "aspect": "P", "definition": {"text": "def"}, "synonyms": []}], "pageInfo": {"total": 1}}
        with patch.object(conn, "_cached_get", _make_cached_get(mock)):
            results = await conn.search("immune")
        assert isinstance(results, list)
        assert results[0]["entity_type"] == "go_term"


# ─── OmicsDI ────────────────────────────────────────────────────────────────

class TestOmicsDIConnector:
    @pytest.mark.asyncio
    async def test_search_returns_omics_datasets(self):
        from connectors.omics_di import OmicsDIConnector
        conn = OmicsDIConnector()
        mock = {
            "datasets": [{"accession": "E-MTAB-1234", "database": "ArrayExpress", "name": "BRCA expression", "description": "desc", "omicsType": ["Transcriptomics"], "organism": ["Homo sapiens"]}]
        }
        with patch.object(conn, "_cached_get", _make_cached_get(mock)):
            results = await conn.search("BRCA")
        assert isinstance(results, list)
        assert results[0]["entity_type"] == "omics_dataset"


# ─── GEO NCBI ────────────────────────────────────────────────────────────────

class TestGEONCBIConnector:
    @pytest.mark.asyncio
    async def test_search_returns_expression_datasets(self):
        from connectors.geo_ncbi import GEONCBIConnector
        conn = GEONCBIConnector()
        search_mock = {"esearchresult": {"idlist": ["200123456"]}}
        summary_mock = {"result": {"uids": ["200123456"], "200123456": {"accession": "GSE123456", "title": "BRCA study", "taxon": "Homo sapiens", "gdstype": "Series", "n_samples": 24, "platform": "GPL570", "pdat": "2020-01-01", "pubmedids": []}}}
        call_count = 0
        async def multi_mock(*a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (search_mock, {})
            return (summary_mock, {})
        with patch.object(conn, "_cached_get", side_effect=multi_mock):
            results = await conn.search("BRCA")
        assert isinstance(results, list)
        if results:
            assert results[0]["entity_type"] == "expression_dataset"


# ─── EUtils NCBI ────────────────────────────────────────────────────────────

class TestEUtilsNCBIConnector:
    @pytest.mark.asyncio
    async def test_search_returns_gene_entities(self):
        from connectors.eutils_ncbi import EUtilsNCBIConnector
        conn = EUtilsNCBIConnector()
        search_mock = {"esearchresult": {"idlist": ["672"]}}
        summary_mock = {"result": {"uids": ["672"], "672": {"name": "BRCA1", "description": "BRCA1 gene", "summary": "DNA repair gene", "chromosome": "17", "maplocation": "17q21.31", "organism": {"scientificname": "Homo sapiens", "taxid": 9606}, "otheraliases": ""}}}
        call_count = 0
        async def multi_mock(*a, **kw):
            nonlocal call_count
            call_count += 1
            return (search_mock, {}) if call_count == 1 else (summary_mock, {})
        with patch.object(conn, "_cached_get", side_effect=multi_mock):
            results = await conn.search("BRCA1")
        assert isinstance(results, list)
        if results:
            assert results[0]["entity_type"] == "gene"


# ─── CTD ────────────────────────────────────────────────────────────────────

class TestCTDConnector:
    @pytest.mark.asyncio
    async def test_search_returns_gene_disease_assocs(self):
        from connectors.ctd import CTDConnector
        conn = CTDConnector()
        mock = [{"GeneSymbol": "BRCA1", "GeneID": "672", "DiseaseName": "Breast Cancer", "DiseaseID": "MESH:D001943", "OmimIDs": "", "InferenceScore": 9.5, "DirectEvidence": "marker/mechanism", "PubMedIDs": "12345678"}]
        with patch.object(conn, "_cached_get", _make_cached_get(mock)):
            results = await conn.search("BRCA1")
        assert isinstance(results, list)
        assert results[0]["entity_type"] == "gene_disease_association"


# ─── LIPID MAPS ─────────────────────────────────────────────────────────────

class TestLipidMapsConnector:
    @pytest.mark.asyncio
    async def test_search_returns_lipid_entities(self):
        from connectors.lipidmaps import LipidMapsConnector
        conn = LipidMapsConnector()
        mock = [{"lm_id": "LMFA01010001", "common_name": "Palmitic acid", "systematic_name": "hexadecanoic acid", "category": "Fatty Acyls", "main_class": "Fatty Acids", "sub_class": "Straight chain fatty acids", "formula": "C16H32O2", "exact_mass": "256.2402", "inchi": "InChI=...", "inchi_key": "IPCSVZSSVZVIGE-UHFFFAOYSA-N", "smiles": "CCCCCCCCCCCCCCCC(O)=O", "pubchem_cid": "985", "hmdbid": "HMDB0000220"}]
        with patch.object(conn, "_cached_get", _make_cached_get(mock)):
            results = await conn.search("palmitic")
        assert isinstance(results, list)
        assert results[0]["entity_type"] == "lipid"


# ─── Metabolomics Workbench ──────────────────────────────────────────────────

class TestMetabolomicsWorkbenchConnector:
    @pytest.mark.asyncio
    async def test_search_returns_study_entities(self):
        from connectors.metabolomics_wb import MetabolomicsWorkbenchConnector
        conn = MetabolomicsWorkbenchConnector()
        mock = {"study_id": "ST000001", "study_title": "BRCA1 Metabolomics", "study_summary": "Study of BRCA1", "institute": "NIH", "subject_species": "Homo sapiens"}
        with patch.object(conn, "_cached_get", _make_cached_get(mock)):
            results = await conn.search("BRCA1")
        assert isinstance(results, list)
        assert results[0]["entity_type"] == "metabolomics_study"


# ─── MalaCards ───────────────────────────────────────────────────────────────

class TestMalaCardsConnector:
    @pytest.mark.asyncio
    async def test_search_returns_disease_entities(self):
        from connectors.malacards import MalaCardsConnector
        conn = MalaCardsConnector()
        mock = {"diseases": [{"id": "breast-cancer", "name": "Breast Cancer", "summary": "...", "mimId": "114480", "aliases": [], "category": "Cancer", "score": 0.95}]}
        with patch.object(conn, "_cached_get", _make_cached_get(mock)):
            results = await conn.search("breast cancer")
        assert isinstance(results, list)
        assert results[0]["entity_type"] == "disease"


# ─── T3DB ────────────────────────────────────────────────────────────────────

class TestT3DBConnector:
    @pytest.mark.asyncio
    async def test_search_returns_toxin_entities(self):
        from connectors.t3db import T3DBConnector
        conn = T3DBConnector()
        mock = [{"t3db_id": "T3D0001", "common_name": "Arsenic", "description": "Heavy metal toxin", "cas_registry_number": "7440-38-2", "chemical_formula": "As", "smiles": "[As]", "exposure_routes": ["ingestion"], "toxicity": "high", "mechanism_of_toxicity": "...", "lethal_dose": "13 mg/kg", "target_count": 42}]
        with patch.object(conn, "_cached_get", _make_cached_get(mock)):
            results = await conn.search("arsenic")
        assert isinstance(results, list)
        assert results[0]["entity_type"] == "toxin"
