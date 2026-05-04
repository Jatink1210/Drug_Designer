"""Document intelligence API routes for doc-tree ingestion and FTS retrieval."""

import os
import shutil
import uuid
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Request
from routers.auth import get_current_user
from pydantic import BaseModel

from services.doc_tree import DocTreeService
from config import settings
from models.envelope import build_envelope

router = APIRouter(prefix="/api/v1/docs", tags=["docs"], dependencies=[Depends(get_current_user)])

# Ensure upload directory exists
UPLOAD_DIR = os.path.join(settings.local_store_path, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


class DocSearchRequest(BaseModel):
    query: str
    limit: int = 5


@router.post("/ingest")
async def ingest_document(request: Request, file: UploadFile = File(...)) -> Dict[str, Any]:
    """Uploads a PDF and indexes its chunks using SQLite FTS5."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
        
    doc_id = f"doc_{uuid.uuid4().hex[:8]}"
    file_path = os.path.join(UPLOAD_DIR, f"{doc_id}.pdf")
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        result = DocTreeService.ingest_pdf(file_path, doc_id=doc_id)
        return build_envelope(request, {"status": "success", "result": result})
        
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Failed to ingest document: {str(e)}")


@router.post("/search")
async def search_documents(req: DocSearchRequest, request: Request) -> Dict[str, Any]:
    """Search ingested documents returning node paths and page anchors."""
    results = DocTreeService.search_nodes(req.query, limit=req.limit)
    return build_envelope(request, {"query": req.query, "count": len(results), "nodes": results})


@router.post("/clear")
async def clear_documents(request: Request) -> Dict[str, Any]:
    """Wipes the local FTS5 document index."""
    DocTreeService.clear_index()
    # Cleanup saved PDFs
    if os.path.exists(UPLOAD_DIR):
        shutil.rmtree(UPLOAD_DIR)
        os.makedirs(UPLOAD_DIR, exist_ok=True)
    return build_envelope(request, {"status": "success", "message": "Document index and files cleared."})
