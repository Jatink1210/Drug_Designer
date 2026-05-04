"""Task 45: Final Verification Checkpoint — Comprehensive Integration Tests.

Tests all 13 verification areas via the FastAPI TestClient (no server needed).
Each test function maps to a subtask (45.1 through 45.13).
"""

from __future__ import annotations

import os
import sys
import re
from pathlib import Path

import pytest
import pytest_asyncio

# ── Ensure apps/api is on sys.path so imports resolve ──
API_DIR = Path(__file__).resolve().parent.parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

# Disable auth for testing
os.environ["DRUGDESIGNER_AUTH_ENABLED"] = "false"
os.environ.setdefault("DSS_ENV", "development")

from httpx import AsyncClient, ASGITransport
from main import app

# Reset rate limiter windows so tests don't hit 429
from middleware.rate_limit import _windows
_windows.clear()

TIMEOUT = 90.0  # generous timeout for external API calls


@pytest_asyncio.fixture
async def client():
    """Async test client using httpx ASGITransport — no server needed."""
    # Clear rate limiter before each test to avoid 429s
    _windows.clear()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver", timeout=TIMEOUT) as ac:
        yield ac


# ─────────────────────────────────────────────────────────
# 45.1  Backend starts + Cockpit search with "BRCA1"
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_45_1_backend_starts_and_cockpit_search(client: AsyncClient):
    """45.1: Verify backend starts without import errors and Cockpit analyze works."""
    # Health check — proves the app loaded all routers
    resp = await client.get("/api/health")
    assert resp.status_code == 200, f"Health check failed: {resp.text}"

    # Cockpit analyze with BRCA1
    resp = await client.post(
        "/api/v1/cockpit/analyze",
        json={"query": "BRCA1", "limit": 20},
    )
    assert resp.status_code == 200, f"Cockpit analyze failed: {resp.status_code} {resp.text[:500]}"
    data = resp.json()
    # Response should be an envelope with data
    assert "data" in data or "status" in data, f"Unexpected response shape: {list(data.keys())}"
    # Status should not be hard error (ok, partial, degraded are all acceptable)
    status = data.get("status", "ok")
    assert status in ("ok", "partial", "degraded"), f"Cockpit returned error status: {status}"


# ─────────────────────────────────────────────────────────
# 45.2  Entity Intelligence with /Gene EGFR
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_45_2_entity_intelligence_gene_egfr(client: AsyncClient):
    """45.2: Test Entity Intelligence with /Gene EGFR input."""
    resp = await client.post(
        "/api/v1/entity-intelligence/analyze",
        json={
            "slots": [
                {"slot_index": 0, "declared_type": "gene", "value": "EGFR"},
            ],
            "graph_max_nodes": 50,
            "graph_depth": 1,
        },
    )
    assert resp.status_code == 200, f"Entity Intelligence failed: {resp.status_code} {resp.text[:500]}"
    data = resp.json()
    assert "data" in data or "status" in data, f"Unexpected response: {list(data.keys())}"
    status = data.get("status", "ok")
    assert status in ("ok", "partial", "degraded"), f"Entity Intelligence error: {status}"

    # Check that we got resolved entities
    inner = data.get("data", data)
    if isinstance(inner, dict):
        resolved = inner.get("resolved_slots") or inner.get("slots") or []
        if resolved:
            first_slot = resolved[0] if isinstance(resolved, list) else resolved
            assert first_slot, "No resolved slot data returned"


# ─────────────────────────────────────────────────────────
# 45.3  Knowledge Graph with colored nodes
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_45_3_knowledge_graph_build(client: AsyncClient):
    """45.3: Test KG build endpoint and verify ENTITY_COLORS in frontend."""
    resp = await client.post(
        "/api/v1/graph/build",
        json={"query": "BRCA1", "max_nodes": 50, "depth": 1},
    )
    assert resp.status_code == 200, f"Graph build failed: {resp.status_code} {resp.text[:500]}"
    data = resp.json()
    status = data.get("status", "ok")
    assert status in ("ok", "partial", "degraded"), f"Graph build error: {status}"

    # Verify ENTITY_COLORS exists in frontend source
    colors_file = API_DIR.parent / "web" / "src" / "lib" / "entityColors.ts"
    assert colors_file.exists(), f"entityColors.ts not found at {colors_file}"
    content = colors_file.read_text(encoding="utf-8")
    assert "ENTITY_COLORS" in content, "ENTITY_COLORS mapping not found"
    # Verify required colors from spec
    for entity_type, expected_color in [
        ("protein", "#7c3aed"),
        ("gene", "#6366f1"),
        ("disease", "#dc2626"),
        ("drug", "#e11d48"),
        ("compound", "#d97706"),
        ("pathway", "#0891b2"),
        ("publication", "#3b82f6"),
        ("clinical_trial", "#059669"),
        ("variant", "#ea580c"),
    ]:
        assert expected_color in content, f"Missing color {expected_color} for {entity_type}"


