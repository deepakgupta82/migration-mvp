/**
 * Graph Visualizer Component - Interactive dependency graph visualization
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { apiService, GraphData, GraphNode, GraphEdge } from '../../services/api';

interface GraphVisualizerProps {
  projectId: string;
  viewType?: 'knowledge-graph' | 'infrastructure';
}

export const GraphVisualizer: React.FC<GraphVisualizerProps> = ({ projectId, viewType = 'knowledge-graph' }) => {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNodeType, setSelectedNodeType] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [hoveredNode, setHoveredNode] = useState<{node: GraphNode, x: number, y: number} | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [modalOpened, setModalOpened] = useState(false);
  const [highlightedNodes, setHighlightedNodes] = useState<Set<string>>(new Set());
  const graphRef = useRef<any>(null);

  const normalizeGraph = (raw: any): GraphData => {
    // If the payload already matches the UI-minimal schema, pass-through with light wrapping
    const rawNodes = (raw?.nodes ?? []) as any[];
    const rawEdges = (raw?.edges ?? raw?.relationships ?? []) as any[];
    const looksMinimal = rawNodes.length > 0 && typeof rawNodes[0]?.id === 'string' && typeof rawNodes[0]?.label === 'string' && !('labels' in rawNodes[0]);

    if (looksMinimal) {
      const nodes: GraphNode[] = rawNodes.map((n) => ({
        id: String(n.id),
        label: String(n.label ?? n.name ?? n.id),
        type: String(n.type ?? 'Unknown'),
        properties: n,
      }));
      const nodeIds = new Set(nodes.map((n) => n.id));
      const edges: GraphEdge[] = rawEdges
        .map((r) => ({
          source: String(r.source ?? r.source_id ?? ''),
          target: String(r.target ?? r.target_id ?? ''),
          label: String(r.label ?? r.type ?? 'RELATED_TO'),
          properties: r,
        }))
        .filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target));
      return { nodes, edges, links: edges };
    }

    // Generic normalization (legacy full graph payloads)
    const nodes: GraphNode[] = [];
    let edges: GraphEdge[] = [];
    const idToName = new Map<string, string>();
    for (const n of rawNodes) {
      const props = (n?.properties ?? {}) as Record<string, any>;
      const labels = (n?.labels ?? n?.label ?? []) as string[] | string;
      const primaryLabel = Array.isArray(labels) ? (labels[0] ?? '') : (labels || '');
      const nodeIdBase = n?.id ?? n?.node_id ?? props?.id ?? props?.node_id ?? props?.name ?? n?.name ?? '';
      const nodeId = String(nodeIdBase);
      const displayBase = n?.label ?? n?.name ?? props?.name ?? nodeId;
      const display = String(displayBase ?? (nodeId || 'Unknown'));
      const typeBase = n?.type ?? props?.type ?? primaryLabel;
      const type = String(typeBase ?? 'Unknown');
      if (!display) continue;
      idToName.set(nodeId || display, display);
      nodes.push({ id: display, label: display, type, properties: n });
    }
    for (const r of rawEdges) {
      const props = (r?.properties ?? {}) as Record<string, any>;
      const src = String(r?.source ?? r?.source_id ?? props?.source ?? props?.source_id ?? '');
      const tgt = String(r?.target ?? r?.target_id ?? props?.target ?? props?.target_id ?? '');
      const label = String(r?.label ?? r?.type ?? props?.type ?? props?.label ?? 'RELATED_TO');
      const sourceName = idToName.get(src);
      const targetName = idToName.get(tgt);
      const source = (sourceName != null && sourceName !== '') ? sourceName : (src || '');
      const target = (targetName != null && targetName !== '') ? targetName : (tgt || '');
      if (!source || !target) continue;
      edges.push({ source, target, label, properties: r });
    }
    const validNodeIds = new Set(nodes.map(n => n.id));
    edges = edges.filter(e => validNodeIds.has(e.source) && validNodeIds.has(e.target));
    return { nodes, edges, links: edges };
  };

  const fetchGraphData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch via API service (adds headers + correlation ID)
      const raw = viewType === 'knowledge-graph'
        ? await apiService.getUiMinimalGraph(projectId)
        : await apiService.getProjectGraph(projectId, 'infrastructure');
      const realGraphData = normalizeGraph(raw);

      // Filter data based on view type
      if (viewType === 'infrastructure') {
        // Filter for infrastructure-related nodes and relationships
        const infrastructureTypes = ['server', 'database', 'network', 'service', 'storage', 'cache', 'application', 'component'];
        realGraphData.nodes = realGraphData.nodes.filter(node =>
          node.type && infrastructureTypes.includes(node.type.toLowerCase())
        );
        realGraphData.edges = realGraphData.edges.filter(edge =>
          realGraphData.nodes.some(n => n.id === edge.source) &&
          realGraphData.nodes.some(n => n.id === edge.target)
        );
      } else {
        // knowledge-graph: UI-minimal already filtered; keep as-is
      }

      // If no data is available, show empty state
      if (!realGraphData.nodes || realGraphData.nodes.length === 0) {
        const emptyMessage = viewType === 'infrastructure'
          ? 'No infrastructure relationship data available for this project. Upload and process infrastructure documents to generate the infrastructure graph.'
          : 'No knowledge graph data available for this project. Upload and process documents to generate the knowledge graph.';
        setGraphData({ nodes: [], edges: [], links: [] });
        setError(emptyMessage);
      } else {
        setGraphData(realGraphData);
      }

      setLoading(false);

    } catch (err) {
      console.error('Error loading graph data:', err);
      const anyErr = err as any;
      const msg = typeof anyErr?.message === 'string' ? anyErr.message : 'Unknown error';
      setError(`Failed to load graph data. ${msg}`);
      setLoading(false);
    }
  }, [projectId, viewType]);

  useEffect(() => {
    fetchGraphData();
  }, [fetchGraphData]);

  const getNodeColor = (nodeType: string) => {
    const colors: Record<string, string> = {
      Server: '#1c7ed6',
      Service: '#1c7ed6',
      Application: '#51cf66',
      App: '#51cf66',
      Database: '#fd7e14',
      DB: '#fd7e14',
      Network: '#9775fa',
      OS: '#845ef7',
      Platform: '#5c7cfa',
      IP: '#1098ad',
      Storage: '#ffd43b',
      Cache: '#20c997',
      Security: '#ff6b6b',
      default: '#868e96',
    };
    return colors[nodeType] || colors[nodeType?.toLowerCase()?.replace(/\b\w/g, c => c.toUpperCase())] || colors.default;
  };


  const getFilteredData = () => {
    if (!graphData) return null;

    let filteredNodes = graphData.nodes || [];
    let filteredEdges = graphData.edges || [];

    // Filter by type
    if (selectedNodeType !== 'all') {
      filteredNodes = filteredNodes.filter(node => node.type === selectedNodeType);
      const nodeIds = new Set(filteredNodes.map(node => node.id));
      filteredEdges = filteredEdges.filter(
        edge => nodeIds.has(edge.source) && nodeIds.has(edge.target)
      );
    }

    // Filter by search
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      filteredNodes = filteredNodes.filter(node =>
        node.label.toLowerCase().includes(term) || node.type.toLowerCase().includes(term)
      );
      const nodeIds = new Set(filteredNodes.map(node => node.id));
      filteredEdges = filteredEdges.filter(
        edge => nodeIds.has(edge.source) && nodeIds.has(edge.target)
      );
    }

    return {
      nodes: filteredNodes,
      edges: filteredEdges,
      links: filteredEdges
    };
  };

  const nodeTypes = graphData && graphData.nodes
    ? [...new Set(graphData.nodes.map(node => node.type).filter(type => type != null && type !== ''))]
    : [];

  if (loading) {
    return (
      <div style={{ padding: '1rem', border: '1px solid #e9ecef', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '2rem', flexDirection: 'column' }}>
          <div>Loading...</div>
          <span>Loading dependency graph...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '1rem', border: '1px solid #e9ecef', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
        <div style={{ color: 'red', padding: '1rem', border: '1px solid red', borderRadius: '4px' }}>
          <h4>Error</h4>
          {error}
        </div>
      </div>
    );
  }

  if (!graphData || !graphData.nodes || graphData.nodes.length === 0) {
    return (
      <div style={{ padding: '1rem', border: '1px solid #e9ecef', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
        <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}>
          <div style={{ textAlign: 'center' }}>
            <span style={{ fontSize: '1.25rem', fontWeight: 600, color: 'blue' }}>
              {viewType === 'infrastructure' ? 'Infrastructure Dependency Graph' : 'Knowledge Graph'}
            </span>
            <span style={{ fontSize: '1rem', color: '#868e96', marginTop: '1rem', display: 'block' }}>
              {viewType === 'infrastructure' ? 'No infrastructure components found' : 'No knowledge graph entities found'}
            </span>
            <span style={{ fontSize: '0.875rem', color: '#868e96', marginTop: '0.5rem', display: 'block' }}>
              Upload and analyze documents to build the graph. The system will automatically extract components and relationships.
            </span>
          </div>
        </div>
      </div>
    );
  }

  const filteredData = getFilteredData();

  return (
    <div style={{ padding: '1rem', border: '1px solid #e9ecef', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
        <span style={{ fontSize: '1.25rem', fontWeight: 600 }}>
          {viewType === 'infrastructure' ? 'Infrastructure Dependency Graph' : 'Knowledge Graph'}
        </span>
        <div style={{ display: 'flex', gap: '1rem' }}>
          <select
            value={selectedNodeType}
            onChange={(e) => setSelectedNodeType(e.target.value)}
            style={{ width: '150px', padding: '0.5rem', fontSize: '0.875rem' }}
          >
            <option value="all">All Components</option>
            {nodeTypes.filter(type => type != null && type !== '').map(type => <option key={type} value={String(type)}>{String(type)}</option>)}
          </select>
          <button style={{ background: 'none', border: 'none', cursor: 'pointer' }} onClick={() => graphRef.current?.zoomToFit(400)}>
            🔍
          </button>
          <button style={{ background: 'none', border: 'none', cursor: 'pointer' }} onClick={fetchGraphData}>
            ↻
          </button>
        </div>
      </div>

      <input
        type="text"
        placeholder="Search nodes..."
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
        style={{ marginBottom: '1rem', padding: '0.5rem', fontSize: '0.875rem', width: '100%' }}
      />

      <div style={{ height: '500px', border: '1px solid #e9ecef', borderRadius: '8px' }}>
        {filteredData && filteredData.nodes && filteredData.nodes.length > 0 ? (
          <ForceGraph2D
            ref={graphRef}
            graphData={filteredData}
            nodeLabel="label"
            nodeColor={(node: any) => highlightedNodes.has(node.id) ? '#ff6b6b' : getNodeColor(node.type)}
            nodeRelSize={8}
            linkLabel="label"
            linkColor={() => '#adb5bd'}
            linkWidth={viewType === 'knowledge-graph' ? 1.2 : 2}
            linkCurvature={0.2}
            linkDirectionalArrowLength={8}
            linkDirectionalArrowRelPos={0.8}
            onNodeClick={(node: any) => {
              setSelectedNode(node);
              setModalOpened(true);
              // Highlight connected nodes
              if (graphData) {
                const connected = new Set([node.id]);
                graphData.edges.forEach(edge => {
                  if (edge.source === node.id) connected.add(edge.target);
                  if (edge.target === node.id) connected.add(edge.source);
                });
                setHighlightedNodes(connected);
              }
            }}
            onLinkClick={(link: any) => {
              console.log('Link clicked:', link);
            }}
            cooldownTicks={100}
            onEngineStop={() => graphRef.current?.zoomToFit(400)}
            // Custom node rendering with gradients and shadows
            nodeCanvasObjectMode={() => 'replace'}
            nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
              // Skip rendering if coordinates are not finite to prevent createRadialGradient errors
              if (!isFinite(node.x) || !isFinite(node.y)) return;

              const size = 8;
              const color = getNodeColor(node.type);

              // Shadow effect
              ctx.shadowColor = 'rgba(0,0,0,0.3)';
              ctx.shadowBlur = 5;
              ctx.shadowOffsetX = 2;
              ctx.shadowOffsetY = 2;

              // Gradient background
              const gradient = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, size);
              gradient.addColorStop(0, color);
              gradient.addColorStop(1, 'rgba(255,255,255,0.8)');
              ctx.fillStyle = gradient;
              ctx.beginPath();
              ctx.arc(node.x, node.y, size, 0, 2 * Math.PI);
              ctx.fill();

              // Reset shadow
              ctx.shadowColor = 'transparent';
              ctx.shadowBlur = 0;
              ctx.shadowOffsetX = 0;
              ctx.shadowOffsetY = 0;

              // Border
              ctx.strokeStyle = '#000';
              ctx.lineWidth = 1;
              ctx.stroke();

              // Label
              const labelFull = String(node.label || node.id || '');
              const label = labelFull.length > 32 ? `${labelFull.slice(0, 29)}...` : labelFull;
              const fontSize = Math.max(10, 12 / globalScale);
              ctx.font = `${fontSize}px Sans-Serif`;
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              ctx.fillStyle = '#fff';
              ctx.fillText(label, node.x, node.y);
            }}
            // Improve click/tap hit area to include label rectangle
            nodePointerAreaPaint={(node: any, color: string, ctx: CanvasRenderingContext2D, globalScale: number) => {
              const labelFull = String(node.label || node.id || '');
              const label = labelFull.length > 32 ? `${labelFull.slice(0, 29)}...` : labelFull;
              const fontSize = Math.max(10, 12 / globalScale);
              ctx.font = `${fontSize}px Sans-Serif`;
              const textWidth = ctx.measureText(label).width;
              const padX = 6, padY = 4;
              ctx.fillStyle = color;
              ctx.fillRect(node.x - textWidth / 2 - padX, node.y - fontSize / 2 - padY, textWidth + padX * 2, fontSize + padY * 2);
            }}
          />
        ) : (
          <div style={{ 
            height: '100%', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            color: '#868e96'
          }}>
            <span>No graph data available</span>
          </div>
        )}
      </div>

      {/* Legend */}
      <div style={{ marginTop: '1rem', display: 'flex', gap: '1rem' }}>
        <span style={{ fontSize: '0.875rem', fontWeight: 500 }}>
          Legend:
        </span>
        {nodeTypes.map(type => (
          <div key={type} style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <span style={{ color: getNodeColor(type) }}>●</span>
            <span style={{ fontSize: '0.875rem' }}>{type}</span>
          </div>
        ))}
      </div>

      {modalOpened && (
        <div style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: 'white', padding: '2rem', borderRadius: '8px', maxWidth: '80%', maxHeight: '80%', overflow: 'auto' }}>
            <h2>Node Details</h2>
            <button onClick={() => setModalOpened(false)} style={{ float: 'right' }}>×</button>
            {selectedNode && <pre>{JSON.stringify(selectedNode, null, 2)}</pre>}
          </div>
        </div>
      )}
    </div>
  );
};
