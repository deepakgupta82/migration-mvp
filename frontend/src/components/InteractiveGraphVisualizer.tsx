/**
 * Interactive Graph Visualizer Component
 * Displays knowledge graphs using react-force-graph-2d library
 */

import React, { useEffect, useRef, useState, useCallback, Suspense, lazy } from 'react';
import {
  Card,
  Text,
  Group,
  Button,
  Loader,
  Alert,
  Stack,
  Select,
  Switch,
  ActionIcon,
  Tooltip,
  Badge,
} from '@mantine/core';
import {
  IconRefresh,
  IconZoomIn,
  IconZoomOut,
  IconMaximize,
  IconMinimize,
  IconFocus,
  IconSettings,
  IconAlertCircle,
} from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';

// Lazy load ForceGraph2D to avoid SSR issues
const ForceGraph2D = lazy(() => import('react-force-graph-2d'));

// Types
interface GraphNode {
  id: string;
  label: string;
  name?: string;
  title?: string;
  group?: string;
  value?: number;
  color?: string;
  shape?: string;
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
}

interface GraphEdge {
  source: string;
  target: string;
  label?: string;
  title?: string;
  value?: number;
  color?: string;
}

interface ForceGraphData {
  nodes: GraphNode[];
  links: GraphEdge[];
}

interface InteractiveGraphVisualizerProps {
  projectId: string;
  height?: string;
  showControls?: boolean;
}

