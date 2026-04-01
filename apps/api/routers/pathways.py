"""Pathway search & detail routes — delegates to Reactome connector."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/pathways", tags=["pathways"])


class PathwaySearchRequest(BaseModel):
    query: str
    source: str = "reactome"
    limit: int = 20


_SUPPORTED_SOURCES = {"reactome"}


@router.post("/search")
async def search_pathways(req: PathwaySearchRequest) -> List[Dict[str, Any]]:
    if req.source not in _SUPPORTED_SOURCES:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported pathway source '{req.source}'. "
                   f"Supported: {sorted(_SUPPORTED_SOURCES)}",
        )
    from connectors.reactome import ReactomeConnector
    conn = ReactomeConnector()
    return await conn.search(req.query, limit=req.limit)


@router.get("/{pathway_id}")
async def get_pathway(pathway_id: str) -> Dict[str, Any]:
    from connectors.reactome import ReactomeConnector
    conn = ReactomeConnector()
    result = await conn.fetch_by_id(pathway_id)
    if not result:
        raise HTTPException(status_code=404, detail="Pathway not found")
    return result
