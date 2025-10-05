/**
 * Unified Graph Container - Multi-View Graph Explorer
 * Orchestrates view selection, data fetching, layout strategies, and interactions
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import * as d3 from 'd3';
import {
  UnifiedNode,
  UnifiedEdge,
  UnifiedGraph,
  GraphViewType,
  GraphFilters,
} from '../types';
import {
  fetchUnifiedGraph,
  fetchNeighbors,
  fetchFactCluster,
} from '../api/graphApi';
import {
  forceLayout,
  layeredLayout,
  radialLayout,
  partitionLayout,
  radialDocumentLayout,
  applyCachedPositions,
  cachePositions,
} from '../layout/strategies';
import './GraphContainer.css';

interface GraphContainerProps {
  projectId: string;
  initialView?: GraphViewType;
  environment?: string;
  documentId?: string;
}

export const GraphContainer: React.FC<GraphContainerProps> = ({
  projectId,
  initialView = 'knowledge',
  environment,
  documentId,
}) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const [view, setView] = useState<GraphViewType>(initialView);
  const [graph, setGraph] = useState<UnifiedGraph | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [filters, setFilters] = useState<GraphFilters>({
    roles: new Set(),
    categories: new Set(),
    environments: new Set(),
    searchQuery: '',
  });

  const [sidePanelOpen, setSidePanelOpen] = useState(false);
  const [sidePanelContent, setSidePanelContent] = useState<any>(null);

  const simulationRef = useRef<d3.Simulation<UnifiedNode, undefined> | null>(null);

  // Load graph data
  const loadGraph = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchUnifiedGraph(projectId, view, {
        environment,
        documentId,
        includeClusters: view === 'knowledge',
        includeRelated: view === 'document',
      });
      setGraph(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [projectId, view, environment, documentId]);

  useEffect(() => {
    loadGraph();
  }, [loadGraph]);

  // Apply layout strategy
  useEffect(() => {
    if (!graph || !svgRef.current || !containerRef.current) return;

    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight;

    let nodes = [...graph.nodes];
    const edges = [...graph.edges];

    // Apply cached positions if available
    const cacheKey = `graph-positions-${projectId}-${view}`;
    nodes = applyCachedPositions(nodes, cacheKey);

    let layoutResult;
    switch (view) {
      case 'knowledge':
        layoutResult = forceLayout(nodes, edges, width, height);
        simulationRef.current = layoutResult.simulation || null;
        break;
      case 'infra':
        layoutResult = layeredLayout(nodes, edges, width, height);
        break;
      case 'platform':
        layoutResult = radialLayout(nodes, edges, width, height);
        break;
      case 'environment':
        layoutResult = partitionLayout(nodes, edges, width, height);
        break;
      case 'document':
        layoutResult = radialDocumentLayout(nodes, edges, width, height, documentId);
        break;
      default:
        layoutResult = forceLayout(nodes, edges, width, height);
    }

    renderGraph(layoutResult.nodes, edges, width, height);

    // Save positions when simulation ends or on unmount
    return () => {
      if (simulationRef.current) {
        simulationRef.current.stop();
        cachePositions(nodes, cacheKey);
      }
    };
    // renderGraph is defined inline and uses current state/props, so we exclude it from dependencies
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph, view, filters, projectId, documentId]);

  const renderGraph = (
    nodes: UnifiedNode[],
    edges: UnifiedEdge[],
    width: number,
    height: number
  ) => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    // Add zoom behavior
    const g = svg.append('g');
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });
    svg.call(zoom);

    // Filter nodes and edges by filters
    const filteredNodes = applyFilters(nodes, filters);
    const nodeIds = new Set(filteredNodes.map((n) => n.id));
    const filteredEdges = edges.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target));

    // Draw edges
    const link = g
      .append('g')
      .selectAll('line')
      .data(filteredEdges)
      .join('line')
      .attr('class', 'graph-edge')
      .attr('stroke', (d) => getEdgeColor(d.kind))
      .attr('stroke-width', 1.5)
      .attr('stroke-opacity', 0.6)
      .attr('marker-end', (d) => (d.directional ? 'url(#arrowhead)' : ''));

    // Draw nodes
    const node = g
      .append('g')
      .selectAll('circle')
      .data(filteredNodes)
      .join('circle')
      .attr('class', 'graph-node')
      .attr('r', (d) => getNodeRadius(d))
      .attr('fill', (d) => getNodeColor(d.role))
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)
      .style('cursor', 'pointer')
      .on('mouseover', handleNodeHover)
      .on('mouseout', handleNodeOut)
      .on('click', handleNodeClick)
      .on('dblclick', handleNodeExpand)
      .call(
        d3
          .drag<SVGCircleElement, UnifiedNode>()
          .on('start', dragStarted)
          .on('drag', dragged)
          .on('end', dragEnded) as any
      );

    // Draw labels
    const label = g
      .append('g')
      .selectAll('text')
      .data(filteredNodes)
      .join('text')
      .attr('class', 'graph-label')
      .attr('text-anchor', 'middle')
      .attr('dy', (d) => getNodeRadius(d) + 12)
      .attr('font-size', '10px')
      .attr('pointer-events', 'none')
      .text((d) => truncateLabel(d.display));

    // Add arrowhead marker
    svg
      .append('defs')
      .append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '-0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('orient', 'auto')
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .append('path')
      .attr('d', 'M 0,-5 L 10,0 L 0,5')
      .attr('fill', '#999');

    // Update positions on tick
    const updatePositions = () => {
      link
        .attr('x1', (d: any) => (typeof d.source === 'object' ? d.source.x : nodes.find((n) => n.id === d.source)?.x || 0))
        .attr('y1', (d: any) => (typeof d.source === 'object' ? d.source.y : nodes.find((n) => n.id === d.source)?.y || 0))
        .attr('x2', (d: any) => (typeof d.target === 'object' ? d.target.x : nodes.find((n) => n.id === d.target)?.x || 0))
        .attr('y2', (d: any) => (typeof d.target === 'object' ? d.target.y : nodes.find((n) => n.id === d.target)?.y || 0));

      node.attr('cx', (d) => d.x!).attr('cy', (d) => d.y!);
      label.attr('x', (d) => d.x!).attr('y', (d) => d.y!);
    };

    if (simulationRef.current) {
      simulationRef.current.on('tick', updatePositions);
    } else {
      updatePositions();
    }
  };

  const applyFilters = (nodes: UnifiedNode[], filters: GraphFilters): UnifiedNode[] => {
    return nodes.filter((n) => {
      if (filters.roles.size > 0 && !filters.roles.has(n.role)) return false;
      if (filters.categories.size > 0 && n.cluster && !Array.from(filters.categories).some((c) => n.id.includes(c))) return false;
      if (filters.environments.size > 0 && n.environment && !filters.environments.has(n.environment)) return false;
      if (filters.searchQuery && !n.display.toLowerCase().includes(filters.searchQuery.toLowerCase())) return false;
      return true;
    });
  };

  const handleNodeHover = (event: any, d: UnifiedNode) => {
    // Show tooltip
    d3.select('body').append('div')
      .attr('class', 'graph-tooltip')
      .style('position', 'absolute')
      .style('background', '#333')
      .style('color', '#fff')
      .style('padding', '8px')
      .style('border-radius', '4px')
      .style('font-size', '12px')
      .style('pointer-events', 'none')
      .style('z-index', '1000')
      .html(`
        <strong>${d.display}</strong><br/>
        Role: ${d.role}<br/>
        ${d.metrics?.degree ? `Degree: ${d.metrics.degree}<br/>` : ''}
        ${d.metrics?.fact_count ? `Facts: ${d.metrics.fact_count}<br/>` : ''}
        ${d.cluster ? `Cluster Size: ${d.cluster.size}` : ''}
      `)
      .style('left', `${event.pageX + 10}px`)
      .style('top', `${event.pageY + 10}px`);
  };

  const handleNodeOut = () => {
    d3.selectAll('.graph-tooltip').remove();
  };

  const handleNodeClick = (event: any, d: UnifiedNode) => {
    event.stopPropagation();
    setSidePanelOpen(true);
    setSidePanelContent({ node: d, type: 'node' });
  };

  const handleNodeExpand = async (event: any, d: UnifiedNode) => {
    event.stopPropagation();
    if (d.role === 'FactCluster') {
      await expandCluster(d.id);
    } else {
      await expandNeighbors(d.id);
    }
  };

  const expandCluster = async (clusterId: string) => {
    try {
      const data = await fetchFactCluster(projectId, clusterId);
      setSidePanelOpen(true);
      setSidePanelContent({ cluster: data, type: 'cluster' });
    } catch (e) {
      console.error('Failed to expand cluster:', e);
    }
  };

  const expandNeighbors = async (nodeId: string) => {
    try {
      const data = await fetchNeighbors(projectId, nodeId, 1, 50);
      // Merge neighbors into graph
      if (graph) {
        const newNodes = [...graph.nodes];
        const newEdges = [...graph.edges];
        const existingIds = new Set(newNodes.map((n) => n.id));

        data.nodes.forEach((n) => {
          if (!existingIds.has(n.id)) {
            newNodes.push(n);
          }
        });

        data.edges.forEach((e) => {
          newEdges.push(e);
        });

        setGraph({ ...graph, nodes: newNodes, edges: newEdges });
      }
    } catch (e) {
      console.error('Failed to expand neighbors:', e);
    }
  };

  const dragStarted = (event: any, d: UnifiedNode) => {
    if (simulationRef.current && !event.active) simulationRef.current.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
  };

  const dragged = (event: any, d: UnifiedNode) => {
    d.fx = event.x;
    d.fy = event.y;
  };

  const dragEnded = (event: any, d: UnifiedNode) => {
    if (simulationRef.current && !event.active) simulationRef.current.alphaTarget(0);
    d.fx = null;
    d.fy = null;
  };

  const getNodeRadius = (d: UnifiedNode): number => {
    if (d.role === 'FactCluster') return Math.min(8 + (d.cluster?.size || 0) * 0.5, 20);
    return Math.min(8 + (d.metrics?.degree || 0) * 2, 25);
  };

  const getNodeColor = (role: string): string => {
    const colors: Record<string, string> = {
      Platform: '#ff6b6b',
      Application: '#4ecdc4',
      Server: '#45b7d1',
      Database: '#f7b731',
      Storage: '#5f27cd',
      IP: '#00d2d3',
      OS: '#ee5a6f',
      Document: '#1dd1a1',
      Environment: '#ff9ff3',
      FactCluster: '#feca57',
      Entity: '#a29bfe',
      Discovery: '#dfe6e9',
    };
    return colors[role] || '#95a5a6';
  };

  const getEdgeColor = (kind: string): string => {
    const colors: Record<string, string> = {
      infra: '#3498db',
      data: '#2ecc71',
      provenance: '#9b59b6',
      semantic: '#e74c3c',
    };
    return colors[kind] || '#95a5a6';
  };

  const truncateLabel = (label: string, maxLen: number = 20): string => {
    return label.length > maxLen ? label.substring(0, maxLen) + '...' : label;
  };

  const handleFitView = () => {
    if (!svgRef.current || !graph) return;
    const svg = d3.select(svgRef.current);
    const bounds = (svg.select('g').node() as SVGGElement)?.getBBox();
    if (bounds) {
      const width = containerRef.current!.clientWidth;
      const height = containerRef.current!.clientHeight;
      const scale = Math.min(width / bounds.width, height / bounds.height) * 0.9;
      const translate = [
        width / 2 - scale * (bounds.x + bounds.width / 2),
        height / 2 - scale * (bounds.y + bounds.height / 2),
      ];
      svg.transition().duration(750).call(
        d3.zoom<SVGSVGElement, unknown>().transform as any,
        d3.zoomIdentity.translate(translate[0], translate[1]).scale(scale)
      );
    }
  };

  const handleResetLayout = () => {
    const cacheKey = `graph-positions-${projectId}-${view}`;
    localStorage.removeItem(cacheKey);
    loadGraph();
  };

  return (
    <div className="graph-container" ref={containerRef}>
      {/* Toolbar */}
      <div className="graph-toolbar">
        <select value={view} onChange={(e) => setView(e.target.value as GraphViewType)}>
          <option value="knowledge">Knowledge</option>
          <option value="infra">Infrastructure</option>
          <option value="platform">Platform</option>
          <option value="environment">Environment</option>
          <option value="document">Document</option>
        </select>
        <input
          type="text"
          placeholder="Search nodes..."
          value={filters.searchQuery}
          onChange={(e) => setFilters({ ...filters, searchQuery: e.target.value })}
        />
        <button onClick={handleFitView}>Fit View (F)</button>
        <button onClick={handleResetLayout}>Reset Layout (L)</button>
      </div>

      {/* Graph Canvas */}
      <svg ref={svgRef} width="100%" height="100%" />

      {/* Side Panel */}
      {sidePanelOpen && (
        <div className="graph-side-panel">
          <button onClick={() => setSidePanelOpen(false)}>Close</button>
          {sidePanelContent?.type === 'node' && (
            <div>
              <h3>{sidePanelContent.node.display}</h3>
              <p>Role: {sidePanelContent.node.role}</p>
              <p>Degree: {sidePanelContent.node.metrics?.degree || 0}</p>
            </div>
          )}
          {sidePanelContent?.type === 'cluster' && (
            <div>
              <h3>Cluster: {sidePanelContent.cluster.category}</h3>
              <ul>
                {sidePanelContent.cluster.facts.map((f: any) => (
                  <li key={f.id}>{f.text}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Legend */}
      <div className="graph-legend">
        <h4>Legend</h4>
        <div>
          {Array.from(new Set(graph?.nodes.map((n) => n.role) || [])).map((role) => (
            <div key={role} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div
                style={{
                  width: '12px',
                  height: '12px',
                  borderRadius: '50%',
                  background: getNodeColor(role),
                }}
              />
              <span>{role}</span>
            </div>
          ))}
        </div>
      </div>

      {loading && <div className="graph-loading">Loading...</div>}
      {error && <div className="graph-error">{error}</div>}
    </div>
  );
};
