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
}

export const GraphVisualizer: React.FC<GraphVisualizerProps> = ({ projectId }) => {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNodeType, setSelectedNodeType] = useState<string>('all');
  const graphRef = useRef<any>(null);

  const fetchGraphData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Generate mock graph data for demonstration
      // In production, this would call the actual API
      setTimeout(() => {
        const mockGraphData: GraphData = {
          nodes: [
            { id: '1', label: 'Web Server', type: 'server', properties: { group: 1, technology: 'Apache' } },
            { id: '2', label: 'Database', type: 'database', properties: { group: 2, technology: 'PostgreSQL' } },
            { id: '3', label: 'Load Balancer', type: 'network', properties: { group: 3, technology: 'NGINX' } },
            { id: '4', label: 'API Gateway', type: 'service', properties: { group: 1, technology: 'Kong' } },
            { id: '5', label: 'Cache Layer', type: 'cache', properties: { group: 2, technology: 'Redis' } },
            { id: '6', label: 'File Storage', type: 'storage', properties: { group: 3, technology: 'NFS' } },
            { id: '7', label: 'Message Queue', type: 'service', properties: { group: 1, technology: 'RabbitMQ' } },
            { id: '8', label: 'Auth Service', type: 'service', properties: { group: 2, technology: 'OAuth2' } },
          ],
          edges: [
            { source: '3', target: '1', label: 'routes traffic', properties: { protocol: 'HTTP', port: 80 } },
            { source: '1', target: '4', label: 'forwards requests', properties: { protocol: 'HTTP', port: 8080 } },
            { source: '4', target: '2', label: 'queries data', properties: { protocol: 'TCP', port: 5432 } },
            { source: '4', target: '5', label: 'caches results', properties: { protocol: 'TCP', port: 6379 } },
            { source: '1', target: '6', label: 'stores files', properties: { protocol: 'NFS', port: 2049 } },
            { source: '4', target: '7', label: 'sends messages', properties: { protocol: 'AMQP', port: 5672 } },
            { source: '4', target: '8', label: 'authenticates', properties: { protocol: 'HTTPS', port: 443 } },
            { source: '8', target: '2', label: 'validates users', properties: { protocol: 'TCP', port: 5432 } },
          ],
          links: [
            { source: '3', target: '1', label: 'routes traffic', properties: { protocol: 'HTTP', port: 80 } },
            { source: '1', target: '4', label: 'forwards requests', properties: { protocol: 'HTTP', port: 8080 } },
            { source: '4', target: '2', label: 'queries data', properties: { protocol: 'TCP', port: 5432 } },
            { source: '4', target: '5', label: 'caches results', properties: { protocol: 'TCP', port: 6379 } },
            { source: '1', target: '6', label: 'stores files', properties: { protocol: 'NFS', port: 2049 } },
            { source: '4', target: '7', label: 'sends messages', properties: { protocol: 'AMQP', port: 5672 } },
            { source: '4', target: '8', label: 'authenticates', properties: { protocol: 'HTTPS', port: 443 } },
            { source: '8', target: '2', label: 'validates users', properties: { protocol: 'TCP', port: 5432 } },
          ]
        };
        setGraphData(mockGraphData);
        setLoading(false);
      }, 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch graph data');
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGraphData();
  }, [projectId]);

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
