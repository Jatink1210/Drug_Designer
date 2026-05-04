"""Context Fabric Models (§39)

Drug Designer Subsystem 1: Manages the 3-tiered scientific project memory system.
Replaces the OpenViking repository dependencies natively.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

class ContextObject(BaseModel):
    """Memory Context wrapper (§39.1)."""
    object_id: str
    project_id: str
    tier: int = Field(..., description="1=Session, 2=Artifact, 3=HeavyArchive")
    object_type: str = Field(..., description="'evidence_bundle', 'disease_run', 'graph_snapshot'")
    created_at: datetime
    content: Any
    embedding_id: Optional[str] = None # Link to Qdrant if searchable

class RetrievalTrace(BaseModel):
    """Search diagnostic trace output (§39.1)."""
    query: str
    objects_retrieved: List[str]
    retrieval_time_ms: int
    compression_ratio: float