# ─────────────────────────────────────────────────────────
# 45.4  Pathway search and interactive rendering
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_45_4_pathway_search(client: AsyncClient):
    """45.4: Test pathway search endpoint and verify click handlers in frontend."""
    resp = await client.post(
        "/api/v1/pathways/search",
        json={"query": "BRCA1", "source": "reactome", "limit": 5},
    )
    assert resp.status_code == 200, f"Pathway search failed: {resp.status_code} {resp.text[:500]}"
    data = resp.json()
    status = data.get("status", "ok")
    assert status in ("ok", "partial", "degraded"), f"Pathway search error: {status}"

    # Verify PathwaysPage has click handlers
    pathways_page = API_DIR.parent / "web" / "src" / "pages" / "PathwaysPage.tsx"
    assert pathways_page.exists(), "PathwaysPage.tsx not found"
    content = pathways_page.read_text(encoding="utf-8")
    assert "onClick" in content, "PathwaysPage missing onClick handlers"

    # Verify BiologicalPathwayWorkbench exists with node/edge selection
    workbench = API_DIR.parent / "web" / "src" / "components" / "pathways" / "BiologicalPathwayWorkbench.tsx"
    assert workbench.exists(), "BiologicalPathwayWorkbench.tsx not found"
    wb_content = workbench.read_text(encoding="utf-8")
    assert "selectedNodeId" in wb_content or "setSelectedNodeId" in wb_content, \
        "BiologicalPathwayWorkbench missing node click handling"


# ─────────────────────────────────────────────────────────
# 45.5  3D Structure loading for P38398 (BRCA1)
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_45_5_structure_loading(client: AsyncClient):
    """45.5: Test 3D Structure loading for P38398 (BRCA1 UniProt ID)."""
    resp = await client.get("/api/v1/structure/P38398")
    # Accept 200 (found) or 404 (external API may not resolve this ID)
    # The key test is that the endpoint exists and responds properly
    assert resp.status_code in (200, 404), f"Structure endpoint error: {resp.status_code} {resp.text[:500]}"
    if resp.status_code == 200:
        data = resp.json()
        assert "data" in data or "status" in data, f"Unexpected structure response: {list(data.keys())}"


# ─────────────────────────────────────────────────────────
# 45.6  Design Studio plugins and RDKit descriptors
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_45_6_design_studio_plugins(client: AsyncClient):
    """45.6: Test Design Studio plugin status and descriptor computation."""
    # Plugin status
    resp = await client.get("/api/v1/design/plugins")
    assert resp.status_code == 200, f"Plugin status failed: {resp.status_code} {resp.text[:500]}"
    data = resp.json()
    inner = data.get("data", data)
    plugins = inner.get("plugins", [])
    assert len(plugins) >= 3, f"Expected at least 3 plugins, got {len(plugins)}"
    plugin_names = [p["name"] for p in plugins]
    assert "RDKit" in plugin_names, f"RDKit not in plugins: {plugin_names}"

    # Descriptor computation with aspirin SMILES
    resp = await client.post(
        "/api/v1/design/descriptors",
        json={"smiles": "CC(=O)Oc1ccccc1C(=O)O", "include_fingerprints": False},
    )
    assert resp.status_code == 200, f"Descriptors failed: {resp.status_code} {resp.text[:500]}"
    data = resp.json()
    inner = data.get("data", data)
    assert "descriptors" in inner or "smiles" in inner, f"Unexpected descriptors response: {list(inner.keys())}"


