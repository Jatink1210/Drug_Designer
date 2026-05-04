"""Contradiction & Similarity Analysis API (Task 21).

POST /api/v1/contradictions/analyze — Full contradiction & similarity analysis.
Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from models.envelope import build_envelope as _shared_envelope
from routers.auth import get_current_user

router = APIRouter(prefix="/api/v1/contradictions", tags=["contradictions"])


def _build_envelope(req: Request, data: Any) -> Dict[str, Any]:
    return _shared_envelope(req, data)


class ContradictionAnalyzeRequest(BaseModel):
    """Request for full contradiction & similarity analysis."""
    query: str = Field(..., description="Search query to analyze for contradictions and similarities")
    max_contradictions: int = Field(50, description="Maximum contradictions to return")
    max_similarities: int = Field(20, description="Maximum similarity clusters to return")


@router.post("/analyze")
async def analyze_contradictions(
    body: ContradictionAnalyzeRequest,
    request: Request,
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """POST /api/v1/contradictions/analyze — Full contradiction & similarity analysis.

    Returns contradiction pairs (with type, severity, explanation, resolution suggestion),
    similarity clusters (with score, shared entities, consensus strength),
    and evidence landscape summary.

    Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6
    """
    from services.contradiction_detector import analyze_contradictions_and_similarities

    result = await analyze_contradictions_and_similarities(body.query)

    # Limit results
    result["contradictions"] = result["contradictions"][:body.max_contradictions]
    result["similarities"] = result["similarities"][:body.max_similarities]

    return _build_envelope(request, result)
