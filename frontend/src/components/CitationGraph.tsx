"use client";

import React, { useCallback, useEffect, useState } from 'react';
import ReactFlow, {
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Edge,
  Node,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { graphApi } from '@/lib/api';
import { useRouter } from 'next/navigation';

interface GraphNodeData {
  label: string;
  meta: {
    year?: number;
    court?: string;
  };
}

interface GraphEdgeData {
  confidence: number;
}

const nodeColor = (node: Node<GraphNodeData>) => {
  // Safely access node data with fallbacks
  if (!node.data || !node.data.meta) {
    return '#84cc16'; // Default green color
  }
  
  if (node.data.meta.court === 'U.S. Supreme Court') return '#ef4444'; // Red for Supreme Court
  if (node.data.meta.year && node.data.meta.year > 2000) return '#3b82f6'; // Blue for recent
  return '#84cc16'; // Green for others
};

const edgeColor = (confidence: number) => {
  if (confidence >= 0.9) return '#10b981'; // Green for High
  if (confidence >= 0.7) return '#f59e0b'; // Yellow for Medium
  return '#ef4444'; // Red for Low
};

const CitationGraph: React.FC = () => {
  const router = useRouter();
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [minConfidence, setMinConfidence] = useState(0.7);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchGraphData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      console.log("Fetching graph data with confidence:", minConfidence);
      const graphData = await graphApi.getGraph(minConfidence);
      console.log("Received graph data:", graphData);
      
      if (!graphData || !graphData.nodes || !graphData.edges) {
        throw new Error("Invalid graph data structure received");
      }
      
      const initialNodes: Node<GraphNodeData>[] = graphData.nodes.map((node: any) => {
        // Ensure node has required structure
        const nodeData = {
          label: node.label || node.title || `Document ${node.id}`,
          meta: node.meta || { court: node.court, year: node.year }
        };
        
        return {
          id: node.id,
          data: nodeData,
          position: { x: Math.random() * 500, y: Math.random() * 500 },
          style: { 
            backgroundColor: '#3b82f6', // Simple blue for all nodes
            color: 'white', 
            borderRadius: '8px', 
            padding: '8px 12px',
            fontSize: '12px',
            fontWeight: '500',
            border: 'none',
            boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
          },
        };
      });
      
      const initialEdges: Edge<GraphEdgeData>[] = graphData.edges.map((edge: any) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: `${(edge.confidence * 100).toFixed(0)}%`,
        animated: edge.confidence < 0.9,
        style: { stroke: edgeColor(edge.confidence), strokeWidth: 2 },
        data: { confidence: edge.confidence },
      }));
      
      console.log("Processed nodes:", initialNodes.length, "edges:", initialEdges.length);
      setNodes(initialNodes);
      setEdges(initialEdges);
    } catch (err) {
      console.error("Failed to fetch graph data:", err);
      setError(`Failed to load graph data: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  }, [minConfidence, setNodes, setEdges]);

  useEffect(() => {
    fetchGraphData();
  }, [fetchGraphData]);

  const onConnect = useCallback(
    (params: Connection | Edge) => setEdges((eds) => addEdge(params, eds)),
    [setEdges],
  );

  const onNodeClick = useCallback((event: React.MouseEvent, node: Node<GraphNodeData>) => {
    router.push(`/documents/${node.id}`);
  }, [router]);

  if (loading) return <div className="flex justify-center items-center h-full text-xl">Loading graph...</div>;
  if (error) return <div className="flex justify-center items-center h-full text-xl text-red-500">{error}</div>;
  if (nodes.length === 0 && edges.length === 0) return <div className="flex justify-center items-center h-full text-xl">No graph data available. Documents are being processed...</div>;

  return (
    <div className="h-full w-full">
      <div className="p-4 bg-gray-100 border-b flex items-center space-x-4">
        <label htmlFor="confidence" className="font-medium">Min Confidence:</label>
        <input
          id="confidence"
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={minConfidence}
          onChange={(e) => setMinConfidence(parseFloat(e.target.value))}
          className="w-48"
        />
        <span>{(minConfidence * 100).toFixed(0)}%</span>
        <button
          onClick={fetchGraphData}
          className="ml-4 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
        >
          Apply Filter
        </button>
      </div>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        fitView
      >
        <MiniMap nodeColor={nodeColor} zoomable pannable />
        <Controls />
        <Background gap={12} size={1} />
      </ReactFlow>
    </div>
  );
};

export default CitationGraph;
