"""Embedding API routes."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel
from models.envelope import build_envelope
from routers.auth import get_current_user
import uuid

# Single-instance desktop mode uses in-memory job status.
# For distributed deployments, use Redis via Arq.

router = APIRouter(prefix="/api/v1/embeddings", tags=["embeddings"], dependencies=[Depends(get_current_user)])

# Single-instance desktop mode: in-memory job status. Use Redis for distributed.
JOB_STATUS = {}

from typing import List

class EmbedRequest(BaseModel):
    collections: List[str] = ["proteins", "molecules", "diseases"]
    limit_per_collection: int = 100

@router.post("/run")
async def run_embeddings(req: EmbedRequest, request: Request, bg_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    JOB_STATUS[job_id] = "pending"
    
    # Normally: await req.app.state.arq.enqueue_job('process_embeddings', job_id, request.collections)
    from worker import process_embeddings
    
    # Run in background to not block
    bg_tasks.add_task(process_embeddings, {}, job_id, req.collections, req.limit_per_collection)
    
    return build_envelope(request, {"job_id": job_id, "status": "queued"})

@router.get("/status/{job_id}")
async def get_status(job_id: str, request: Request):
    if job_id not in JOB_STATUS:
        raise HTTPException(status_code=404, detail="Job not found")
    return build_envelope(request, {"job_id": job_id, "status": JOB_STATUS[job_id]})

class SemanticSearchRequest(BaseModel):
    query: str
    target_collection: str
    limit: int = 10

@router.post("/semantic_search")
async def semantic_search(request: Request, req: SemanticSearchRequest = None):
    from services.embedding_service import EmbeddingService
    from models.alignment_model import AlignmentModel
    from core.qdrant_utils import similarity_search
    import torch
    
    embedder = EmbeddingService()
    aligner = AlignmentModel(target_dim=512)
    
    try:
        raw_emb = embedder.embed_text([req.query])
        with torch.no_grad():
            target_vec = aligner(raw_emb, modality="text").numpy()[0].tolist()
            
        results = await similarity_search(req.target_collection, target_vec, limit=req.limit)
        return build_envelope(request, {"query": req.query, "results": results})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
