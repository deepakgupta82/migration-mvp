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

/**
 * Extract human-readable label from node data
 * Tries multiple property paths to find a meaningful name instead of GUID
 */
const extractMeaningfulLabel = (node: any): string => {
  // Try label first (PyVis format)
  if (node.label && !node.label.startsWith('discovery_') && !node.label.match(/^[a-f0-9-]{36}$/i)) {
    return node.label;
  }
  
  // Try common name properties
  const props = node.properties ?? node;
  const candidateFields = [
    'name', 'server_name', 'app_name', 'application_name', 'db_name', 'database_name',
    'hostname', 'host_name', 'service_name', 'tech_name', 'technology_name',
    'display_name', 'title', 'description'
  ];
  
  for (const field of candidateFields) {
    const value = props[field];
    if (value && typeof value === 'string' && value.trim().length > 0) {
      // Avoid GUIDs and discovery IDs
      if (!value.startsWith('discovery_') && !value.match(/^[a-f0-9-]{36}$/i)) {
        return value.trim();
      }
    }
  }
  
  // Fallback: extract from title or label, removing GUID suffix
  const label = node.label || node.title || node.id || 'Unknown';
  // Remove GUID patterns like "discovery_90c3b08b-f7f8-47db..."
  return label.replace(/^discovery_[a-f0-9-]+_?/i, '').replace(/[a-f0-9-]{20,}/gi, '...').slice(0, 50);
};

