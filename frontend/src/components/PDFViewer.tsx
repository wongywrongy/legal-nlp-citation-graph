"use client";

import React, { useState } from 'react';
import { FileText, ExternalLink, Calendar, User, Hash, ArrowLeft, Eye, Download } from 'lucide-react';

interface Citation {
  id: string;
  raw_text: string;
  normalized_key: string;
  reporter?: string;
  volume?: number;
  page?: number;
  year?: number;
  page_number?: number;
  confidence: number;
  resolution_notes?: string;
}

interface DocumentData {
  id: string;
  title: string;
  fingerprint: string;
  source_path?: string;
  source_url?: string;
  court?: string;
  year?: number;
  docket?: string;
  created_at: string;
}

interface PDFViewerProps {
  document: DocumentData;
  citations: Citation[];
  onClose: () => void;
}

const PDFViewer: React.FC<PDFViewerProps> = ({ document, citations, onClose }) => {
  const [currentPage, setCurrentPage] = useState<number>(1);

  const getPageCitations = (pageNum: number) => {
    return citations.filter(citation => citation.page_number === pageNum);
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-600';
    if (confidence >= 0.6) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getConfidenceLabel = (confidence: number) => {
    if (confidence >= 0.8) return 'High';
    if (confidence >= 0.6) return 'Medium';
    return 'Low';
  };

  const pdfUrl = `/api/documents/${document.id}/pdf`;

  return (
    <div className="fixed inset-0 bg-gray-900 bg-opacity-75 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-2xl w-full h-full max-w-7xl mx-4 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b bg-gray-50">
          <div className="flex items-center space-x-4">
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-200 rounded-md transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h2 className="text-xl font-bold text-gray-900">{document.title}</h2>
              <p className="text-sm text-gray-600">PDF Document Viewer</p>
            </div>
          </div>
          
          {/* Actions */}
          <div className="flex items-center space-x-2">
            <a
              href={pdfUrl}
              download={`${document.title}.pdf`}
              className="p-2 hover:bg-gray-200 rounded-md transition-colors text-gray-600 hover:text-gray-900"
              title="Download PDF"
            >
              <Download className="w-5 h-5" />
            </a>
            <a
              href={pdfUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="p-2 hover:bg-gray-200 rounded-md transition-colors text-gray-600 hover:text-gray-900"
              title="Open in new tab"
            >
              <Eye className="w-5 h-5" />
            </a>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 flex overflow-hidden">
          {/* PDF Viewer */}
          <div className="flex-1 bg-gray-100 overflow-hidden">
            <iframe
              src={`${pdfUrl}#toolbar=1&navpanes=1&scrollbar=1`}
              className="w-full h-full border-0"
              title={`PDF Viewer - ${document.title}`}
            />
          </div>

          {/* Analysis Sidebar */}
          <div className="w-80 bg-white border-l overflow-y-auto">
            <div className="p-4">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Document Analysis</h3>
              
              {/* Document Metadata */}
              <div className="mb-6">
                <h4 className="text-sm font-medium text-gray-700 mb-3">Document Information</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex items-center space-x-2">
                    <FileText className="w-4 h-4 text-gray-400" />
                    <span className="text-gray-600">Title:</span>
                    <span className="font-medium">{document.title}</span>
                  </div>
                  
                  {document.court && (
                    <div className="flex items-center space-x-2">
                      <ExternalLink className="w-4 h-4 text-gray-400" />
                      <span className="text-gray-600">Court:</span>
                      <span className="font-medium">{document.court}</span>
                    </div>
                  )}
                  
                  {document.year && (
                    <div className="flex items-center space-x-2">
                      <Calendar className="w-4 h-4 text-gray-400" />
                      <span className="text-gray-600">Year:</span>
                      <span className="font-medium">{document.year}</span>
                    </div>
                  )}
                  
                  {document.docket && (
                    <div className="flex items-center space-x-2">
                      <Hash className="w-4 h-4 text-gray-400" />
                      <span className="text-gray-600">Docket:</span>
                      <span className="font-medium">{document.docket}</span>
                    </div>
                  )}
                  
                  <div className="flex items-center space-x-2">
                    <User className="w-4 h-4 text-gray-400" />
                    <span className="text-gray-600">ID:</span>
                    <span className="font-mono text-xs">{document.fingerprint.substring(0, 8)}...</span>
                  </div>
                </div>
              </div>

              {/* Citations Summary */}
              <div className="mb-6">
                <h4 className="text-sm font-medium text-gray-700 mb-3">
                  Citations Found ({citations.length})
                </h4>
                
                {citations.length === 0 ? (
                  <p className="text-sm text-gray-500">No citations found in this document.</p>
                ) : (
                  <div className="space-y-3">
                    {citations.slice(0, 10).map((citation) => (
                      <div key={citation.id} className="p-3 bg-gray-50 rounded-md">
                        <div className="flex items-start justify-between mb-2">
                          <span className="text-sm font-medium text-gray-900">
                            {citation.raw_text}
                          </span>
                          <span className={`text-xs font-medium px-2 py-1 rounded-full ${getConfidenceColor(citation.confidence)} bg-opacity-10 ${getConfidenceColor(citation.confidence).replace('text-', 'bg-')}`}>
                            {getConfidenceLabel(citation.confidence)}
                          </span>
                        </div>
                        
                        <div className="text-xs text-gray-600 space-y-1">
                          {citation.reporter && (
                            <div>Reporter: {citation.reporter}</div>
                          )}
                          {citation.volume && (
                            <div>Volume: {citation.volume}</div>
                          )}
                          {citation.page && (
                            <div>Page: {citation.page}</div>
                          )}
                          {citation.page_number && (
                            <div>Found on page: {citation.page_number}</div>
                          )}
                        </div>
                      </div>
                    ))}
                    
                    {citations.length > 10 && (
                      <p className="text-xs text-gray-500 text-center">
                        +{citations.length - 10} more citations
                      </p>
                    )}
                  </div>
                )}
              </div>

              {/* Page-specific Citations */}
              {getPageCitations(currentPage).length > 0 && (
                <div className="mb-6">
                  <h4 className="text-sm font-medium text-gray-700 mb-3">
                    Citations on Page {currentPage}
                  </h4>
                  <div className="space-y-2">
                    {getPageCitations(currentPage).map((citation) => (
                      <div key={citation.id} className="p-2 bg-blue-50 rounded border-l-4 border-blue-400">
                        <div className="text-sm font-medium text-blue-900">
                          {citation.raw_text}
                        </div>
                        <div className="text-xs text-blue-700 mt-1">
                          Confidence: {Math.round(citation.confidence * 100)}%
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Page Navigation Help */}
              <div className="mt-6 p-3 bg-blue-50 rounded-md">
                <h4 className="text-sm font-medium text-blue-900 mb-2">Navigation Tips</h4>
                <ul className="text-xs text-blue-800 space-y-1">
                  <li>• Use browser's built-in PDF controls</li>
                  <li>• Press Ctrl+F to search within the PDF</li>
                  <li>• Use mouse wheel to zoom in/out</li>
                  <li>• Right-click for additional PDF options</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PDFViewer;