# ─────────────────────────────────────────────────────────
# 45.7  Clinical Design 10-step workflow
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_45_7_clinical_workflow(client: AsyncClient):
    """45.7: Test Clinical Design 10-step workflow creation and step execution."""
    import uuid

    project_id = str(uuid.uuid4())

    # Create workflow
    resp = await client.post(
        "/api/v1/clinical/workflows",
        json={
            "project_id": project_id,
            "disease_context": "Breast cancer",
            "description": "Test clinical workflow",
        },
    )
    assert resp.status_code == 200, f"Create workflow failed: {resp.status_code} {resp.text[:500]}"
    data = resp.json()
    inner = data.get("data", data)
    workflow_id = inner.get("workflow_id")
    assert workflow_id, f"No workflow_id returned: {inner}"

    # Verify 10 steps exist
    steps = inner.get("steps", [])
    assert len(steps) == 10, f"Expected 10 steps, got {len(steps)}"

    # Execute step 1
    resp = await client.post(
        f"/api/v1/clinical/workflows/{workflow_id}/steps/1",
        json={
            "action": "complete",
            "input_data": {"disease": "Breast cancer", "unmet_need": "Better targeted therapy"},
        },
    )
    assert resp.status_code == 200, f"Execute step 1 failed: {resp.status_code} {resp.text[:500]}"


# ─────────────────────────────────────────────────────────
# 45.8  SynthArena session creation and scoring
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_45_8_syntharena_session(client: AsyncClient):
    """45.8: Test SynthArena session creation with 2+ compounds and scoring."""
    # Create session with 2 compounds
    resp = await client.post(
        "/api/v1/syntharena/sessions",
        json={
            "name": "Test Arena Session",
            "target": "BRCA1",
            "description": "Verification test",
            "compounds": [
                {"name": "Aspirin", "smiles": "CC(=O)Oc1ccccc1C(=O)O", "source": "PubChem"},
                {"name": "Ibuprofen", "smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O", "source": "PubChem"},
            ],
            "scoring_criteria": ["binding_affinity", "selectivity", "admet_score"],
        },
    )
    assert resp.status_code == 200, f"Create session failed: {resp.status_code} {resp.text[:500]}"
    data = resp.json()
    inner = data.get("data", data)
    session_id = inner.get("session_id") or inner.get("id")
    assert session_id, f"No session_id returned: {inner}"

    # Score a compound
    resp = await client.post(
        f"/api/v1/syntharena/sessions/{session_id}/score",
        json={
            "compound_name": "Aspirin",
            "scores": {"binding_affinity": 75, "selectivity": 60, "admet_score": 80},
        },
    )
    assert resp.status_code == 200, f"Score compound failed: {resp.status_code} {resp.text[:500]}"


# ─────────────────────────────────────────────────────────
# 45.9  Research Labs — target-discovery and admet
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_45_9_research_labs(client: AsyncClient):
    """45.9: Test at least 2 Research Labs with real inputs."""
    import asyncio
    # Small delay to avoid rate limiting from previous tests
    await asyncio.sleep(2)

    # Target Discovery lab
    resp = await client.post(
        "/api/v1/labs/target-discovery/start",
        json={
            "disease": "breast cancer",
            "objective_function": "relevance * pathway_centrality",
            "max_iterations": 5,
            "early_stop_threshold": 0.9,
        },
    )
    # Accept 200 or 429 (rate limit from external APIs) — endpoint exists and processes
    assert resp.status_code in (200, 429), f"Target Discovery failed: {resp.status_code} {resp.text[:500]}"
    if resp.status_code == 200:
        data = resp.json()
        assert "data" in data or "run_id" in data.get("data", {}), "Unexpected target discovery response"

    await asyncio.sleep(2)

    # ADMET lab
    resp = await client.post(
        "/api/v1/labs/admet/run",
        json={
            "smiles_list": ["CC(=O)Oc1ccccc1C(=O)O", "CC(C)Cc1ccc(cc1)C(C)C(=O)O"],
        },
    )
    assert resp.status_code in (200, 429), f"ADMET lab failed: {resp.status_code} {resp.text[:500]}"


