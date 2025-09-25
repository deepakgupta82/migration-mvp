/**
 * Graph Visualizer Component - Interactive dependency graph visualization
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Card, Text, Loader, Alert, Group, ActionIcon, Select } from '@mantine/core';
import { IconAlertCircle, IconRefresh, IconZoomIn } from '@tabler/icons-react';
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
  const graphRef = useRef<any>(null);

  const normalizeGraph = (raw: any): GraphData => {
    const nodes: GraphNode[] = [];
    let edges: GraphEdge[] = [];

    const rawNodes = (raw?.nodes ?? []) as any[];
    const rawEdges = (raw?.edges ?? raw?.relationships ?? []) as any[];

    // Build id -> displayName map to reconcile relationships referring by IDs
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
    // Remove any edges that reference nodes that do not exist
    const validNodeIds = new Set(nodes.map(n => n.id));
    edges = edges.filter(e => validNodeIds.has(e.source) && validNodeIds.has(e.target));

    return { nodes, edges, links: edges };
  };

  const fetchGraphData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch via API service (adds headers + correlation ID)
      const raw = await apiService.getProjectGraph(projectId, viewType === 'infrastructure' ? 'infrastructure' : undefined);
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
      Storage: '#ffd43b',
      Cache: '#20c997',
      Security: '#ff6b6b',
      default: '#868e96',
    };
    return colors[nodeType] || colors[nodeType?.toLowerCase()?.replace(/\b\w/g, c => c.toUpperCase())] || colors.default;
  };

  const getFilteredData = () => {
    if (!graphData || selectedNodeType === 'all') {
      return graphData ? {
        ...graphData,
        links: graphData.edges || [] // ForceGraph2D expects 'links' property, default to empty array
      } : null;
    }

    // Ensure nodes and edges exist before filtering
    if (!graphData.nodes || !graphData.edges) {
      return {
        nodes: [],
        edges: [],
        links: []
      };
    }

    const filteredNodes = graphData.nodes.filter(node => node.type === selectedNodeType);
    const nodeIds = new Set(filteredNodes.map(node => node.id));
    const filteredEdges = graphData.edges.filter(
      edge => nodeIds.has(edge.source) && nodeIds.has(edge.target)
    );

    return {
      nodes: filteredNodes,
      edges: filteredEdges,
      links: filteredEdges // ForceGraph2D expects 'links' property
    };
  };

  const nodeTypes = graphData && graphData.nodes
    ? [...new Set(graphData.nodes.map(node => node.type).filter(type => type != null && type !== ''))]
    : [];

  if (loading) {
    return (
      <Card shadow="sm" p="lg" radius="md" withBorder>
        <Group justify="center" p="xl">
          <Loader size="lg" />
          <Text>Loading dependency graph...</Text>
        </Group>
      </Card>
    );
  }

  if (error) {
    return (
      <Card shadow="sm" p="lg" radius="md" withBorder>
        <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red">
          {error}
        </Alert>
      </Card>
    );
  }

  if (!graphData || !graphData.nodes || graphData.nodes.length === 0) {
    return (
      <Card shadow="sm" p="lg" radius="md" withBorder>
        <Group justify="center" p="xl">
          <div style={{ textAlign: 'center' }}>
            <Text size="lg" fw={600} c="blue">
              {viewType === 'infrastructure' ? 'Infrastructure Dependency Graph' : 'Knowledge Graph'}
            </Text>
            <Text size="md" c="dimmed" mt="md">
              {viewType === 'infrastructure' ? 'No infrastructure components found' : 'No knowledge graph entities found'}
            </Text>
            <Text size="sm" c="dimmed" mt="xs">
              Upload and analyze documents to build the graph. The system will automatically extract components and relationships.
            </Text>
          </div>
        </Group>
      </Card>
    );
  }

  const filteredData = getFilteredData();

  return (
    <Card shadow="sm" p="lg" radius="md" withBorder>
      <Group justify="space-between" mb="md">
        <Text size="lg" fw={600}>
          {viewType === 'infrastructure' ? 'Infrastructure Dependency Graph' : 'Knowledge Graph'}
        </Text>
        <Group gap="md">
          <Select
            placeholder="Filter by type"
            value={selectedNodeType}
            onChange={(value) => setSelectedNodeType(value || 'all')}
            data={[
              { value: 'all', label: 'All Components' },
              ...nodeTypes.filter(type => type != null && type !== '').map(type => ({ value: String(type), label: String(type) })),
            ]}
            size="sm"
            style={{ width: 150 }}
          />
          <ActionIcon
            variant="subtle"
            onClick={() => graphRef.current?.zoomToFit(400)}
          >
            <IconZoomIn size={16} />
          </ActionIcon>
          <ActionIcon
            variant="subtle"
            onClick={fetchGraphData}
          >
            <IconRefresh size={16} />
          </ActionIcon>
        </Group>
      </Group>

      <div style={{ height: '500px', border: '1px solid #e9ecef', borderRadius: '8px' }}>
        {filteredData && filteredData.nodes && filteredData.nodes.length > 0 ? (
          <ForceGraph2D
            ref={graphRef}
            graphData={filteredData}
            nodeLabel="label"
            nodeColor={(node: any) => getNodeColor(node.type)}
            nodeRelSize={8}
            linkLabel="label"
            linkColor={() => '#868e96'}
            linkWidth={2}
            linkDirectionalArrowLength={6}
            linkDirectionalArrowRelPos={1}
            onNodeClick={(node: any) => {
              // Show node details in a tooltip or modal
              console.log('Node clicked:', node);
            }}
            onLinkClick={(link: any) => {
              // Show relationship details
              console.log('Link clicked:', link);
            }}
            cooldownTicks={100}
            onEngineStop={() => graphRef.current?.zoomToFit(400)}
            nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
              const label = node.label;
              const fontSize = 12 / globalScale;
              ctx.font = `${fontSize}px Sans-Serif`;
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              ctx.fillStyle = '#333';
              ctx.fillText(label, node.x, node.y + 15);
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
            <Text>No graph data available</Text>
          </div>
        )}
      </div>

      {/* Legend */}
      <Group mt="md" gap="md">
        <Text size="sm" fw={500}>
          Legend:
        </Text>
        {nodeTypes.map(type => (
          <Group key={type} gap="xs">
            <div
              style={{
                width: 12,
                height: 12,
                borderRadius: '50%',
                backgroundColor: getNodeColor(type),
              }}
            />
            <Text size="sm">{type}</Text>
          </Group>
        ))}
      </Group>
    </Card>
  );
};
