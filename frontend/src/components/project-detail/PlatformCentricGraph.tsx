/**
 * PlatformCentricGraph Component
 * 
 * Hierarchical visualization with concentric layout showing:
 * - Layer 0 (Center): Platforms
 * - Layer 1: Applications connected to Platforms
 * - Layer 2: Servers connected to Applications
 * - Layer 3 (Outer): Details (IP addresses, OS) connected to Servers
 * 
 * Uses ForceGraph2D with custom node positioning based on hierarchy_level.
 */

import React, { useEffect, useRef, useState } from 'react';
import { Alert, Card, Group, Loader, Text, Badge, Stack } from '@mantine/core';
import { IconAlertCircle, IconHierarchy } from '@tabler/icons-react';
import ForceGraph2D from 'react-force-graph-2d';
import { apiService, PlatformCentricGraphData, PlatformCentricNode } from '../../services/api';

interface PlatformCentricGraphProps {
  projectId: string;
}

interface GraphNodeWithPosition extends PlatformCentricNode {
  x?: number;
  y?: number;
  fx?: number;
  fy?: number;
}

export const PlatformCentricGraph: React.FC<PlatformCentricGraphProps> = ({ projectId }) => {
  const [graphData, setGraphData] = useState<PlatformCentricGraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const fgRef = useRef<any>(null);

  useEffect(() => {
    const loadGraphData = async () => {
      setLoading(true);
      setError(null);
      try {
        let data;
        try {
          // Try platform-centric endpoint first
          data = await apiService.getPlatformCentricGraph(projectId);
        } catch (platformError) {
          console.warn('Platform-centric endpoint failed, falling back to PyVis:', platformError);
          // Fallback to PyVis and filter for platform-related nodes
          const pyvisData = await apiService.getPyvisGraph(projectId);
          
          // Convert PyVis data to platform-centric format
          const platformTypes = new Set(['Platform', 'Application', 'App', 'Server', 'Database', 'DB']);
          const filteredNodes = pyvisData.nodes
            .filter(n => platformTypes.has(n.group || ''))
            .map((n, idx) => ({
              id: n.id,
              label: n.label || n.id,
              type: n.group || 'Unknown',
              properties: n,
              layer_type: n.group as any,
              hierarchy_level: n.group === 'Platform' ? 0 : n.group === 'Application' || n.group === 'App' ? 1 : n.group === 'Server' ? 2 : 3
            })) as PlatformCentricNode[];
          
          const nodeIds = new Set(filteredNodes.map(n => n.id));
          const filteredEdges = pyvisData.edges
            .filter(e => nodeIds.has(e.from) && nodeIds.has(e.to))
            .map(e => ({
              source: e.from,
              target: e.to,
              label: e.label || 'CONNECTS',
              properties: e
            }));
          
          data = {
            project_id: projectId,
            view_type: 'platform-centric' as const,
            layers: {
              platforms: filteredNodes.filter(n => n.hierarchy_level === 0),
              applications: filteredNodes.filter(n => n.hierarchy_level === 1),
              servers: filteredNodes.filter(n => n.hierarchy_level === 2),
              details: filteredNodes.filter(n => n.hierarchy_level === 3)
            },
            nodes: filteredNodes,
            edges: filteredEdges,
            links: filteredEdges
          };
        }
        
        // Transform layers from array to object structure expected by interface
        const layersObject = data.layers && Array.isArray(data.layers) ? {
          platforms: data.layers.find((l: any) => l.name === 'Platform')?.nodes || [],
          applications: data.layers.find((l: any) => l.name === 'Application')?.nodes || [],
          servers: data.layers.find((l: any) => l.name === 'Server')?.nodes || [],
          details: data.layers.find((l: any) => l.name === 'Details')?.nodes || [],
        } : data.layers || {
          platforms: [],
          applications: [],
          servers: [],
          details: [],
        };
        
        // Position nodes in concentric circles based on hierarchy_level
        const positionedNodes = positionNodesConcentrically(data.nodes);
        
        setGraphData({
          ...data,
          nodes: positionedNodes,
          layers: layersObject,
          links: data.edges || data.links || [],
        });
      } catch (err: any) {
        console.error('Failed to load platform-centric graph:', err);
        setError(err.message || 'Failed to load graph data');
      } finally {
        setLoading(false);
      }
    };

    loadGraphData();
  }, [projectId]);

  /**
   * Position nodes in concentric circles based on hierarchy_level
   * Level 0 (Platforms) at center, Level 3 (Details) at outer ring
   */
  const positionNodesConcentrically = (nodes: PlatformCentricNode[]): GraphNodeWithPosition[] => {
    const positioned: GraphNodeWithPosition[] = [];
    
    // Group nodes by hierarchy level
    const levels: Record<number, PlatformCentricNode[]> = { 0: [], 1: [], 2: [], 3: [] };
    nodes.forEach((node) => {
      const level = node.hierarchy_level ?? 0;
      if (level >= 0 && level <= 3) {
        levels[level].push(node);
      }
    });

    // Radii for each concentric circle (in pixels) - increased spacing for better readability
    const radii = [80, 280, 520, 800];
    
    // Position each level in a circle
    Object.keys(levels).forEach((levelKey) => {
      const level = parseInt(levelKey, 10);
      const nodesInLevel = levels[level];
      const radius = radii[level];
      const angleStep = (2 * Math.PI) / (nodesInLevel.length || 1);
      
      nodesInLevel.forEach((node, index) => {
        const angle = index * angleStep;
        const x = radius * Math.cos(angle);
        const y = radius * Math.sin(angle);
        
        positioned.push({
          ...node,
          x,
          y,
          fx: radius > 0 ? x : undefined, // Fix position for outer layers
          fy: radius > 0 ? y : undefined,
        });
      });
    });

    return positioned;
  };

  // Node color based on layer type
  const getNodeColor = (node: PlatformCentricNode) => {
    const colorMap = {
      Platform: '#ff6b6b',     // Red for platforms
      Application: '#4dabf7',  // Blue for applications
      Server: '#51cf66',       // Green for servers
      Details: '#ffd43b',      // Yellow for details
    };
    return colorMap[node.layer_type] || '#868e96';
  };

  // Node size based on degree (connection count) - significantly larger for better visibility
  const getNodeSize = (node: PlatformCentricNode) => {
    const degree = (node as any).degree || 1;
    // Scale: min 10px, max 35px based on connection count
    return Math.max(10, Math.min(35, 10 + degree * 2));
  };

  if (loading) {
    return (
      <Card shadow="sm" padding="lg" radius="md" withBorder>
        <Group justify="center" style={{ minHeight: '400px' }}>
          <Stack align="center" gap="md">
            <Loader size="lg" />
            <Text size="sm" c="dimmed">Loading platform-centric view...</Text>
          </Stack>
        </Group>
      </Card>
    );
  }

  if (error) {
    return (
      <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red">
        {error}
      </Alert>
    );
  }

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <Alert icon={<IconHierarchy size={16} />} title="No Data" color="blue">
        No platform-centric graph data available for this project. 
        Process documents to build the knowledge graph.
      </Alert>
    );
  }

  const { layers } = graphData;

  return (
    <Card shadow="sm" padding="lg" radius="md" withBorder>
      {/* Legend */}
      <Group mb="md" justify="space-between">
        <Group gap="sm">
          <Text size="sm" fw={500}>Layers:</Text>
          <Badge color="red" variant="light">
            Platforms: {layers.platforms.length}
          </Badge>
          <Badge color="blue" variant="light">
            Applications: {layers.applications.length}
          </Badge>
          <Badge color="green" variant="light">
            Servers: {layers.servers.length}
          </Badge>
          <Badge color="yellow" variant="light">
            Details: {layers.details.length}
          </Badge>
        </Group>
        <Text size="xs" c="dimmed">
          {graphData.nodes.length} nodes, {graphData.edges.length} connections
        </Text>
      </Group>

      {/* Graph Visualization */}
      <div ref={containerRef} style={{ width: '100%', height: '700px', backgroundColor: '#f8f9fa' }}>
        <ForceGraph2D
          ref={fgRef}
          graphData={{
            nodes: graphData.nodes,
            links: graphData.links || graphData.edges,
          }}
          nodeLabel={(node: any) => {
            const n = node as PlatformCentricNode;
            return `${(n as any).name || n.label || n.id}\nType: ${n.type || 'Unknown'}\nLayer: ${n.layer_type}\nLevel: ${n.hierarchy_level}`;
          }}
          nodeColor={(node: any) => getNodeColor(node as PlatformCentricNode)}
          nodeVal={(node: any) => getNodeSize(node as PlatformCentricNode)}
          linkDirectionalArrowLength={6}
          linkDirectionalArrowRelPos={1}
          linkColor={() => 'rgba(200, 200, 200, 0.5)'}
          linkWidth={1.5}
          d3AlphaDecay={0.01}
          d3VelocityDecay={0.2}
          cooldownTicks={150}
          onNodeClick={(node: any) => {
            console.log('Node clicked:', node);
          }}
          nodeCanvasObject={(node: any, ctx, globalScale) => {
            const n = node as any;
            const label = n.name || n.label || n.id;
            const nodeSize = getNodeSize(node as PlatformCentricNode);

            // Draw node circle with border
            ctx.beginPath();
            ctx.arc(n.x, n.y, nodeSize, 0, 2 * Math.PI);
            ctx.fillStyle = getNodeColor(node as PlatformCentricNode);
            ctx.fill();
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 2;
            ctx.stroke();

            // Draw label with background for readability
            if (globalScale >= 0.8) { // Show labels at moderate zoom
              const fontSize = Math.max(10, 14 / globalScale);
              ctx.font = `bold ${fontSize}px Arial, Sans-Serif`;
              ctx.textAlign = 'center';
              ctx.textBaseline = 'top';
              
              // Measure text width for background
              const textWidth = ctx.measureText(label).width;
              const padding = 4;
              const bgHeight = fontSize + padding * 2;
              const bgY = n.y + nodeSize + 4;
              
              // Draw semi-transparent background for label
              ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
              ctx.fillRect(
                n.x - textWidth / 2 - padding, 
                bgY, 
                textWidth + padding * 2, 
                bgHeight
              );
              
              // Draw border around label
              ctx.strokeStyle = 'rgba(0, 0, 0, 0.2)';
              ctx.lineWidth = 1;
              ctx.strokeRect(
                n.x - textWidth / 2 - padding, 
                bgY, 
                textWidth + padding * 2, 
                bgHeight
              );
              
              // Draw text
              ctx.fillStyle = '#1a1a1a';
              ctx.fillText(label, n.x, bgY + padding);
            }
          }}
          enableNodeDrag={true}
          enableZoomInteraction={true}
          enablePanInteraction={true}
        />
      </div>

      <Text size="xs" c="dimmed" mt="md">
        💡 Tip: Center nodes are Platforms (Layer 0), outer rings show Applications → Servers → Details.
        Drag nodes to explore connections. Use mouse wheel to zoom.
      </Text>
    </Card>
  );
};

export default PlatformCentricGraph;