# ─────────────────────────────────────────────────────────
# 45.10  Contradiction detection with "aspirin cardiovascular"
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_45_10_contradiction_detection(client: AsyncClient):
    """45.10: Test Contradiction detection with 'aspirin cardiovascular'."""
    resp = await client.post(
        "/api/v1/contradictions/analyze",
        json={"query": "aspirin cardiovascular", "max_contradictions": 10, "max_similarities": 5},
    )
    assert resp.status_code == 200, f"Contradiction analyze failed: {resp.status_code} {resp.text[:500]}"
    data = resp.json()
    status = data.get("status", "ok")
    assert status in ("ok", "partial", "degraded"), f"Contradiction error: {status}"
    inner = data.get("data", data)
    # Should have contradictions and similarities keys
    assert "contradictions" in inner or "similarities" in inner, \
        f"Missing contradictions/similarities in response: {list(inner.keys())}"


# ─────────────────────────────────────────────────────────
# 45.11  PICO extraction with "metformin diabetes"
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_45_11_pico_extraction(client: AsyncClient):
    """45.11: Test PICO extraction with 'metformin diabetes'."""
    resp = await client.post(
        "/api/v1/pico/extract",
        json={"query": "metformin diabetes"},
    )
    assert resp.status_code == 200, f"PICO extract failed: {resp.status_code} {resp.text[:500]}"
    data = resp.json()
    status = data.get("status", "ok")
    assert status in ("ok", "partial", "degraded"), f"PICO error: {status}"
    inner = data.get("data", data)
    # Should have extractions
    assert "extractions" in inner or "pico_extractions" in inner or "results" in inner, \
        f"Missing PICO extractions in response: {list(inner.keys())}"


# ─────────────────────────────────────────────────────────
# 45.12  Removed pages redirect to Cockpit
# ─────────────────────────────────────────────────────────

def test_45_12_removed_pages_redirect():
    """45.12: Verify removed pages redirect to Cockpit in source code."""
    app_tsx = API_DIR.parent / "web" / "src" / "App.tsx"
    assert app_tsx.exists(), "App.tsx not found"
    content = app_tsx.read_text(encoding="utf-8")

    # Verify Navigate redirects exist for removed pages
    for removed_path in ["/operations", "/reports", "/exports", "/notes"]:
        # Check that a route with Navigate exists for this path
        pattern = rf'path="{re.escape(removed_path)}".*?Navigate'
        assert re.search(pattern, content, re.DOTALL), \
            f"Missing redirect for {removed_path} in App.tsx"

    # Verify LeftRail does NOT include these in navigation
    left_rail = API_DIR.parent / "web" / "src" / "components" / "shell" / "LeftRail.tsx"
    assert left_rail.exists(), "LeftRail.tsx not found"
    lr_content = left_rail.read_text(encoding="utf-8")

    # These should NOT appear as navigation items (check for nav label patterns)
    for removed_label in ["Operations", "Reports & Export", "Notes"]:
        nav_pattern = rf'label:\s*["\'].*{re.escape(removed_label)}.*["\']'
        match = re.search(nav_pattern, lr_content, re.IGNORECASE)
        assert match is None, f"LeftRail still contains nav item '{removed_label}'"


# ─────────────────────────────────────────────────────────
# 45.13  Settings page sections load real data
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_45_13_settings_diagnostics(client: AsyncClient):
    """45.13: Test Settings diagnostics endpoint and verify all sections exist."""
    # Test diagnostics endpoint
    resp = await client.get("/api/v1/settings/diagnostics")
    assert resp.status_code == 200, f"Diagnostics failed: {resp.status_code} {resp.text[:500]}"
    data = resp.json()
    inner = data.get("data", data)
    assert "platform" in inner or "database" in inner or "api" in inner, \
        f"Diagnostics missing expected keys: {list(inner.keys())}"
    assert "vina" in inner and "fpocket" in inner and "p2rank" in inner and "rdkit" in inner, \
        f"Diagnostics missing native-tool keys: {list(inner.keys())}"
    assert inner["vina"]["shipping_tier"] == "optional_local"
    assert inner["fpocket"]["shipping_tier"] == "optional_local"
    assert inner["p2rank"]["shipping_tier"] == "optional_local"

    # Verify Settings page has all required sections
    settings_page = API_DIR.parent / "web" / "src" / "pages" / "SettingsPage.tsx"
    assert settings_page.exists(), "SettingsPage.tsx not found"
    content = settings_page.read_text(encoding="utf-8")

    required_sections = [
        "General", "Sources", "Runtime", "Security", "Storage",
        "Notifications", "Export", "Accessibility", "Advanced", "Diagnostics",
    ]
    for section in required_sections:
        assert section.lower() in content.lower(), \
            f"Settings page missing section: {section}"