export const GraphVisualizer: React.FC<GraphVisualizerProps> = ({ projectId, viewType = 'knowledge-graph' }) => {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNodeType, setSelectedNodeType] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState<string>('');
  // Removed hoveredNode state (not currently used in UI hover tooltips)
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [modalOpened, setModalOpened] = useState(false);
  const [highlightedNodes, setHighlightedNodes] = useState<Set<string>>(new Set());
  const [hoverNode, setHoverNode] = useState<GraphNode | null>(null);
  // Persisted zoom/center state
  const [initialZoomApplied, setInitialZoomApplied] = useState(false);
  const ZOOM_STORE_KEY = `graph_zoom_${projectId}_${viewType}`;
  const POS_STORE_KEY = `graph_pos_${projectId}_${viewType}`;
  const lastTransformRef = useRef<{k:number; x:number; y:number}|null>(null);
  const graphRef = useRef<any>(null);

  const normalizeGraph = (raw: any): GraphData => {
    // Normalization pipeline accepts PyVis enriched format (preferred) and legacy structures.
    // It converts nodes/edges into a unified GraphData shape with labels suitable for visualization.
    // Handle infrastructure topology structure: {topology: {nodes, relationships}}
    const topologyData = raw?.topology ?? raw;
    const rawNodes = (topologyData?.nodes ?? raw?.nodes ?? []) as any[];
    const rawEdges = (topologyData?.relationships ?? topologyData?.edges ?? raw?.edges ?? raw?.relationships ?? []) as any[];
    
    console.log(`[GraphVisualizer] normalizeGraph - rawNodes count: ${rawNodes.length}, rawEdges count: ${rawEdges.length}`);
    
    // PyVis format: nodes have {id, label, group}
    const isPyvisFormat = rawNodes.length > 0 && rawNodes[0]?.label && rawNodes[0]?.group;
    
    if (isPyvisFormat) {
      console.log(`[GraphVisualizer] Detected PyVis format - using labels directly`);
      const nodes: GraphNode[] = rawNodes.map((n) => {
        // Extract meaningful label from PyVis node
        const label = extractMeaningfulLabel(n);
        return {
          id: String(n.id),
          label: label,
          type: String(n.group ?? n.type ?? 'Unknown'),
          properties: n,
        };
      });
      const nodeIds = new Set(nodes.map((n) => n.id));
      
      // Handle PyVis edge format: {from, to, label}
      const edges: GraphEdge[] = rawEdges
        .map((e) => ({
          source: String(e.from ?? e.source ?? e.source_id ?? ''),
          target: String(e.to ?? e.target ?? e.target_id ?? ''),
          label: String(e.label ?? e.type ?? 'RELATED_TO'),
          properties: e,
        }))
        .filter((e) => {
          const valid = nodeIds.has(e.source) && nodeIds.has(e.target);
          if (!valid) {
            console.warn(`[GraphVisualizer] Filtered edge: ${e.source} -> ${e.target}`);
          }
          return valid;
        });
      
      console.log(`[GraphVisualizer] PyVis normalization: ${nodes.length} nodes, ${edges.length} edges`);
      return { nodes, edges, links: edges };
    }
    
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

      // UNIFIED STRATEGY: Use PyVis endpoint as primary source (it has labels!)
      // Then filter client-side based on view type
      let raw: any;
      
      try {
        // Try PyVis endpoint first - it has proper labels
        raw = await apiService.getPyvisGraph(projectId);
        console.log(`[GraphVisualizer] Using PyVis data with proper labels`);
      } catch (pyvisError) {
        console.warn(`[GraphVisualizer] PyVis failed, trying specialized endpoint:`, pyvisError);
        // Fallback to specialized endpoints
        raw = viewType === 'knowledge-graph'
          ? await apiService.getUiMinimalGraph(projectId, { hideSystem: false })
          : await apiService.getProjectGraph(projectId, 'infrastructure');
      }
      
      console.log(`[GraphVisualizer] Raw data from API (${viewType}):`, raw);
      console.log(`[GraphVisualizer] Raw data structure:`, JSON.stringify(raw, null, 2));
      console.log(`[GraphVisualizer] Raw nodes count:`, raw?.nodes?.length || 0);
      console.log(`[GraphVisualizer] Raw edges count:`, raw?.edges?.length || 0);
      
      const realGraphData = normalizeGraph(raw);
      
      console.log(`[GraphVisualizer] Normalized data:`, realGraphData);
      console.log(`[GraphVisualizer] Normalized nodes count:`, realGraphData.nodes.length);
      console.log(`[GraphVisualizer] Normalized edges count:`, realGraphData.edges.length);

      // Filter data based on view type
      if (viewType === 'infrastructure') {
        // Filter for infrastructure-related nodes and relationships.
        // We deliberately exclude 'discovery' facts and business/security categories here.
        const infraTypeAllow = new Set([
          'server','database','network','service','storage','cache','application','component','platform','os','ip'
        ]);
        realGraphData.nodes = realGraphData.nodes.filter(node => {
          const t = (node.type || '').toLowerCase();
            if (!t) return false;
            if (t === 'discovery') return false; // exclude fact nodes
            return infraTypeAllow.has(t);
        });
        const nodeIds = new Set(realGraphData.nodes.map(n=>n.id));
        realGraphData.edges = realGraphData.edges.filter(e => nodeIds.has(e.source) && nodeIds.has(e.target));
        console.log(`[GraphVisualizer] After improved infrastructure filter: ${realGraphData.nodes.length} nodes, ${realGraphData.edges.length} edges`);
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
      console.error('[GraphVisualizer] Error loading graph data:', err);
      const anyErr = err as any;
      const msg = typeof anyErr?.message === 'string' ? anyErr.message : 'Unknown error';
      setError(`Failed to load graph data. ${msg}`);
      setLoading(false);
    }
  }, [projectId, viewType]);

  useEffect(() => { fetchGraphData(); }, [fetchGraphData]);

  // Restore zoom/position after data load
  useEffect(() => {
    if (!graphData || initialZoomApplied) return;
    try {
      const storedZoom = localStorage.getItem(ZOOM_STORE_KEY);
      const storedPos = localStorage.getItem(POS_STORE_KEY);
      if (graphRef.current && storedZoom) {
        const k = parseFloat(storedZoom);
        let x = 0, y = 0;
        if (storedPos) { const parsed = JSON.parse(storedPos); x = parsed.x; y = parsed.y; }
        // Schedule after force-engine tick
        setTimeout(()=>{
          try { graphRef.current.zoom(k, 0); if (!isNaN(x) && !isNaN(y)) graphRef.current.centerAt(x, y, 0); } catch(e) { /* noop */ }
          setInitialZoomApplied(true);
        }, 400); // wait some ticks
      } else {
        setInitialZoomApplied(true);
      }
    } catch(e) { /* ignore */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graphData, initialZoomApplied]);

  // Track zoom changes (using onZoom handler delegated via ref hack)
  useEffect(() => {
    if (!graphRef.current) return;
    const fg = graphRef.current;
    const id = window.setInterval(() => {
      try {
        if (!fg) return;
        const { k } = (fg as any).state || {};
        if (k && (!lastTransformRef.current || lastTransformRef.current.k !== k)) {
          localStorage.setItem(ZOOM_STORE_KEY, String(k));
          lastTransformRef.current = { k, x:0, y:0 };
        }
      } catch { /* noop */ }
    }, 1500);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graphRef]);

  // Capture position periodically
  useEffect(() => {
    const id = window.setInterval(() => {
      try {
        if (!graphRef.current) return;
        const g = graphRef.current;
        const bbox = g.getGraphBbox?.();
        if (bbox) {
          const x = (bbox.x[0] + bbox.x[1]) / 2;
          const y = (bbox.y[0] + bbox.y[1]) / 2;
          localStorage.setItem(POS_STORE_KEY, JSON.stringify({ x, y }));
        }
      } catch { /* ignore */ }
    }, 3000);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
          <button style={{ background: 'none', border: '1px solid #ccc', borderRadius: 4, padding: '0 6px', cursor: 'pointer' }} onClick={() => graphRef.current?.zoomToFit(400)} title="Zoom to Fit">🔍</button>
          <button style={{ background: 'none', border: '1px solid #ccc', borderRadius: 4, padding: '0 6px', cursor: 'pointer' }} onClick={() => { try { const k=(graphRef.current.zoom() as number)||1; graphRef.current.zoom(k*1.15, 300);} catch{} }} title="Zoom In">＋</button>
          <button style={{ background: 'none', border: '1px solid #ccc', borderRadius: 4, padding: '0 6px', cursor: 'pointer' }} onClick={() => { try { const k=(graphRef.current.zoom() as number)||1; graphRef.current.zoom(k/1.15, 300);} catch{} }} title="Zoom Out">－</button>
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
            nodeRelSize={6}
            nodeVal={(node: any) => {
              // Degree-based sizing for readability
              const degree = graphData ? graphData.edges.filter(e=>e.source===node.id || e.target===node.id).length : 0;
              return Math.min(12, 3 + Math.sqrt(degree));
            }}
            linkLabel="label"
            linkColor={() => '#adb5bd'}
            linkWidth={viewType === 'knowledge-graph' ? 1 : 1.5}
            linkCurvature={0.15}
            linkDirectionalArrowLength={6}
            linkDirectionalArrowRelPos={0.8}
            onNodeHover={(n:any)=> setHoverNode(n || null)}
            // Physics configuration for large graphs
            d3AlphaDecay={0.02} // Slower cooling for better layout
            d3VelocityDecay={0.3} // More friction to reduce jitter
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
            cooldownTicks={150}
            // REMOVED: Auto-zoom on engine stop to prevent zoom reset
            // onEngineStop={() => graphRef.current?.zoomToFit(400)}
            // Custom node rendering with better text visibility
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

              // Label with BLACK text (was white) and white background for visibility
              const labelFull = String(node.label || node.id || '');
              const label = labelFull.length > 32 ? `${labelFull.slice(0, 29)}...` : labelFull;
              const fontSize = Math.max(10, 12 / globalScale);
              ctx.font = `${fontSize}px Sans-Serif`;
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              
              // Measure text for background
              const textWidth = ctx.measureText(label).width;
              const padX = 4, padY = 2;
              
              // Draw background rectangle for better readability
              ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
              ctx.fillRect(
                node.x - textWidth / 2 - padX, 
                node.y + size + 2 - padY, 
                textWidth + padX * 2, 
                fontSize + padY * 2
              );
              
              // Draw text in BLACK for maximum contrast
              ctx.fillStyle = '#000000';
              ctx.fillText(label, node.x, node.y + size + fontSize / 2 + 3);
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

      {/* Dual Legend */}
      <div style={{ marginTop: '1rem', display: 'flex', flexWrap:'wrap', gap: '2rem' }}>
        <div style={{ display:'flex', flexDirection:'column', gap: '0.35rem' }}>
          <span style={{ fontSize: '0.875rem', fontWeight: 600 }}>Types</span>
          {nodeTypes.map(type => (
            <div key={type} style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <span style={{ color: getNodeColor(type) }}>●</span>
              <span style={{ fontSize: '0.75rem' }}>{type}</span>
            </div>
          ))}
        </div>
        {viewType==='knowledge-graph' && (
          <div style={{ display:'flex', flexDirection:'column', gap:'0.35rem' }}>
            <span style={{ fontSize:'0.875rem', fontWeight:600 }}>Categories (Sample)</span>
            <div style={{ display:'flex', gap:'0.75rem', flexWrap:'wrap', maxWidth:420 }}>
              {['infrastructure','technology','business','security','performance','compliance'].map(cat => (
                <div key={cat} style={{ display:'flex', gap:'0.25rem', alignItems:'center', border:'1px solid #dee2e6', padding:'2px 6px', borderRadius:4, fontSize:'0.65rem', background:'#f8f9fa' }}>
                  <span style={{ fontWeight:500 }}>{cat}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Hover Tooltip */}
      {hoverNode && (
        <div style={{ position:'fixed', left: 12, bottom: 12, background:'rgba(0,0,0,0.75)', color:'#fff', padding:'8px 12px', borderRadius:6, maxWidth:360, fontSize:'0.7rem', zIndex: 1200 }}>
          <div style={{ fontWeight:600, marginBottom:4 }}>{hoverNode.label}</div>
          <div style={{ opacity:0.8 }}>Type: {hoverNode.type}</div>
          {hoverNode.properties?.raw && hoverNode.properties.raw.text && (
            <div style={{ marginTop:4 }}><em>{String(hoverNode.properties.raw.text).slice(0,120)}{String(hoverNode.properties.raw.text).length>120?'…':''}</em></div>
          )}
          <div style={{ marginTop:4, display:'flex', gap:8 }}>
            <span>Deg: {graphData ? graphData.edges.filter(e=>e.source===hoverNode.id || e.target===hoverNode.id).length : 0}</span>
            <span>ID: {hoverNode.id.slice(0,18)}{hoverNode.id.length>18?'…':''}</span>
          </div>
        </div>
      )}

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
