/**
 * Interactive Graph Visualizer (PyVis-style data rendered via ForceGraph2D)
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Card, Text, Loader, Alert, Group, ActionIcon, Switch, Badge, Stack } from '@mantine/core';
import { IconAlertCircle, IconRefresh, IconZoomIn } from '@tabler/icons-react';
import ForceGraph2D from 'react-force-graph-2d';
import { apiService, PyvisGraphData } from '../../services/api';

interface InteractiveGraphVisualizerProps {
  projectId: string;
}

type FGNode = { id: string; label?: string; group?: string; title?: string; type?: string; value?: number };
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
  const links: FGEdge[] = (res.edges || []).map((e) => ({ source: e.from, target: e.to, label: e.label, title: (e as any).title, dashes: (e as any).dashes, value: (e as any).value }));
      setData({ nodes, links });
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
      <Card shadow="sm" p="lg" radius="md" withBorder>
        <Group justify="center" p="xl">
          <Loader size="lg" />
          <Text>Loading interactive graph...</Text>
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

  if (!data || !data.nodes || data.nodes.length === 0) {
    return (
      <Card shadow="sm" p="lg" radius="md" withBorder>
        <Group justify="center" p="xl">
          <div style={{ textAlign: 'center' }}>
            <Text size="lg" fw={600} c="blue">Interactive Graph</Text>
            <Text size="md" c="dimmed" mt="md">No nodes available</Text>
            <Text size="sm" c="dimmed" mt="xs">Upload and process documents to build the graph</Text>
          </div>
        </Group>
      </Card>
    );
  }

  const displayedLinks = useMemo(() => {
    if (!data) return [] as FGEdge[];
    return (data.links || []).filter((l) => showInferred || !l.dashes);
  }, [data, showInferred]);

  const Legend = () => (
    <Group gap="sm" wrap="wrap">
      <Badge color="blue" variant="light">Server</Badge>
      <Badge color="green" variant="light">Application</Badge>
      <Badge color="orange" variant="light">Database</Badge>
      <Badge color="grape" variant="light">Technology</Badge>
      <Badge color="teal" variant="light">Service</Badge>
      <Badge color="gray" variant="outline">Inferred edge = dashed</Badge>
    </Group>
  );

  return (
    <Card shadow="sm" p="lg" radius="md" withBorder>
      <Group justify="space-between" mb="md">
        <Text size="lg" fw={600}>Interactive Graph (New)</Text>
        <Group gap="md">
          <Switch
            size="sm"
            checked={showInferred}
            onChange={(e) => setShowInferred(e.currentTarget.checked)}
            onLabel="Inferred on"
            offLabel="Inferred off"
            thumbIcon={null}
          />
          <ActionIcon variant="subtle" onClick={() => graphRef.current?.zoomToFit(400)}>
            <IconZoomIn size={16} />
          </ActionIcon>
          <ActionIcon variant="subtle" onClick={load}>
            <IconRefresh size={16} />
          </ActionIcon>
        </Group>
      </Group>

      <Stack gap={6} mb="sm">
        <Legend />
        <Text size="xs" c="dimmed">Nodes sized by degree; hover edges for details. Toggle hides dashed inferred edges.</Text>
      </Stack>

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
          linkDirectionalParticles={(l: any) => (l.dashes ? 2 : 0)}
          linkDirectionalArrowLength={6}
          linkDirectionalArrowRelPos={1}
          onNodeClick={(node: any) => console.log('Node clicked:', node)}
          onLinkClick={(link: any) => console.log('Link clicked:', link)}
          cooldownTicks={100}
          onEngineStop={() => graphRef.current?.zoomToFit(400)}
          nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
            const label = node.label || node.id;
            const fontSize = 12 / globalScale;
            ctx.font = `${fontSize}px Sans-Serif`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = '#333';
            ctx.fillText(label, node.x, node.y + 15);
          }}
        />
      </div>
    </Card>
  );
};

export default InteractiveGraphVisualizer;
