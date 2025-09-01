'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, FileText, ExternalLink, Calendar, Building, Hash, Download } from 'lucide-react';
import { documentApi, Document, Citation } from '@/lib/api';

export default function DocumentDetailPage() {
  const params = useParams();
  const docId = params.id as string;
  
  const [document, setDocument] = useState<Document | null>(null);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (docId) {
      loadDocument();
    }
  }, [docId]);

  const loadDocument = async () => {
    try {
      const response = await documentApi.getDocument(docId);
      setDocument(response.document);
      setCitations(response.citations);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load document');
    } finally {
      setLoading(false);
    }
  };

  const getConfidenceBadge = (confidence: number) => {
    if (confidence >= 0.9) {
      return <span className="px-2 py-1 text-xs bg-green-100 text-green-800 rounded-full">High</span>;
    } else if (confidence >= 0.7) {
      return <span className="px-2 py-1 text-xs bg-yellow-100 text-yellow-800 rounded-full">Medium</span>;
    } else {
      return <span className="px-2 py-1 text-xs bg-red-100 text-red-800 rounded-full">Low</span>;
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const groupCitationsByPage = (citations: Citation[]) => {
    const grouped: { [page: number]: Citation[] } = {};
    citations.forEach(citation => {
      const page = citation.page_number || 0;
      if (!grouped[page]) {
        grouped[page] = [];
      }
      grouped[page].push(citation);
    });
    return grouped;
  };

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-center">Loading document...</div>
      </div>
    );
  }

  if (error || !document) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <div className="text-red-700">Error: {error || 'Document not found'}</div>
          <Link href="/documents" className="text-red-600 hover:text-red-800 underline mt-2 inline-block">
            ← Back to Documents
          </Link>
        </div>
      </div>
    );
  }

  const groupedCitations = groupCitationsByPage(citations);
  const linkedCitations = citations.filter(c => c.to_doc_id);
  const pdfUrl = `http://localhost:8000/v1/documents/${docId}/pdf`;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center mb-4">
            <Link
              href="/documents"
              className="flex items-center text-gray-600 hover:text-gray-900 mr-4"
            >
              <ArrowLeft className="w-4 h-4 mr-1" />
              Back to Documents
            </Link>
          </div>
          
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <h1 className="text-3xl font-bold text-gray-900 mb-4">{document.title}</h1>
              
              {/* Document metadata */}
              <div className="flex flex-wrap gap-4 text-sm text-gray-600">
                {document.court && (
                  <div className="flex items-center">
                    <Building className="w-4 h-4 mr-1" />
                    <span>{document.court}</span>
                  </div>
                )}
                
                {document.year && (
                  <div className="flex items-center">
                    <Calendar className="w-4 h-4 mr-1" />
                    <span>{document.year}</span>
                  </div>
                )}
                
                {document.docket && (
                  <div className="flex items-center">
                    <Hash className="w-4 h-4 mr-1" />
                    <span>{document.docket}</span>
                  </div>
                )}
                
                <div className="flex items-center">
                  <Calendar className="w-4 h-4 mr-1" />
                  <span>Added {formatDate(document.created_at)}</span>
                </div>
              </div>
            </div>
            
            <div className="flex space-x-2 ml-6">
              <a
                href={pdfUrl}
                download={`${document.title}.pdf`}
                className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 flex items-center transition-colors"
              >
                <Download className="w-4 h-4 mr-2" />
                Download PDF
              </a>
            </div>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* PDF Viewer - Takes up most of the space */}
          <div className="lg:col-span-3">
            <div className="bg-white rounded-lg shadow-md p-4">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold">Document PDF</h2>
                <a
                  href={pdfUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:text-blue-800 text-sm"
                >
                  Open in new tab
                </a>
              </div>
              
              {/* PDF iframe */}
              <div className="w-full h-[800px] bg-gray-100 rounded-lg overflow-hidden">
                <iframe
                  src={`${pdfUrl}#toolbar=1&navpanes=1&scrollbar=1`}
                  className="w-full h-full border-0"
                  title={`PDF Viewer - ${document.title}`}
                />
              </div>
            </div>
          </div>

          {/* Analysis Sidebar */}
          <div className="lg:col-span-1">
            {/* Citations Summary */}
            <div className="bg-white rounded-lg shadow-md p-6 mb-6">
              <h2 className="text-xl font-semibold mb-4">Citation Summary</h2>
              
              <div className="grid grid-cols-2 gap-4 text-center">
                <div>
                  <div className="text-2xl font-bold text-blue-600">{citations.length}</div>
                  <div className="text-sm text-gray-600">Total Citations</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-green-600">{linkedCitations.length}</div>
                  <div className="text-sm text-gray-600">Linked</div>
                </div>
              </div>
              
              {citations.length > 0 && (
                <div className="mt-4 pt-4 border-t">
                  <div className="text-sm text-gray-600">
                    <div>Average Confidence: {(citations.reduce((sum, c) => sum + c.confidence, 0) / citations.length * 100).toFixed(0)}%</div>
                    <div>Pages with Citations: {Object.keys(groupedCitations).length}</div>
                  </div>
                </div>
              )}
            </div>

            {/* Document Info */}
            <div className="bg-white rounded-lg shadow-md p-6 mb-6">
              <h3 className="font-semibold mb-3">Document Info</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">ID:</span>
                  <span className="font-mono text-xs">{document.id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Fingerprint:</span>
                  <span className="font-mono text-xs">{document.fingerprint.substring(0, 8)}...</span>
                </div>
                {document.source_path && (
                  <div className="flex justify-between">
                    <span className="text-gray-600">Source:</span>
                    <span className="text-xs truncate ml-2">{document.source_path}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Top Citations */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <h3 className="font-semibold mb-3">Top Citations</h3>
              {citations.length === 0 ? (
                <p className="text-sm text-gray-500">No citations found</p>
              ) : (
                <div className="space-y-3">
                  {citations.slice(0, 5).map((citation) => (
                    <div key={citation.id} className="p-3 bg-gray-50 rounded-md">
                      <div className="flex items-start justify-between mb-2">
                        <span className="text-sm font-medium text-gray-900">
                          {citation.raw_text}
                        </span>
                        {getConfidenceBadge(citation.confidence)}
                      </div>
                      
                      <div className="text-xs text-gray-600">
                        {citation.reporter && <div>Reporter: {citation.reporter}</div>}
                        {citation.page_number && <div>Page: {citation.page_number}</div>}
                      </div>
                    </div>
                  ))}
                  
                  {citations.length > 5 && (
                    <p className="text-xs text-gray-500 text-center">
                      +{citations.length - 5} more citations
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

