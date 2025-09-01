import CitationGraph from '@/components/CitationGraph';

export default function GraphPage() {
  return (
    <div className="h-screen">
      <div className="bg-white shadow-sm border-b px-6 py-4">
        <h1 className="text-2xl font-bold text-gray-900">Citation Graph</h1>
        <p className="text-gray-600 mt-1">
          Interactive visualization of legal citation relationships
        </p>
      </div>
      <div className="h-full">
        <CitationGraph />
      </div>
    </div>
  );
}
