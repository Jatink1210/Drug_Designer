"""Document intelligence API routes for doc-tree ingestion and FTS retrieval."""

import os
import shutil
import uuid
from typing import Any, Dict, List
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from services.doc_tree import DocTreeService
from config import settings

router = APIRouter(prefix="/api/docs", tags=["docs"])

# Ensure upload directory exists
UPLOAD_DIR = os.path.join(settings.local_store_path, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


class DocSearchRequest(BaseModel):
    query: str
    limit: int = 5


@router.post("/ingest")
async def ingest_document(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Uploads a PDF and indexes its chunks using SQLite FTS5."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
        
    doc_id = f"doc_{uuid.uuid4().hex[:8]}"
    file_path = os.path.join(UPLOAD_DIR, f"{doc_id}.pdf")
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        result = DocTreeService.ingest_pdf(file_path, doc_id=doc_id)
        return {"status": "success", "result": result}
        
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Failed to ingest document: {str(e)}")


@router.post("/search")
async def search_documents(req: DocSearchRequest) -> Dict[str, Any]:
    """Search ingested documents returning node paths and page anchors."""
    results = DocTreeService.search_nodes(req.query, limit=req.limit)
    return {"query": req.query, "count": len(results), "nodes": results}


@router.post("/clear")
async def clear_documents() -> Dict[str, Any]:
    """Wipes the local FTS5 document index."""
    DocTreeService.clear_index()
    # Cleanup saved PDFs
    if os.path.exists(UPLOAD_DIR):
        shutil.rmtree(UPLOAD_DIR)
        os.makedirs(UPLOAD_DIR, exist_ok=True)
    return {"status": "success", "message": "Document index and files cleared."}
