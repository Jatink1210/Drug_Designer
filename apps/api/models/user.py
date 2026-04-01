"""User and Tenant SQLAlchemy Models."""

import uuid
from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.sql import func
from core.db import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
class Project(Base):
    """
    Project model linking workspaces to specific tenants.
    (Legacy SQLite project_memory.py is kept separate for physical data tracking
    but this table serves for access control and metadata).
    """
    __tablename__ = "projects"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    target = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
