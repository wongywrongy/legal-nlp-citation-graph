"use client";

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { FileText, Calendar, User, ArrowRight, RefreshCw } from 'lucide-react';
import { documentApi } from '@/lib/api';

interface Document {
  id: string;
  title: string;
  created_at: string;
  fingerprint: string;
}

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatingTitles, setUpdatingTitles] = useState(false);

  const loadDocuments = async () => {
    try {
      const response = await documentApi.getDocuments();
      setDocuments(response.items || []);
    } catch (err) {
      console.error('Failed to fetch documents:', err);
      setError('Failed to load documents');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, []);

  if (loading) {
    return (
      <div className="container mx-auto px-6 py-8">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading documents...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto px-6 py-8">
        <div className="text-center text-red-600">
          <p>{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-6 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Legal Documents</h1>
        <div className="flex space-x-2">
          <button
            onClick={async () => {
              try {
                setUpdatingTitles(true);
                const response = await fetch('/v1/documents/update-all-titles', { method: 'POST' });
                const result = await response.json();
                alert(result.message);
                // Refresh the documents list
                loadDocuments();
              } catch (err) {
                alert('Failed to update titles');
                console.error(err);
              } finally {
                setUpdatingTitles(false);
              }
            }}
            disabled={updatingTitles}
            className="bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 disabled:opacity-50 flex items-center"
          >
            {updatingTitles ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                Updating...
              </>
            ) : (
              <>
                <RefreshCw className="w-4 h-4 mr-2" />
                Update Titles
              </>
            )}
          </button>
        </div>
      </div>

      <div className="mb-8">
        <p className="text-gray-600">
          Browse and analyze processed legal documents
        </p>
      </div>

      {documents.length === 0 ? (
        <div className="text-center py-12">
          <FileText className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">No documents</h3>
          <p className="mt-1 text-sm text-gray-500">
            No documents have been processed yet.
          </p>
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {documents.map((doc) => (
            <Link
              key={doc.id}
              href={`/documents/${doc.id}`}
              className="block group"
            >
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center mb-3">
                      <FileText className="h-5 w-5 text-blue-600 mr-2" />
                      <h3 className="text-lg font-semibold text-gray-900 group-hover:text-blue-600 transition-colors">
                        {doc.title}
                      </h3>
                    </div>
                    
                    <div className="space-y-2 text-sm text-gray-600">
                      <div className="flex items-center">
                        <Calendar className="h-4 w-4 mr-2" />
                        <span>
                          {new Date(doc.created_at).toLocaleDateString()}
                        </span>
                      </div>
                      
                      <div className="flex items-center">
                        <User className="h-4 w-4 mr-2" />
                        <span className="font-mono text-xs">
                          {doc.fingerprint.substring(0, 8)}...
                        </span>
                      </div>
                    </div>
                  </div>
                  
                  <ArrowRight className="h-5 w-5 text-gray-400 group-hover:text-blue-600 transition-colors" />
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
