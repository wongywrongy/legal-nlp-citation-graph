"""
Citation parsing service for extracted citation spans
"""
import structlog
from typing import List, Dict, Any
from dataclasses import dataclass
import re

logger = structlog.get_logger()

@dataclass
class ParsedCitation:
    """Parsed citation data structure"""
    raw_text: str
    normalized_key: str
    reporter: str = None
    volume: int = None
    page: int = None
    year: int = None
    page_number: int = None
    span_start: int = None
    span_end: int = None
    confidence: float = 0.0

class CitationParser:
    """Citation parsing service"""
    
    def __init__(self):
        self.logger = logger.bind(component="citation_parser")
    
    def parse_citations_from_spans(self, citation_spans: List[Dict]) -> List[ParsedCitation]:
        """
        Parse citation spans into structured citation objects
        
        Args:
            citation_spans: List of citation span dictionaries from PDF processor
            
        Returns:
            List of parsed citation objects
        """
        parsed_citations = []
        
        for span in citation_spans:
            try:
                parsed = self._parse_single_citation(span)
                if parsed:
                    parsed_citations.append(parsed)
            except Exception as e:
                self.logger.warning("Failed to parse citation span", 
                                  span=span, error=str(e))
                continue
        
        self.logger.info("Citation parsing completed", 
                        input_spans=len(citation_spans),
                        parsed_citations=len(parsed_citations))
        
        return parsed_citations
    
    def _parse_single_citation(self, span: Dict) -> ParsedCitation:
        """Parse a single citation span"""
        raw_text = span.get("raw_text", "")
        page_number = span.get("page_number", 0)
        span_start = span.get("span_start", 0)
        span_end = span.get("span_end", 0)
        confidence = span.get("confidence", 0.0)
        
        # Extract citation components using regex
        citation_data = self._extract_citation_components(raw_text)
        
        # Create normalized key
        normalized_key = self._create_normalized_key(citation_data)
        
        return ParsedCitation(
            raw_text=raw_text,
            normalized_key=normalized_key,
            reporter=citation_data.get("reporter"),
            volume=citation_data.get("volume"),
            page=citation_data.get("page"),
            year=citation_data.get("year"),
            page_number=page_number,
            span_start=span_start,
            span_end=span_end,
            confidence=confidence
        )
    
    def _extract_citation_components(self, text: str) -> Dict[str, Any]:
        """Extract citation components from raw text"""
        components = {}
        
        # U.S. Supreme Court: 123 U.S. 456
        us_match = re.match(r'(\d+)\s+U\.S\.\s+(\d+)', text)
        if us_match:
            components["volume"] = int(us_match.group(1))
            components["reporter"] = "U.S."
            components["page"] = int(us_match.group(2))
            return components
        
        # Federal Reporter: 123 F.2d 456
        fed_match = re.match(r'(\d+)\s+F\.(?:2d|3d|4d)?\s+(\d+)', text)
        if fed_match:
            components["volume"] = int(fed_match.group(1))
            components["reporter"] = "F."
            components["page"] = int(fed_match.group(2))
            return components
        
        # State cases: 123 N.E.2d 456
        state_match = re.match(r'(\d+)\s+([A-Z]{2})\.?\s+(?:2d|3d)?\s+(\d+)', text)
        if state_match:
            components["volume"] = int(state_match.group(1))
            components["reporter"] = state_match.group(2)
            components["page"] = int(state_match.group(3))
            return components
        
        # Generic pattern: 123 Reporter 456
        generic_match = re.match(r'(\d+)\s+([A-Za-z]+)\.?\s+(\d+)', text)
        if generic_match:
            components["volume"] = int(generic_match.group(1))
            components["reporter"] = generic_match.group(2)
            components["page"] = int(generic_match.group(3))
            return components
        
        return components
    
    def _create_normalized_key(self, components: Dict[str, Any]) -> str:
        """Create a normalized key for the citation"""
        parts = []
        
        if components.get("volume"):
            parts.append(str(components["volume"]))
        
        if components.get("reporter"):
            parts.append(components["reporter"])
        
        if components.get("page"):
            parts.append(str(components["page"]))
        
        return " ".join(parts) if parts else "unknown"
    
    def parse_citations(self, text: str) -> List[ParsedCitation]:
        """
        Parse citations from raw text (fallback method)
        
        Args:
            text: Raw text to search for citations
            
        Returns:
            List of parsed citations
        """
        # This is a simplified fallback - in production you'd use eyecite
        citations = []
        
        # Basic citation patterns
        patterns = [
            r'(\d+)\s+U\.S\.\s+(\d+)',
            r'(\d+)\s+F\.(?:2d|3d|4d)?\s+(\d+)',
            r'(\d+)\s+[A-Z]{2}\.?\s+(?:2d|3d)?\s+(\d+)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                citation = ParsedCitation(
                    raw_text=match.group(0),
                    normalized_key=match.group(0),
                    confidence=0.6
                )
                citations.append(citation)
        
        return citations

