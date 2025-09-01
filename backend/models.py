"""
Data models following cursor/eng/data.models.md specification
"""
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

Base = declarative_base()

class Document(Base):
    """Document model as specified in data.models.md"""
    __tablename__ = "documents"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    fingerprint = Column(String, nullable=False, unique=True)  # hash of content
    source_path = Column(String, nullable=True)  # local file path
    source_url = Column(String, nullable=True)   # optional URL
    court = Column(String, nullable=True)
    year = Column(Integer, nullable=True)
    docket = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    citations_from = relationship("Citation", foreign_keys="Citation.from_doc_id", back_populates="from_document")
    citations_to = relationship("Citation", foreign_keys="Citation.to_doc_id", back_populates="to_document")

class Citation(Base):
    """Citation model as specified in data.models.md"""
    __tablename__ = "citations"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    from_doc_id = Column(String, ForeignKey("documents.id"), nullable=False)
    to_doc_id = Column(String, ForeignKey("documents.id"), nullable=True)  # nullable for unresolved citations
    
    # Citation text and normalization
    raw_text = Column(Text, nullable=False)
    normalized_key = Column(String, nullable=False, index=True)
    
    # Citation components
    reporter = Column(String, nullable=True)
    volume = Column(Integer, nullable=True)
    page = Column(Integer, nullable=True)
    year = Column(Integer, nullable=True)
    
    # Location in source document
    page_number = Column(Integer, nullable=True)
    span_start = Column(Integer, nullable=True)
    span_end = Column(Integer, nullable=True)
    
    # Resolution metadata
    confidence = Column(Float, nullable=False, default=0.0)  # 0.0 to 1.0
    resolution_notes = Column(Text, nullable=True)  # JSON array as text
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    from_document = relationship("Document", foreign_keys=[from_doc_id], back_populates="citations_from")
    to_document = relationship("Document", foreign_keys=[to_doc_id], back_populates="citations_to")

