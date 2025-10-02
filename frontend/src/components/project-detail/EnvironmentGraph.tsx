/**
 * EnvironmentGraph Component
 * 
 * Environment-based graph visualization with:
 * - Environment selector (All, Development, Test, Production, etc.)
 * - Color-coded nodes by environment
 * - Cross-environment connection highlighting
 * - Environment grouping for deployment/migration analysis
 */

import React, { useEffect, useState } from 'react';
import { Alert, Card, Group, Loader, Text, Select, Stack, Badge } from '@mantine/core';
import { IconAlertCircle, IconCloud } from '@tabler/icons-react';
import ForceGraph2D from 'react-force-graph-2d';
import {
  apiService,
  EnvironmentGraphData,
  ProjectEnvironmentsResponse,
  EnvironmentNode,
} from '../../services/api';

interface EnvironmentGraphProps {
  projectId: string;
}

export const EnvironmentGraph: React.FC<EnvironmentGraphProps> = ({ projectId }) => {
  const [environments, setEnvironments] = useState<string[]>([]);
  const [selectedEnvironment, setSelectedEnvironment] = useState<string | null>(null);
  const [graphData, setGraphData] = useState<EnvironmentGraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [graphLoading, setGraphLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadEnvironments = async () => {
      setLoading(true);
      setError(null);
      try {
        const response: ProjectEnvironmentsResponse = await apiService.getProjectEnvironments(projectId);
        setEnvironments(response.environments || []);
        
        // Load graph with no filter (all environments) initially
        const data = await apiService.getEnvironmentGraph(projectId, undefined);
        setGraphData({
          ...data,
          links: data.edges || data.links || [],
        });
      } catch (err: any) {
        console.error('Failed to load environments:', err);
        setError(err.message || 'Failed to load environments');
      } finally {
        setLoading(false);
      }
    };

    loadEnvironments();
  }, [projectId]);

  useEffect(() => {
    const loadGraphForEnvironment = async (environment: string | null) => {
      setGraphLoading(true);
      try {
        const data = await apiService.getEnvironmentGraph(projectId, environment || undefined);
        setGraphData({
          ...data,
          links: data.edges || data.links || [],
        });
      } catch (err: any) {
        console.error('Failed to load environment graph:', err);
        setError(err.message || 'Failed to load graph data');
      } finally {
        setGraphLoading(false);
      }
    };

    if (!loading) {
      loadGraphForEnvironment(selectedEnvironment);
    }
  }, [selectedEnvironment, projectId, loading]);

  // Color palette for environments
  const environmentColors: Record<string, string> = {
    Development: '#51cf66',   // Green
    Test: '#ffd43b',          // Yellow
    Staging: '#ff922b',       // Orange
    Production: '#ff6b6b',    // Red
    Unknown: '#868e96',       // Gray
  };

  const getEnvironmentColor = (env: string | null) => {
    if (!env) return environmentColors.Unknown;
    return environmentColors[env] || environmentColors.Unknown;
  };

  const getNodeColor = (node: EnvironmentNode) => {
    return getEnvironmentColor(node.environment);
  };

  const getNodeSize = (node: EnvironmentNode) => {
    const degree = (node as any).degree || 1;
    // Scale: min 10px, max 35px for better visibility
    return Math.max(10, Math.min(35, 10 + degree * 2));
  };

  // Highlight cross-environment connections
  const getLinkColor = (link: any) => {
    if (!graphData) return 'rgba(200, 200, 200, 0.5)';
    
    // Check if this link is a cross-environment connection
    const isCrossEnv = graphData.cross_environment_connections.some(
      (conn) =>
        (conn.from_node === link.source.id && conn.to_node === link.target.id) ||
        (conn.from_node === link.target.id && conn.to_node === link.source.id)
    );
    
    return isCrossEnv ? '#e03131' : 'rgba(200, 200, 200, 0.5)'; // Red for cross-env, gray for same-env
  };

  const getLinkWidth = (link: any) => {
    if (!graphData) return 1.5;
    
    const isCrossEnv = graphData.cross_environment_connections.some(
      (conn) =>
        (conn.from_node === link.source.id && conn.to_node === link.target.id) ||
        (conn.from_node === link.target.id && conn.to_node === link.source.id)
    );
    
    return isCrossEnv ? 3 : 1.5; // Thicker for cross-env connections
  };

  if (loading) {
    return (
      <Card shadow="sm" padding="lg" radius="md" withBorder>
        <Group justify="center" style={{ minHeight: '400px' }}>
          <Stack align="center" gap="md">
            <Loader size="lg" />
            <Text size="sm" c="dimmed">Loading environments...</Text>
          </Stack>
        </Group>
      </Card>
    );
  }

  if (error && environments.length === 0) {
    return (
      <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red">
        {error}
      </Alert>
    );
  }

  if (environments.length === 0) {
    return (
      <Alert icon={<IconCloud size={16} />} title="No Environments" color="blue">
        No environment information found in the processed documents. 
        Ensure documents contain environment metadata (Dev, Test, Production, etc.).
      </Alert>
    );
  }

  const envOptions = [
    { value: '', label: 'All Environments' },
    ...environments.map((env) => ({ value: env, label: env })),
  ];

  return (
    <Card shadow="sm" padding="lg" radius="md" withBorder>
      {/* Environment Selector */}
      <Group mb="md" align="flex-start">
        <Select
          label="Filter by Environment"
          placeholder="Select environment"
          data={envOptions}
          value={selectedEnvironment || ''}
          onChange={(value) => setSelectedEnvironment(value || null)}
          style={{ flex: 1, minWidth: '250px' }}
        />
        
        <Stack gap="xs" style={{ marginTop: '24px' }}>
          {graphData && graphData.nodes.length > 0 && (
            <Badge color="blue" variant="light">
              {graphData.nodes.length} nodes
            </Badge>
          )}
          {graphData && graphData.cross_environment_connections.length > 0 && (
            <Badge color="red" variant="light">
              {graphData.cross_environment_connections.length} cross-env connections
            </Badge>
          )}
        </Stack>
      </Group>

      {/* Environment Legend */}
      <Group mb="md" gap="sm">
        <Text size="sm" fw={500}>Environments:</Text>
        {environments.map((env) => (
          <Badge key={env} color={getEnvironmentColor(env)} variant="filled">
            {env}
          </Badge>
        ))}
      </Group>

      {/* Graph Loading State */}
      {graphLoading && (
        <Group justify="center" style={{ minHeight: '400px' }}>
          <Stack align="center" gap="md">
            <Loader size="lg" />
            <Text size="sm" c="dimmed">Loading graph...</Text>
          </Stack>
        </Group>
      )}

      {/* Graph Visualization */}
      {!graphLoading && graphData && graphData.nodes.length > 0 && (
        <>
          <div style={{ width: '100%', height: '700px', marginBottom: '1rem', backgroundColor: '#f8f9fa' }}>
            <ForceGraph2D
              graphData={{
                nodes: graphData.nodes,
                links: graphData.links || graphData.edges,
              }}
              nodeLabel={(node: any) => {
                const n = node as EnvironmentNode;
                const env = n.environment || 'Unknown';
                return `${(n as any).name || n.label || n.id}\nType: ${n.type || 'Unknown'}\nEnvironment: ${env}`;
              }}
              nodeColor={(node: any) => getNodeColor(node as EnvironmentNode)}
              nodeVal={(node: any) => getNodeSize(node as EnvironmentNode)}
              linkDirectionalArrowLength={6}
              linkDirectionalArrowRelPos={1}
              linkColor={getLinkColor}
              linkWidth={getLinkWidth}
              d3AlphaDecay={0.01}
              d3VelocityDecay={0.2}
              cooldownTicks={150}
              onNodeClick={(node: any) => {
                console.log('Node clicked:', node);
              }}
              nodeCanvasObject={(node: any, ctx, globalScale) => {
                const n = node as any;
                const label = n.name || n.label || n.id;
                const nodeSize = getNodeSize(node as EnvironmentNode);

                // Draw node with border
                ctx.beginPath();
                ctx.arc(n.x, n.y, nodeSize, 0, 2 * Math.PI);
                ctx.fillStyle = getNodeColor(node as EnvironmentNode);
                ctx.fill();
                ctx.strokeStyle = '#ffffff';
                ctx.lineWidth = 2;
                ctx.stroke();

                // Draw label with background
                if (globalScale >= 0.8) {
                  const fontSize = Math.max(10, 14 / globalScale);
                  ctx.font = `bold ${fontSize}px Arial, Sans-Serif`;
                  ctx.textAlign = 'center';
                  ctx.textBaseline = 'top';
                  
                  const textWidth = ctx.measureText(label).width;
                  const padding = 4;
                  const bgHeight = fontSize + padding * 2;
                  const bgY = n.y + nodeSize + 4;
                  
                  // Background
                  ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
                  ctx.fillRect(n.x - textWidth / 2 - padding, bgY, textWidth + padding * 2, bgHeight);
                  
                  // Border
                  ctx.strokeStyle = 'rgba(0, 0, 0, 0.2)';
                  ctx.lineWidth = 1;
                  ctx.strokeRect(n.x - textWidth / 2 - padding, bgY, textWidth + padding * 2, bgHeight);
                  
                  // Text
                  ctx.fillStyle = '#1a1a1a';
                  ctx.fillText(label, n.x, bgY + padding);
                }
              }}
              enableNodeDrag={true}
              enableZoomInteraction={true}
              enablePanInteraction={true}
            />
          </div>

          <Text size="xs" c="dimmed">
            💡 Tip: Nodes are color-coded by environment. <strong style={{ color: '#e03131' }}>Red connections</strong> indicate 
            cross-environment dependencies. Use this view to identify potential migration risks. Drag nodes to explore.
          </Text>
        </>
      )}

      {!graphLoading && graphData && graphData.nodes.length === 0 && (
        <Alert icon={<IconCloud size={16} />} title="No Entities" color="blue">
          No entities found for the selected environment.
        </Alert>
      )}
    </Card>
  );
};

export default EnvironmentGraph;
