"""
Document processing service that orchestrates PDF processing and citation parsing
"""
import os
import hashlib
import structlog
from typing import List, Dict
from sqlalchemy.orm import Session
import pdfplumber

from backend.pdf_processor import PDFProcessor
from backend.citation_parser import CitationParser, ParsedCitation
from backend.models import Document as DocumentModel, Citation as CitationModel
from backend.database import SessionLocal

logger = structlog.get_logger()

class DocumentProcessor:
    """
    Main document processing service following cursor/ai/extraction.pipeline.md
    """
    
    def __init__(self):
        self.pdf_processor = PDFProcessor()
        self.citation_parser = CitationParser()
        self.logger = logger.bind(component="document_processor")
    
    def _extract_document_title(self, file_path: str) -> str:
        """Extract document title from PDF content instead of filename"""
        try:
            # Extract first page text to find title
            with pdfplumber.open(file_path) as pdf:
                if pdf.pages:
                    first_page = pdf.pages[0]
                    text = first_page.extract_text() or ""
                    
                    # Look for title patterns in first page
                    lines = text.split('\n')
                    
                    # Legal document title patterns
                    title_patterns = [
                        # Look for lines that look like case titles
                        r'^[A-Z][A-Za-z\s&,\-\'\.]+(?:v\.|vs\.|versus)\s+[A-Z][A-Za-z\s&,\-\'\.]+$',
                        # Look for lines with "IN RE" or "IN THE MATTER OF"
                        r'^(?:IN RE|IN THE MATTER OF)\s+[A-Z][A-Za-z\s&,\-\'\.]+$',
                        # Look for lines with "UNITED STATES" or "STATE OF"
                        r'^(?:UNITED STATES|STATE OF|COMMONWEALTH OF)\s+[A-Z][A-Za-z\s&,\-\'\.]+$',
                        # Look for lines with "PEOPLE OF" or "CITY OF"
                        r'^(?:PEOPLE OF|CITY OF|COUNTY OF)\s+[A-Z][A-Za-z\s&,\-\'\.]+$'
                    ]
                    
                    import re
                    
                    # Try to find a title using patterns
                    for line in lines[:15]:  # Check first 15 lines
                        line = line.strip()
                        if line and len(line) > 15 and len(line) < 300:  # Reasonable title length
                            # Check if line matches any title pattern
                            for pattern in title_patterns:
                                if re.match(pattern, line, re.IGNORECASE):
                                    return line
                            
                            # Check if line looks like a title (starts with capital, has reasonable length)
                            if (line[0].isupper() and 
                                not line.startswith('Page') and 
                                not line.startswith('Date') and
                                not line.startswith('Docket') and
                                not line.startswith('Case') and
                                not line.startswith('No.') and
                                not line.startswith('Filed') and
                                not line.startswith('Decided')):
                                return line
                    
                    # Fallback: use first non-empty line that looks like a title
                    for line in lines:
                        line = line.strip()
                        if (line and len(line) > 10 and len(line) < 200 and 
                            line[0].isupper() and 
                            not any(line.startswith(x) for x in ['Page', 'Date', 'Docket', 'Case', 'No.', 'Filed', 'Decided', 'Before', 'Opinion'])):
                            return line[:150]  # Limit length
                    
                    # Last resort: use filename without extension
                    return os.path.basename(file_path).replace('.pdf', '')
                    
        except Exception as e:
            self.logger.warning("Failed to extract title from PDF", file_path=file_path, error=str(e))
            # Fallback to filename
            return os.path.basename(file_path).replace('.pdf', '')
    
    def process_document(self, document_id: str) -> Dict:
        """
        Process a document through the complete pipeline:
        1) PDF Text extraction
        2) Citation parsing
        3) Store citations in database
        4) Link candidates (basic implementation)
        
        Args:
            document_id: UUID of document to process
            
        Returns:
            Processing results summary
        """
        self.logger.info("Starting document processing", document_id=document_id)
        
        db = SessionLocal()
        try:
            # Get document from database
            document = db.query(DocumentModel).filter(DocumentModel.id == document_id).first()
            if not document:
                raise ValueError(f"Document not found: {document_id}")
            
            if not document.source_path or not os.path.exists(document.source_path):
                raise ValueError(f"PDF file not found: {document.source_path}")
            
            # Step 1: Extract PDF text
            pdf_result = self.pdf_processor.process_pdf(document.source_path)
            
            # Step 2: Parse citations
            parsed_citations = self.citation_parser.parse_citations_from_spans(
                pdf_result["citations"]
            )
            
            # Step 3: Store citations in database
            stored_citations = self._store_citations(db, document_id, parsed_citations)
            
            # Step 4: Basic candidate linking (simplified)
            linked_citations = self._link_citations(db, stored_citations)
            
            result = {
                "document_id": document_id,
                "pdf_pages": pdf_result["total_pages"],
                "pdf_chars": pdf_result["total_chars"],
                "citations_found": len(parsed_citations),
                "citations_stored": len(stored_citations),
                "citations_linked": linked_citations,
                "processing_status": "completed"
            }
            
            self.logger.info("Document processing completed", **result)
            return result
            
        except Exception as e:
            self.logger.error("Document processing failed", 
                            document_id=document_id, 
                            error=str(e))
            raise
        finally:
            db.close()
    
    def _store_citations(self, db: Session, from_doc_id: str, 
                        parsed_citations: List[ParsedCitation]) -> List[CitationModel]:
        """Store parsed citations in database"""
        stored_citations = []
        
        for parsed in parsed_citations:
            citation = CitationModel(
                from_doc_id=from_doc_id,
                raw_text=parsed.raw_text,
                normalized_key=parsed.normalized_key,
                reporter=parsed.reporter,
                volume=parsed.volume,
                page=parsed.page,
                year=parsed.year,
                page_number=parsed.page_number,
                span_start=parsed.span_start,
                span_end=parsed.span_end,
                confidence=parsed.confidence,
                resolution_notes="[]"  # Empty JSON array
            )
            
            db.add(citation)
            stored_citations.append(citation)
        
        db.commit()
        
        # Refresh to get IDs
        for citation in stored_citations:
            db.refresh(citation)
        
        self.logger.info("Citations stored", 
                        document_id=from_doc_id,
                        count=len(stored_citations))
        
        return stored_citations
    
    def _link_citations(self, db: Session, citations: List[CitationModel]) -> int:
        """
        Enhanced citation linking - process ALL possible connections between documents
        This is a one-time intensive process that will be stored in the database
        """
        linked_count = 0
        
        # Get all documents for cross-referencing
        all_documents = db.query(DocumentModel).all()
        self.logger.info("Processing citations across all documents", 
                        total_documents=len(all_documents),
                        total_citations=len(citations))
        
        for citation in citations:
            if not all([citation.reporter, citation.volume, citation.page]):
                continue  # Skip incomplete citations
            
            # Find ALL candidate documents with matching citations
            candidates = db.query(DocumentModel).join(CitationModel).filter(
                CitationModel.reporter == citation.reporter,
                CitationModel.volume == citation.volume,
                CitationModel.page == citation.page,
                CitationModel.from_doc_id != citation.from_doc_id  # Don't link to self
            ).all()
            
            if len(candidates) == 1:
                # Exact match - high confidence link
                citation.to_doc_id = candidates[0].id
                citation.confidence = min(citation.confidence + 0.3, 1.0)
                citation.resolution_notes = '["Exact reporter/volume/page match"]'
                linked_count += 1
                
            elif len(candidates) > 1:
                # Multiple candidates - create links to ALL matching documents
                # This creates a network of connections
                for candidate in candidates:
                    # Create additional citation records for multiple connections
                    if candidate.id != citation.to_doc_id:  # Avoid duplicates
                        additional_citation = CitationModel(
                            from_doc_id=citation.from_doc_id,
                            to_doc_id=candidate.id,
                            raw_text=citation.raw_text,
                            normalized_key=citation.normalized_key,
                            reporter=citation.reporter,
                            volume=citation.volume,
                            page=citation.page,
                            year=citation.year,
                            page_number=citation.page_number,
                            span_start=citation.span_start,
                            span_end=citation.span_end,
                            confidence=max(citation.confidence - 0.2, 0.1),
                            resolution_notes=f'["Multiple candidates ({len(candidates)}), network connection"]'
                        )
                        db.add(additional_citation)
                        linked_count += 1
                
                # Set primary link to first candidate
                citation.to_doc_id = candidates[0].id
                citation.confidence = max(citation.confidence - 0.2, 0.1)
                citation.resolution_notes = f'["Multiple candidates ({len(candidates)}), primary connection"]'
                linked_count += 1
            
            # If no candidates, try fuzzy matching for potential connections
            if not candidates:
                fuzzy_candidates = self._find_fuzzy_citations(db, citation)
                if fuzzy_candidates:
                    # Create lower confidence connections for fuzzy matches
                    for candidate in fuzzy_candidates:
                        fuzzy_citation = CitationModel(
                            from_doc_id=citation.from_doc_id,
                            to_doc_id=candidate.id,
                            raw_text=citation.raw_text,
                            normalized_key=citation.normalized_key,
                            reporter=citation.reporter,
                            volume=citation.volume,
                            page=citation.page,
                            year=citation.year,
                            page_number=citation.page_number,
                            span_start=citation.span_start,
                            span_end=citation.span_end,
                            confidence=0.3,  # Lower confidence for fuzzy matches
                            resolution_notes='["Fuzzy citation match - potential connection"]'
                        )
                        db.add(fuzzy_citation)
                        linked_count += 1
        
        db.commit()
        
        self.logger.info("Enhanced citation linking completed", 
                        total_links_created=linked_count,
                        documents_processed=len(all_documents))
        return linked_count
    
    def _find_fuzzy_citations(self, db: Session, citation: CitationModel) -> List[DocumentModel]:
        """Find potential fuzzy matches for citations"""
        candidates = []
        
        if citation.reporter:
            # Look for documents with same reporter but different volume/page
            similar_citations = db.query(DocumentModel).join(CitationModel).filter(
                CitationModel.reporter == citation.reporter,
                CitationModel.from_doc_id != citation.from_doc_id
            ).all()
            
            for doc in similar_citations:
                # Check if this document has citations that might be related
                doc_citations = db.query(CitationModel).filter(
                    CitationModel.from_doc_id == doc.id
                ).all()
                
                for doc_citation in doc_citations:
                    # If both citations reference the same case type, create connection
                    if (doc_citation.reporter == citation.reporter and 
                        doc_citation.volume and citation.volume and
                        abs(doc_citation.volume - citation.volume) <= 10):  # Within 10 volumes
                        candidates.append(doc)
                        break
        
        return list(set(candidates))  # Remove duplicates
    
    def process_all_documents(self) -> Dict:
        """Process all documents that haven't been processed yet"""
        db = SessionLocal()
        try:
            # First, add any new PDFs from the data/pdfs folder
            pdf_storage_path = os.getenv("PDF_STORAGE_PATH", "./data/pdfs")
            if os.path.exists(pdf_storage_path):
                pdf_files = [f for f in os.listdir(pdf_storage_path) if f.lower().endswith('.pdf')]
                
                for pdf_file in pdf_files:
                    file_path = os.path.join(pdf_storage_path, pdf_file)
                    
                    # Check if already in database
                    with open(file_path, "rb") as f:
                        content = f.read()
                        fingerprint = hashlib.sha256(content).hexdigest()
                    
                    existing_doc = db.query(DocumentModel).filter(DocumentModel.fingerprint == fingerprint).first()
                    if not existing_doc:
                        # Add new PDF to database
                        document = DocumentModel(
                            title=self._extract_document_title(file_path),
                            fingerprint=fingerprint,
                            source_path=file_path
                        )
                        db.add(document)
                        db.commit()
                        db.refresh(document)
                        self.logger.info("Added new PDF to database", filename=pdf_file, doc_id=document.id)
            
            # Find documents without citations
            unprocessed_docs = db.query(DocumentModel).filter(
                ~DocumentModel.citations_from.any()
            ).all()
            
            results = []
            for doc in unprocessed_docs:
                try:
                    result = self.process_document(doc.id)
                    results.append(result)
                except Exception as e:
                    self.logger.error("Failed to process document", 
                                    doc_id=doc.id, error=str(e))
                    results.append({
                        "document_id": doc.id,
                        "processing_status": "failed",
                        "error": str(e)
                    })
            
            summary = {
                "total_documents": len(unprocessed_docs),
                "processed": len([r for r in results if r.get("processing_status") == "completed"]),
                "failed": len([r for r in results if r.get("processing_status") == "failed"]),
                "results": results
            }
            
            self.logger.info("Batch processing completed", **summary)
            return summary
            
        finally:
            db.close()

