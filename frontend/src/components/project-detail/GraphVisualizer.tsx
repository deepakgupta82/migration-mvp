/**
 * Graph Visualizer Component - Interactive dependency graph visualization
 */

import React, { useEffect, useRef, useState } from 'react';
import { Card, Text, Loader, Alert, Group, ActionIcon, Select } from '@mantine/core';
import { IconAlertCircle, IconRefresh, IconZoomIn } from '@tabler/icons-react';
import ForceGraph2D from 'react-force-graph-2d';
import { apiService, GraphData } from '../../services/api';

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

  const fetchGraphData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch real graph data from the backend API
      const endpoint = viewType === 'infrastructure'
        ? `http://localhost:8000/api/projects/${projectId}/graph?type=infrastructure`
        : `http://localhost:8000/api/projects/${projectId}/graph`;

      const response = await fetch(endpoint);

      if (!response.ok) {
        throw new Error(`Failed to fetch graph data: ${response.status} ${response.statusText}`);
      }

      const realGraphData: GraphData = await response.json();

      // Filter data based on view type
      if (viewType === 'infrastructure') {
        // Filter for infrastructure-related nodes and relationships
        const infrastructureTypes = ['server', 'database', 'network', 'service', 'storage', 'cache', 'application', 'component'];
        realGraphData.nodes = realGraphData.nodes.filter(node =>
          infrastructureTypes.includes(node.type.toLowerCase())
        );
        realGraphData.edges = realGraphData.edges.filter(edge =>
          realGraphData.nodes.some(n => n.id === edge.source) &&
          realGraphData.nodes.some(n => n.id === edge.target)
        );
      }

      // Convert edges to links for ForceGraph2D compatibility
      realGraphData.links = realGraphData.edges;

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
      setError('Failed to load graph data. Please ensure the backend services are running.');
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGraphData();
  }, [projectId, viewType]);

  const getNodeColor = (nodeType: string) => {
    const colors: Record<string, string> = {
      Server: '#1c7ed6',
      Application: '#51cf66',
      Database: '#fd7e14',
      Network: '#9775fa',
      Storage: '#ffd43b',
      Security: '#ff6b6b',
      default: '#868e96',
    };
    return colors[nodeType] || colors.default;
  };

  const getFilteredData = () => {
    if (!graphData || selectedNodeType === 'all') {
      return graphData ? {
        ...graphData,
        links: graphData.edges // ForceGraph2D expects 'links' property
      } : null;
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

  const nodeTypes = graphData ? [...new Set(graphData.nodes.map(node => node.type))] : [];

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

  if (!graphData || (graphData && graphData.nodes.length === 0)) {
    return (
      <Card shadow="sm" p="lg" radius="md" withBorder>
        <Group justify="center" p="xl">
          <div style={{ textAlign: 'center' }}>
            <Text size="lg" fw={600} c="blue">
              Infrastructure Dependency Graph
            </Text>
            <Text size="md" c="dimmed" mt="md">
              No infrastructure components found
            </Text>
            <Text size="sm" c="dimmed" mt="xs">
              Upload and analyze documents to see the dependency graph.
              The system will automatically extract infrastructure components and their relationships.
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
          Infrastructure Dependency Graph
        </Text>
        <Group gap="md">
          <Select
            placeholder="Filter by type"
            value={selectedNodeType}
            onChange={(value) => setSelectedNodeType(value || 'all')}
            data={[
              { value: 'all', label: 'All Components' },
              ...nodeTypes.map(type => ({ value: type, label: type })),
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
        <ForceGraph2D
          ref={graphRef}
          graphData={filteredData || undefined}
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
