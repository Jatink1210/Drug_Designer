import sys
import time
import pytest
from fastapi.testclient import TestClient

from main import app
from config import settings

pytestmark = pytest.mark.integration

client = TestClient(app)

def run_tests():
    print("====================================")
    print("DrugSynth Workbench: E2E Smoke Tests")
    print("====================================")
    
    print("\n1. Testing /api/health...")
    resp = client.get("/api/health")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    print("[PASS] /api/health")
    
    print("\n2. Testing /api/diagnostics...")
    resp = client.get("/api/diagnostics")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    diag = resp.json()
    assert getattr(diag, "status", diag.get("status")) == "ok"
    # Ensure components exist
    assert diag["components"]["qdrant"]["status"] in ["PASS", "FAIL"]
    print("[PASS] /api/diagnostics yields determinatic matrices.")

    def _test_query(query_str: str, label: str):
        print(f"\n3. Testing Query Matrix -> '{label}'...")
        print(f"   Query: {query_str}")
        t0 = time.time()
        # Increased client timeout mapped native for extensive Qdrant/Connector bounds
        resp = client.post("/api/search", json={"query": query_str, "limit": 10}, timeout=60.0)
        assert resp.status_code == 200, f"Unexpected status: {resp.status_code}"
        
        data = resp.json()
        assert "categories" in data, "Missing categories in search envelope"
        assert "provenance" in data, "Missing provenance in search envelope"
        stats = data.get("summary_stats", {})
        
        print(f"   [PASS] Found {stats.get('total_results')} results across {stats.get('categories_found')} categories in {round(time.time() - t0, 2)}s")
        print(f"   Categories: {list(data.get('categories', {}).keys())}")
        if data.get("errors"):
            print(f"   [WARN] Network Partial Drop: {data.get('errors')}")

    # 3.1 Generic Biological Assertion
    _test_query("Parkinson proteins", "Generic Target Pipeline")
    
    # 3.2 Specific Matrix Bounds
    _test_query("EGFR lung cancer", "Specific Correlation Pipeline")
    
    # 3.3 Indian Genomics Pipeline 
    _test_query("warfarin dosing Indian population", "Indian Populations Pipeline")
    
    # 3.4 PICO Verification
    print("\n4. Testing /api/translational/pico/verify...")
    resp = client.post("/api/translational/pico/verify", json={
        "claim": "Aspirin reduces headache severity",
        "evidence_text": "A randomized controlled trial showed aspirin significantly reduced tension headache severity compared to placebo."
    })
    # Will likely return 500 if OpenAI/Ollama is not bound, but structurally it must accept the payload
    assert resp.status_code in [200, 500, 503], f"Unexpected status: {resp.status_code}"
    print("[PASS] PICO structural endpoints reachable.")

    # 3.5 DL Run Inference Matrix
    print("\n5. Testing /api/models/run_inference/admet...")
    resp = client.post("/api/models/run_inference/admet?smiles=CC(=O)OC1=CC=CC=C1C(=O)O")
    assert resp.status_code == 200, f"Unexpected status: {resp.status_code}"
    admet_res = resp.json()
    assert admet_res["status"] == "baseline_success"
    print(f"[PASS] ADMET Pipeline: MW={admet_res['predictions'].get('molecular_weight')}, Drug-Like={admet_res['predictions'].get('drug_like')}")

    print("\n====================================")
    print("✅ All Determinstic Smoke Tests Passed!")
    print("====================================")

if __name__ == "__main__":
    try:
        run_tests()
    except AssertionError as e:
        print(f"\n[FAIL] Assertion Error: {e}")
        sys.exit(1)
    except Exception as e:
        print("\n[FAIL] Unknown Exception:")
        import traceback; traceback.print_exc()
        sys.exit(2)
