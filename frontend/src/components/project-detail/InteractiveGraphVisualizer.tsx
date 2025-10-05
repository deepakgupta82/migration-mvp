/**
 * Interactive Graph Visualizer (PyVis-style data rendered via ForceGraph2D)
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { apiService, PyvisGraphData } from '../../services/api';

interface InteractiveGraphVisualizerProps {
  projectId: string;
}

type FGNode = { id: string; label?: string; group?: string; title?: string; type?: string; value?: number; x?: number; y?: number };
type FGEdge = { source: string; target: string; label?: string; title?: string; dashes?: boolean; value?: number };

export const InteractiveGraphVisualizer: React.FC<InteractiveGraphVisualizerProps> = ({ projectId }) => {
  const [data, setData] = useState<{ nodes: FGNode[]; links: FGEdge[] } | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const graphRef = useRef<any>(null);
  const [showInferred, setShowInferred] = useState<boolean>(() => {
    try {
      const saved = sessionStorage.getItem('graph_show_inferred');
      return saved === null ? true : saved === '1';
    } catch {
      return true;
    }
  });

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
  const res: PyvisGraphData = await apiService.getPyvisGraph(projectId);
  const nodes: FGNode[] = (res.nodes || []).map((n) => ({ id: n.id, label: n.label, group: n.group, title: n.title, type: n.group, value: (n as any).value }));
  
      // Create a Set of valid node IDs for fast lookup
      const nodeIds = new Set(nodes.map(n => n.id));
      
      // Filter edges to only include those where both source and target nodes exist
      const allLinks: FGEdge[] = (res.edges || []).map((e) => ({ source: e.from, target: e.to, label: e.label, title: (e as any).title, dashes: (e as any).dashes, value: (e as any).value }));
      const validLinks = allLinks.filter(link => {
        const hasSource = nodeIds.has(link.source);
        const hasTarget = nodeIds.has(link.target);
        if (!hasSource || !hasTarget) {
          console.warn(`Filtered out invalid edge: ${link.source} -> ${link.target} (source exists: ${hasSource}, target exists: ${hasTarget})`);
        }
        return hasSource && hasTarget;
      });
      
      console.log(`Graph loaded: ${nodes.length} nodes, ${validLinks.length}/${allLinks.length} valid edges`);
      
      // Center applications at (0,0)
      nodes.forEach((node) => {
        if (node.group === 'Application' || node.type === 'Application') {
          node.x = 0;
          node.y = 0;
        }
      });
      setData({ nodes, links: validLinks });
    } catch (e: any) {
      setError(typeof e?.message === 'string' ? e.message : 'Failed to load graph');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => {
    try {
      sessionStorage.setItem('graph_show_inferred', showInferred ? '1' : '0');
    } catch {}
  }, [showInferred]);

  // Compute filtered links at top-level to avoid conditional hook usage warnings
  const displayedLinks = useMemo(() => {
    if (!data) return [] as FGEdge[];
    return (data.links || []).filter((l) => showInferred || !l.dashes);
  }, [data, showInferred]);

  const colorFor = (group?: string) => {
    const colors: Record<string, string> = {
      Server: '#1c7ed6',
      Application: '#51cf66',
      Database: '#fd7e14',
      Technology: '#9775fa',
      Service: '#20c997',
      default: '#868e96',
    };
    if (!group) return colors.default;
    return colors[group] || colors[group.charAt(0).toUpperCase() + group.slice(1)] || colors.default;
  };

  if (loading) {
    return (
      <div style={{ padding: '1rem', border: '1px solid #e9ecef', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '2rem', flexDirection: 'column' }}>
          <div>Loading...</div>
          <span>Loading interactive graph...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '1rem', border: '1px solid #e9ecef', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
        <div style={{ color: 'red', padding: '1rem', border: '1px solid red', borderRadius: '4px' }}>
          <strong>Error:</strong> {error}
        </div>
      </div>
    );
  }

  if (!data || !data.nodes || data.nodes.length === 0) {
    return (
      <div style={{ padding: '1rem', border: '1px solid #e9ecef', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '2rem' }}>
          <div style={{ textAlign: 'center' }}>
            <span style={{ fontSize: '1.25rem', fontWeight: '600', color: 'blue' }}>Interactive Graph</span>
            <span style={{ fontSize: '1rem', color: '#868e96', marginTop: '1rem', display: 'block' }}>No nodes available</span>
            <span style={{ fontSize: '0.875rem', color: '#868e96', marginTop: '0.5rem', display: 'block' }}>Upload and process documents to build the graph</span>
          </div>
        </div>
      </div>
    );
  }

  const Legend = () => (
    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
      <span style={{ backgroundColor: '#1c7ed6', color: 'white', padding: '0.25rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem' }}>Server</span>
      <span style={{ backgroundColor: '#51cf66', color: 'white', padding: '0.25rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem' }}>Application</span>
      <span style={{ backgroundColor: '#fd7e14', color: 'white', padding: '0.25rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem' }}>Database</span>
      <span style={{ backgroundColor: '#9775fa', color: 'white', padding: '0.25rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem' }}>Technology</span>
      <span style={{ backgroundColor: '#20c997', color: 'white', padding: '0.25rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem' }}>Service</span>
      <span style={{ border: '1px solid #868e96', color: '#868e96', padding: '0.25rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem' }}>Inferred edge = dashed</span>
    </div>
  );

  return (
    <div style={{ padding: '1rem', border: '1px solid #e9ecef', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <span style={{ fontSize: '1.25rem', fontWeight: '600' }}>Interactive Graph (New)</span>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.875rem' }}>
            <input
              type="checkbox"
              checked={showInferred}
              onChange={(e) => setShowInferred(e.target.checked)}
            />
            Inferred {showInferred ? 'on' : 'off'}
          </label>
          <button style={{ background: 'none', border: 'none', cursor: 'pointer' }} onClick={() => graphRef.current?.zoomToFit(400)}>
            Zoom
          </button>
          <button style={{ background: 'none', border: 'none', cursor: 'pointer' }} onClick={load}>
            Refresh
          </button>
        </div>
      </div>

      <div style={{ marginBottom: '0.5rem' }}>
        <Legend />
        <span style={{ fontSize: '0.75rem', color: '#868e96' }}>Nodes sized by degree; hover edges for details. Toggle hides dashed inferred edges.</span>
      </div>

      <div style={{ height: '500px', border: '1px solid #e9ecef', borderRadius: '8px' }}>
        <ForceGraph2D
           ref={graphRef}
           graphData={{ nodes: data.nodes, links: displayedLinks }}
          nodeLabel={(n: any) => n.title || n.label || n.id}
          nodeColor={(n: any) => colorFor(n.group || n.type)}
          nodeRelSize={8}
          nodeVal={(n: any) => Math.max(1, Math.min(10, (n.value || 1)))}
          linkLabel={(l: any) => l.title || l.label || 'RELATES_TO'}
          linkColor={(l: any) => (l.dashes ? '#adb5bd' : '#868e96')}
          linkWidth={(l: any) => Math.max(1, Math.min(4, (l.value || 2)))}
          linkCurvature={0.2}
          linkDirectionalParticles={(l: any) => (l.dashes ? 2 : 0)}
          linkDirectionalArrowLength={8}
          linkDirectionalArrowRelPos={0.8}
          onNodeClick={(node: any) => console.log('Node clicked:', node)}
          onLinkClick={(link: any) => console.log('Link clicked:', link)}
          cooldownTicks={100}
          onEngineStop={() => graphRef.current?.zoomToFit(400)}
          nodeCanvasObjectMode={() => 'replace'}
          nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
            // Skip rendering if coordinates are not finite to prevent createRadialGradient errors
            if (!isFinite(node.x) || !isFinite(node.y)) return;

            const size = Math.max(8, Math.min(20, node.value || 8));
            const color = colorFor(node.group || node.type);

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

            // Label with BLACK text and white background for visibility
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
        />
      </div>
    </div>
  );
};

export default InteractiveGraphVisualizer;
