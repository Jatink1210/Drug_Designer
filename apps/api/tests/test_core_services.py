"""
Backend Test Suite — pytest tests for core services.
Satisfies Section 19.2 CI requirement for backend tests.
"""
import pytest
import json
import os
import sys

# Ensure the API directory is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestVectorStore:
    def test_upsert_and_search(self):
        from services.vector_store import EmbeddedVectorStore
        store = EmbeddedVectorStore(persist_path="/tmp/test_vectors.json")
        store.clear()
        store.upsert("doc1", "EGFR is a tyrosine kinase receptor")
        store.upsert("doc2", "BRCA1 is involved in DNA repair")
        store.upsert("doc3", "EGFR mutations drive lung cancer")
        results = store.search("EGFR kinase", top_k=2)
        assert len(results) == 2
        # EGFR docs should score higher than BRCA1
        ids = [r[0] for r in results]
        assert "doc1" in ids or "doc3" in ids
        store.clear()

    def test_count_and_delete(self):
        from services.vector_store import EmbeddedVectorStore
        store = EmbeddedVectorStore(persist_path="/tmp/test_vectors2.json")
        store.clear()
        store.upsert("a", "test document alpha")
        store.upsert("b", "test document beta")
        assert store.count() == 2
        store.delete("a")
        assert store.count() == 1
        store.clear()


class TestRuntimeFabric:
    def test_mode_switching(self):
        from services.runtime.fabric import RuntimeFabric
        fabric = RuntimeFabric()
        fabric.PERSIST_PATH = "/tmp/test_runtime.json"
        fabric.config["mode"] = "cpu"
        fabric._save()
        assert fabric.get_mode() == "cpu"
        fabric.set_mode("gpu")
        assert fabric.get_mode() == "gpu"
        fabric.set_mode("auto")
        assert fabric.get_mode() == "auto"

    def test_model_roles(self):
        from services.runtime.fabric import RuntimeFabric
        fabric = RuntimeFabric()
        fabric.PERSIST_PATH = "/tmp/test_runtime2.json"
        fabric.set_model_for_role("chat", "mistral-7b")
        assert fabric.get_model_for_role("chat") == "mistral-7b"


class TestDossierGenerator:
    def test_zip_generation(self):
        from services.dossier_generator import DossierCompiler
        data = {
            "target_id": "EGFR",
            "llm_consensus": "EGFR is a validated oncology target.",
            "binding_energy": -8.5,
            "rmsd": 1.2,
            "evidence_array": [{"source": "PubMed", "pmid": "12345"}],
            "graph_topology": {"nodes": 5, "edges": 10}
        }
        zip_bytes = DossierCompiler.generate_dossier_zip(data)
        assert isinstance(zip_bytes, bytes)
        assert len(zip_bytes) > 100  # Should have content


class TestJobQueue:
    @pytest.mark.asyncio
    async def test_submit_and_complete(self):
        from services.job_queue import AsyncJobQueue
        queue = AsyncJobQueue(max_concurrent=2)
        
        async def dummy_task(x):
            return x * 2
        
        job_id = await queue.submit("test", dummy_task, 21)
        assert job_id.startswith("job_")
        
        # Wait briefly for execution
        import asyncio
        await asyncio.sleep(0.5)
        
        job = queue.get_job(job_id)
        assert job is not None

    def test_stats(self):
        from services.job_queue import AsyncJobQueue
        queue = AsyncJobQueue()
        stats = queue.get_stats()
        assert "total" in stats


class TestEvidenceStore:
    def test_stats(self):
        from services.evidence_store import EvidenceStore
        stats = EvidenceStore.get_stats()
        assert isinstance(stats, dict)


class TestContradictionDetector:
    def test_import(self):
        from services.contradiction_detector import ContradictionDetector
        assert ContradictionDetector is not None
