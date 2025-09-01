"""
Pydantic schemas for API requests/responses following cursor/eng/api.contract.md
"""
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# Document schemas
class DocumentBase(BaseModel):
    title: str
    court: Optional[str] = None
    year: Optional[int] = None
    docket: Optional[str] = None

class DocumentCreate(DocumentBase):
    pass

class Document(DocumentBase):
    id: str
    fingerprint: str
    source_path: Optional[str] = None
    source_url: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

# Citation schemas
class CitationBase(BaseModel):
    raw_text: str
    normalized_key: str
    reporter: Optional[str] = None
    volume: Optional[int] = None
    page: Optional[int] = None
    year: Optional[int] = None
    page_number: Optional[int] = None
    span_start: Optional[int] = None
    span_end: Optional[int] = None
    confidence: float = 0.0
    resolution_notes: Optional[str] = None

class CitationCreate(CitationBase):
    from_doc_id: str
    to_doc_id: Optional[str] = None

class Citation(CitationBase):
    id: str
    from_doc_id: str
    to_doc_id: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

# API response schemas following cursor/eng/api.contract.md
class DocumentsResponse(BaseModel):
    items: List[Document]
    total: int

class DocumentDetailResponse(BaseModel):
    document: Document
    citations: List[Citation]

# Graph schemas
class GraphNode(BaseModel):
    id: str
    label: str
    meta: dict

class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    confidence: float

class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]

# Upload response
class IngestResponse(BaseModel):
    document_ids: List[str]