const InteractiveGraphVisualizer: React.FC<InteractiveGraphVisualizerProps> = ({
  projectId,
  height = '600px',
  showControls = true,
}) => {
  const fgRef = useRef<any>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [graphData, setGraphData] = useState<ForceGraphData | null>(null);
  const [physicsEnabled, setPhysicsEnabled] = useState(true);
  const [nodeFilter, setNodeFilter] = useState<string>('all');
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  // Safely transform and sanitize backend graph to ForceGraph format
  const transformToForceGraph = (data: any): ForceGraphData => {
    const rawNodes = Array.isArray(data?.nodes) ? data.nodes : [];
    const rawEdges = Array.isArray(data?.edges) ? data.edges : [];

    // Build map of node ids used by backend (id/name) to display id
    const idToDisplay = new Map<string, string>();
    const nodes: GraphNode[] = rawNodes.map((node: any) => {
      const idBase = node?.id ?? node?.node_id ?? node?.name ?? node?.label ?? '';
      const id = String(idBase);
      const display = String(node?.label ?? node?.name ?? id);
      idToDisplay.set(id, display);
      return {
        ...node,
        id: display,
        name: node?.label ?? node?.name ?? display,
        val: node?.value || 1,
      } as GraphNode;
    });

    // Normalize links and drop any invalid ones
    const links: GraphEdge[] = rawEdges
      .map((edge: any) => {
        const srcRaw = edge?.from ?? edge?.source ?? edge?.source_id ?? '';
        const tgtRaw = edge?.to ?? edge?.target ?? edge?.target_id ?? '';
        const srcId = String(srcRaw);
        const tgtId = String(tgtRaw);
        const source = idToDisplay.get(srcId) ?? (typeof srcRaw === 'string' ? srcRaw : '');
        const target = idToDisplay.get(tgtId) ?? (typeof tgtRaw === 'string' ? tgtRaw : '');
        return {
          ...edge,
          source,
          target,
          label: edge?.label ?? edge?.name,
          color: edge?.color,
          value: edge?.value,
        } as GraphEdge;
      })
      .filter((e: GraphEdge) => Boolean(e.source) && Boolean(e.target));

    // Ensure links reference existing nodes only
    const validIds = new Set(nodes.map(n => n.id));
    const safeLinks = links.filter(l => validIds.has(l.source) && validIds.has(l.target));

    return { nodes, links: safeLinks } as ForceGraphData;
  };

  // Load graph data
  const loadGraphData = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`http://localhost:8000/api/projects/${projectId}/graph/vis-network`);

      if (!response.ok) {
        throw new Error(`Failed to load graph data: ${response.status}`);
      }

      const data = await response.json();
      const transformedData = transformToForceGraph(data);
      setGraphData(transformedData);

    } catch (err: any) {
      setError(err.message);
      notifications.show({
        title: 'Error',
        message: 'Failed to load graph data',
        color: 'red',
        icon: <IconAlertCircle size={16} />
      });
    } finally {
      setLoading(false);
    }
  };

  // Node color function
  const getNodeColor = useCallback((node: any) => {
    const groupColors: { [key: string]: string } = {
      entity: '#1976d2',
      concept: '#7b1fa2',
      document: '#388e3c',
      default: '#666666'
    };
    return groupColors[node.group] || groupColors.default;
  }, []);

  // Node size function
  const getNodeSize = useCallback((node: any) => {
    return Math.sqrt(node.val || 1) * 6;
  }, []);

  // Control functions
  const zoomIn = () => {
    if (fgRef.current) {
      fgRef.current.zoom(1.5, 400);
    }
  };

  const zoomOut = () => {
    if (fgRef.current) {
      fgRef.current.zoom(0.67, 400);
    }
  };

  const fitToScreen = () => {
    if (fgRef.current) {
      fgRef.current.zoomToFit(400);
    }
  };

  const centerGraph = () => {
    if (fgRef.current) {
      fgRef.current.centerAt(0, 0, 400);
    }
  };

  // Filter nodes
  const applyNodeFilter = (filter: string) => {
    setNodeFilter(filter);
    // Filtering would require re-processing the data
    // For now, just update the state
  };

  // Node click handler
  const handleNodeClick = useCallback((node: any) => {
    setSelectedNode(node);
    notifications.show({
      title: node.name || node.label,
      message: node.title || 'Click to view details',
      autoClose: 3000,
    });
  }, []);

  // Effect to load data on mount
  useEffect(() => {
    loadGraphData();
  }, [projectId]);

  return (
    <Card withBorder shadow="sm">
      <Stack gap="md">
        {/* Header */}
        <Group justify="space-between">
          <div>
            <Text size="lg" fw={600}>Knowledge Graph Visualization</Text>
            <Text size="sm" c="dimmed">
              Interactive visualization of project knowledge graph
            </Text>
          </div>

          {showControls && (
            <Group gap="xs">
              <Tooltip label="Refresh Graph">
                <ActionIcon
                  variant="light"
                  color="blue"
                  onClick={loadGraphData}
                  loading={loading}
                >
                  <IconRefresh size={16} />
                </ActionIcon>
              </Tooltip>

              <Tooltip label="Zoom In">
                <ActionIcon variant="light" onClick={zoomIn}>
                  <IconZoomIn size={16} />
                </ActionIcon>
              </Tooltip>

              <Tooltip label="Zoom Out">
                <ActionIcon variant="light" onClick={zoomOut}>
                  <IconZoomOut size={16} />
                </ActionIcon>
              </Tooltip>

              <Tooltip label="Fit to Screen">
                <ActionIcon variant="light" onClick={fitToScreen}>
                  <IconMaximize size={16} />
                </ActionIcon>
              </Tooltip>

              <Tooltip label="Center Graph">
                <ActionIcon variant="light" onClick={centerGraph}>
                  <IconFocus size={16} />
                </ActionIcon>
              </Tooltip>
            </Group>
          )}
        </Group>

        {/* Controls */}
        {showControls && (
          <Group gap="md">
            <Select
              placeholder="Filter Nodes"
              value={nodeFilter}
              onChange={(value) => applyNodeFilter(value || 'all')}
              data={[
                { value: 'all', label: 'All Nodes' },
                { value: 'entities', label: 'Entities Only' },
                { value: 'concepts', label: 'Concepts Only' },
                { value: 'documents', label: 'Documents Only' },
              ]}
              style={{ width: 150 }}
            />

            <Switch
              label="Physics"
              checked={physicsEnabled}
              onChange={(event) => setPhysicsEnabled(event.currentTarget.checked)}
            />
          </Group>
        )}

        {/* Graph Statistics */}
        {graphData && (
          <Group gap="lg">
            <Badge color="blue" variant="light">
              {graphData.nodes.length} Nodes
            </Badge>
            <Badge color="green" variant="light">
              {graphData.links.length} Relationships
            </Badge>
            <Badge color="purple" variant="light">
              {new Set(graphData.nodes.map((n: GraphNode) => n.group)).size} Types
            </Badge>
          </Group>
        )}

        {/* Selected Node Info */}
        {selectedNode && (
          <Alert color="blue" variant="light">
            <Group>
              <Text fw={500}>Selected: {selectedNode.name || selectedNode.label}</Text>
              {selectedNode.group && (
                <Badge size="sm" color="blue">{selectedNode.group}</Badge>
              )}
            </Group>
            {selectedNode.title && (
              <Text size="sm" mt="xs">{selectedNode.title}</Text>
            )}
          </Alert>
        )}

        {/* Graph Container */}
        <div
          style={{
            height,
            border: '1px solid #e9ecef',
            borderRadius: '8px',
            backgroundColor: '#fafafa',
            position: 'relative',
          }}
        >
          {loading && (
            <Group justify="center" align="center" style={{ height: '100%' }}>
              <Stack align="center" gap="sm">
                <Loader size="lg" />
                <Text size="sm" c="dimmed">Loading graph data...</Text>
              </Stack>
            </Group>
          )}

          {error && (
            <Alert icon={<IconAlertCircle size={16} />} color="red" style={{ margin: '20px' }}>
              <Text size="sm">{error}</Text>
              <Button
                size="xs"
                variant="light"
                color="red"
                mt="xs"
                onClick={loadGraphData}
              >
                Retry
              </Button>
            </Alert>
          )}

          {!loading && !error && graphData && (
            <Suspense fallback={<Loader size="lg" />}>
              <ForceGraph2D
                ref={fgRef}
                graphData={graphData}
                nodeColor={getNodeColor}
                nodeVal={getNodeSize}
                nodeLabel={(node: any) => `${node.name || node.label}${node.title ? `\n${node.title}` : ''}`}
                linkColor={() => '#999999'}
                linkWidth={(link: any) => Math.sqrt(link.value || 1)}
                linkLabel={(link: any) => link.name || link.label}
                onNodeClick={handleNodeClick}
                cooldownTicks={physicsEnabled ? 100 : 0}
                d3AlphaDecay={physicsEnabled ? 0.02 : 1}
                d3VelocityDecay={physicsEnabled ? 0.3 : 1}
                width={parseInt(height.replace('px', '')) * 1.5 || 800}
                height={parseInt(height.replace('px', '')) || 600}
                enableNodeDrag={true}
                enableZoomInteraction={true}
              />
            </Suspense>
          )}

          {!loading && !error && !graphData && (
            <Group justify="center" align="center" style={{ height: '100%' }}>
              <Stack align="center" gap="sm">
                <IconAlertCircle size={48} color="#868e96" />
                <Text size="sm" c="dimmed">No graph data available</Text>
                <Button size="sm" variant="light" onClick={loadGraphData}>
                  Load Graph
                </Button>
              </Stack>
            </Group>
          )}
        </div>

        {/* Instructions */}
        <Alert color="blue" variant="light">
          <Text size="sm">
            <strong>Graph Controls:</strong> Click and drag to pan • Scroll to zoom •
            Click nodes for details • Use controls above for additional options
          </Text>
        </Alert>
      </Stack>
    </Card>
  );
};

export default InteractiveGraphVisualizer;