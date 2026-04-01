"""Search API route."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel, Field

from services.search_engine import execute_search

router = APIRouter(prefix="/api", tags=["search"])


class SearchRequest(BaseModel):
    query: str
    mode: str = "auto"
    filters: Dict[str, Any] = Field(default_factory=dict)
    limit: int = 20
    strict_evidence: bool = False


@router.post("/search")
async def search(request: SearchRequest) -> dict:
    """Multi-source biomedical search with categorized table results."""
    result = await execute_search(
        query=request.query,
        mode=request.mode,
        filters=request.filters,
        limit=request.limit,
        strict_evidence=request.strict_evidence,
    )
    return result.dict()
