"""ESM-3 Large De Novo Protein Design endpoints.

Drug_Designer.md §24.2:
  "ESM 3 98B can handle De Novo Protein Design. If your framework identifies
  a disease mechanism that requires a specific protein-protein interaction
  (PPI) inhibitor, ESM 3 can generate the scaffold for a novel binder."

Routes:
  POST /api/v1/esm3/scaffold      — Generate de-novo protein scaffold
  POST /api/v1/esm3/embed         — Embed sequence with ESM-3 Large (2560-d)
  POST /api/v1/esm3/fold          — Structure prediction via Forge
  GET  /api/v1/esm3/health        — Forge API connectivity check
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from routers.auth import get_current_user
from core.rbac import require_role, Role
from core.db import get_db
from models.envelope import build_envelope
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

log = structlog.get_logger()

router = APIRouter(prefix="/api/v1/esm3", tags=["esm3-protein-design"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class ScaffoldRequest(BaseModel):
    partial_sequence: Optional[str] = Field(
        None,
        description="Partial amino-acid sequence with '_' as mask tokens. "
                    "Fixed residues are preserved; masked positions are generated.",
        example="MKTAY____QRQISFVK____WKRQTLG",
    )
    target_description: Optional[str] = Field(
        None,
        description="Free-text description of binding target or desired function.",
        example="PPI inhibitor targeting EGFR-KRAS interface",
    )
    motif_sequences: Optional[List[str]] = Field(
        None,
        description="Short motif strings that must appear in the generated sequence.",
    )
    num_steps: int = Field(8, ge=1, le=32, description="ESM-3 generation steps.")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature.")
    project_id: Optional[str] = None
    run_id: Optional[str] = None


class EmbedRequest(BaseModel):
    sequence: str = Field(..., description="Amino-acid sequence.")
    protein_id: Optional[str] = None


class FoldRequest(BaseModel):
    sequence: str = Field(..., description="Amino-acid sequence to fold.")
    protein_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/scaffold", response_model=Dict[str, Any])
async def generate_scaffold(
    body: ScaffoldRequest,
    request: Request,
    user=Depends(require_role(Role.COLLABORATOR)),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Generate a de-novo protein scaffold using ESM-3 Large (98B) via Forge API.

    Returns generated sequence with per-residue confidence and full provenance.
    DEGRADED if Forge API is unreachable (returns error envelope, not exception).
    """
    try:
        from services.ml.esm3_client import get_esm3_client
        client = get_esm3_client()
        result = await client.generate_protein_scaffold(
            partial_sequence=body.partial_sequence,
            target_description=body.target_description,
            motif_sequences=body.motif_sequences,
            num_steps=body.num_steps,
            temperature=body.temperature,
            project_id=body.project_id,
            run_id=body.run_id,
        )
        log.info(
            "esm3_scaffold_endpoint_success",
            seq_len=len(result.get("sequence", "")),
            project_id=body.project_id,
        )
        # A-8: audit log — model inference
        try:
            from core.audit import log_audit
            await log_audit(
                db, user_id=getattr(user, "id", "system"),
                action="model.inference",
                resource_type="esm3.scaffold",
                resource_id=body.project_id or "none",
                details={"model": "esm3-large-2024-08", "project_id": body.project_id},
            )
            await db.commit()
        except Exception:
            pass
        return build_envelope(request, result)
    except RuntimeError as e:
        # Missing API key — configuration error
        log.warning("esm3_scaffold_config_error", error=str(e))
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        log.error("esm3_scaffold_error", error=str(e))
        return build_envelope(
            request,
            {"error": str(e), "model": "esm3-large-2024-08"},
            status="degraded",
        )


@router.post("/embed", response_model=Dict[str, Any])
async def embed_sequence(
    body: EmbedRequest,
    request: Request,
    user=Depends(require_role(Role.COLLABORATOR)),
) -> Dict[str, Any]:
    """Generate ESM-3 Large 2560-d embedding for a protein sequence.

    Use for high-value sequences requiring maximum quality embeddings.
    For bulk processing use ESM-C 600M (/api/v1/embeddings/protein).
    """
    try:
        from services.ml.esm3_client import get_esm3_client
        client = get_esm3_client()
        result = await client.embed_sequence(
            sequence=body.sequence,
            protein_id=body.protein_id,
        )
        return build_envelope(request, result)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        log.error("esm3_embed_error", error=str(e))
        return build_envelope(request, {"error": str(e)}, status="degraded")


@router.post("/fold", response_model=Dict[str, Any])
async def fold_sequence(
    body: FoldRequest,
    request: Request,
    user=Depends(require_role(Role.COLLABORATOR)),
) -> Dict[str, Any]:
    """Predict 3D structure from amino-acid sequence using ESM-3 via Forge API.

    Returns PDB string + per-residue pLDDT confidence + PTM score.
    """
    try:
        from services.ml.esm3_client import get_esm3_client
        client = get_esm3_client()
        result = await client.fold_sequence(
            sequence=body.sequence,
            protein_id=body.protein_id,
        )
        return build_envelope(request, result)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        log.error("esm3_fold_error", error=str(e))
        return build_envelope(request, {"error": str(e)}, status="degraded")


@router.get("/health", response_model=Dict[str, Any])
async def esm3_health(
    request: Request,
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Check ESM-3 Forge API connectivity.

    Returns ok / degraded. Does NOT fail the app healthcheck if Forge is down
    (Forge is optional premium capability, not a hard dependency).
    """
    try:
        from services.ml.esm3_client import get_esm3_client
        client = get_esm3_client()
        status = await client.health_check()
        return build_envelope(request, status)
    except RuntimeError as e:
        return build_envelope(
            request,
            {"status": "degraded", "error": str(e), "hint": "Set ESM_FORGE_API_KEY env var"},
        )
    except Exception as e:
        return build_envelope(
            request,
            {"status": "degraded", "error": str(e)},
        )
