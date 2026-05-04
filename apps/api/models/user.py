"""User and Tenant SQLAlchemy Models."""

import uuid
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from core.db import Base
from core.pii_encryption import EncryptedString

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(EncryptedString(512), unique=True, index=True, nullable=False)  # §N-3: PII encrypted
    hashed_password = Column("password_hash", String, nullable=False)  # §56.1: password_hash
    display_name = Column(String, nullable=True)  # §56.1
    full_name = Column(String, nullable=True)  # kept for backward compat
    role = Column(String, default="collaborator")  # §55.2: owner|collaborator|viewer|admin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # §2.1
    last_login = Column(DateTime(timezone=True), nullable=True)  # §56.1
    
class Project(Base):
    """
    Project model linking workspaces to specific tenants (§56.1, Deep-Impl §2.2).
    """
    __tablename__ = "projects"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)  # §56.1: title
    name = Column(String, nullable=True)  # kept for backward compat
    description = Column(String, nullable=True)
    objective = Column(String, nullable=True)  # §2.2: project’s scientific objective
    scientific_domain = Column(String, nullable=True)  # §2.2: disease | target | compound | pathway | general
    status = Column(String, default="active")  # §2.2: active | archived | closed
    owner_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)  # §56.1: owner_id FK users.id
    user_id = Column(String, index=True, nullable=True)  # kept for backward compat
    target = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # §2.2
    archived_at = Column(DateTime(timezone=True), nullable=True)  # §2.2: when archived
    last_active = Column(DateTime(timezone=True), server_default=func.now())  # §56.1
