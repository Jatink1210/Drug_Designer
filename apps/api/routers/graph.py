"""Graph API routes — works with embedded (NetworkX) or full (Neo4j) backend."""

from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.graph_service import GraphService
from services.graph_store import get_graph_store

router = APIRouter(prefix="/api/graph", tags=["graph"])


class NeighborhoodRequest(BaseModel):
    entity_id: str
    depth: int = 1


class ShortestPathRequest(BaseModel):
    source_id: str
    target_id: str


async def startup_graph_constraints():
    """Run graph constraint setup. Called from the app lifespan handler."""
    gs = GraphService()
    try:
        await gs.setup_constraints()
    except Exception as e:
        print(f"Skipping graph constraints setup: {e}")
    finally:
        await gs.close()


@router.get("/stats")
async def get_graph_stats() -> Dict[str, Any]:
    store = get_graph_store()
    return store.stats()


@router.get("/sample")
async def get_graph_sample(limit: int = 50) -> Dict[str, Any]:
    store = get_graph_store()
    return store.sample(limit=limit)


@router.post("/neighborhood")
async def get_neighborhood(req: NeighborhoodRequest) -> Dict[str, Any]:
    gs = GraphService()
    try:
        graph_data = await gs.get_neighborhood(req.entity_id, req.depth)
        return graph_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await gs.close()


@router.post("/shortest_path")
async def get_shortest_path(req: ShortestPathRequest) -> Dict[str, Any]:
    gs = GraphService()
    try:
        graph_data = await gs.get_shortest_path(req.source_id, req.target_id)
        return graph_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await gs.close()

@router.post("/viking_walk")
async def execute_viking_walk(req: NeighborhoodRequest) -> Dict[str, Any]:
    """Execute OpenViking topological walks for implicit therapeutic connections."""
    from services.graph.viking_walker import VikingGraphWalker
    walker = VikingGraphWalker()
    walks = walker.compute_deep_random_walks(req.entity_id, req.depth)
    return {"status": "success", "engine": "OpenViking_Equivalent", "random_walks": walks}
