"""
FastAPI main application following cursor/eng/api.contract.md
"""
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import hashlib
import structlog

from backend.database import get_db, create_tables
from backend.models import Document as DocumentModel, Citation as CitationModel
from backend.schemas import (
    DocumentsResponse, DocumentDetailResponse, GraphResponse,
    Document, Citation, GraphNode, GraphEdge
)
from backend.document_processor import DocumentProcessor

# Configure structured logging
logger = structlog.get_logger()

# Create FastAPI app
app = FastAPI(
    title="Legal Citation Graph API",
    description="AI-assisted legal citation graph using eyecite",
    version="0.1.0"
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create tables on startup
@app.on_event("startup")
async def startup_event():
    create_tables()
    logger.info("Database tables created")
    
    # Automatically process existing PDFs in the data/pdfs folder
    await process_existing_pdfs()

async def process_existing_pdfs():
    """Automatically process existing PDFs in the data/pdfs folder"""
    try:
        pdf_storage_path = os.getenv("PDF_STORAGE_PATH", "./data/pdfs")
        if not os.path.exists(pdf_storage_path):
            logger.warning("PDF storage path does not exist", path=pdf_storage_path)
            return
        
        # Find all PDF files
        pdf_files = [f for f in os.listdir(pdf_storage_path) if f.lower().endswith('.pdf')]
        logger.info("Found existing PDFs", count=len(pdf_files))
        
        if not pdf_files:
            logger.info("No PDF files found to process")
            return
        
        # Process PDFs using DocumentProcessor
        try:
            processor = DocumentProcessor()
            result = processor.process_all_documents()
            logger.info("Processed existing PDFs", result=result)
        except Exception as e:
            logger.error("Failed to process PDFs through pipeline", error=str(e))
        
    except Exception as e:
        logger.error("Failed to process existing PDFs", error=str(e))

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# API endpoints following cursor/eng/api.contract.md

@app.get("/v1/documents", response_model=DocumentsResponse)
async def get_documents(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get list of documents"""
    documents = db.query(DocumentModel).offset(skip).limit(limit).all()
    total = db.query(DocumentModel).count()
    
    return DocumentsResponse(
        items=[Document.model_validate(doc) for doc in documents],
        total=total
    )

@app.get("/v1/documents/{doc_id}", response_model=DocumentDetailResponse)
async def get_document_detail(
    doc_id: str,
    db: Session = Depends(get_db)
):
    """Get document with its citations"""
    document = db.query(DocumentModel).filter(DocumentModel.id == doc_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    citations = db.query(CitationModel).filter(CitationModel.from_doc_id == doc_id).all()
    
    return DocumentDetailResponse(
        document=Document.model_validate(document),
        citations=[Citation.model_validate(citation) for citation in citations]
    )

@app.get("/v1/documents/{doc_id}/pdf")
async def get_document_pdf(
    doc_id: str,
    db: Session = Depends(get_db)
):
    """Stream PDF bytes"""
    document = db.query(DocumentModel).filter(DocumentModel.id == doc_id).first()
    if not document or not document.source_path:
        raise HTTPException(status_code=404, detail="PDF not found")
    
    if not os.path.exists(document.source_path):
        raise HTTPException(status_code=404, detail="PDF file not found on disk")
    
    def iter_file(file_path: str):
        with open(file_path, "rb") as file_like:
            yield from file_like
    
    return StreamingResponse(
        iter_file(document.source_path),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={os.path.basename(document.source_path)}"}
    )

@app.get("/v1/graph", response_model=GraphResponse)
async def get_citation_graph(
    min_confidence: float = Query(0.7, ge=0.0, le=1.0),
    db: Session = Depends(get_db)
):
    """Get citation graph with confidence threshold"""
    # Get all documents
    documents = db.query(DocumentModel).all()
    nodes = [
        GraphNode(
            id=doc.id,
            label=doc.title,
            meta={
                "court": doc.court,
                "year": doc.year,
                "docket": doc.docket
            }
        )
        for doc in documents
    ]
    
    # Get citations above confidence threshold
    citations = db.query(CitationModel).filter(
        CitationModel.confidence >= min_confidence,
        CitationModel.to_doc_id.isnot(None)
    ).all()
    
    edges = [
        GraphEdge(
            id=citation.id,
            source=citation.from_doc_id,
            target=citation.to_doc_id,
            confidence=citation.confidence
        )
        for citation in citations
    ]
    
    return GraphResponse(nodes=nodes, edges=edges)

# Upload endpoint removed - system now automatically processes existing PDFs

@app.post("/v1/process")
async def process_documents():
    """Process all unprocessed documents through citation parsing pipeline"""
    processor = DocumentProcessor()
    try:
        result = processor.process_all_documents()
        return result
    except Exception as e:
        logger.error("Document processing failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@app.post("/v1/process/{doc_id}")
async def process_single_document(
    doc_id: str,
    db: Session = Depends(get_db)
):
    """Process a single document through citation parsing pipeline"""
    # Verify document exists
    document = db.query(DocumentModel).filter(DocumentModel.id == doc_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    processor = DocumentProcessor()
    try:
        result = processor.process_document(doc_id)
        return result
    except Exception as e:
        logger.error("Document processing failed", doc_id=doc_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@app.post("/v1/documents/{doc_id}/update-title")
async def update_document_title(
    doc_id: str,
    db: Session = Depends(get_db)
):
    """Update document title using improved extraction logic"""
    document = db.query(DocumentModel).filter(DocumentModel.id == doc_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not document.source_path or not os.path.exists(document.source_path):
        raise HTTPException(status_code=404, detail="PDF file not found on disk")
    
    try:
        processor = DocumentProcessor()
        new_title = processor._extract_document_title(document.source_path)
        
        if new_title and new_title != document.title:
            document.title = new_title
            db.commit()
            logger.info("Updated document title", doc_id=doc_id, old_title=document.title, new_title=new_title)
            return {"message": "Title updated", "old_title": document.title, "new_title": new_title}
        else:
            return {"message": "Title unchanged", "title": document.title}
            
    except Exception as e:
        logger.error("Failed to update document title", doc_id=doc_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Title update failed: {str(e)}")

@app.post("/v1/documents/update-all-titles")
async def update_all_document_titles(
    db: Session = Depends(get_db)
):
    """Update titles for all documents using improved extraction logic"""
    documents = db.query(DocumentModel).all()
    updated_count = 0
    
    try:
        processor = DocumentProcessor()
        
        for document in documents:
            if document.source_path and os.path.exists(document.source_path):
                new_title = processor._extract_document_title(document.source_path)
                if new_title and new_title != document.title:
                    document.title = new_title
                    updated_count += 1
        
        db.commit()
        logger.info("Updated document titles", updated_count=updated_count, total_documents=len(documents))
        return {"message": f"Updated {updated_count} out of {len(documents)} document titles"}
        
    except Exception as e:
        logger.error("Failed to update document titles", error=str(e))
        raise HTTPException(status_code=500, detail=f"Title update failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
