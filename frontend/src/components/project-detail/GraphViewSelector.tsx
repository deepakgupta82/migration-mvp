/**
 * GraphViewSelector Component
 * 
 * Provides a tab/button interface for switching between different graph visualization views:
 * - Knowledge Graph: General force-directed graph with all entities
 * - Infrastructure: Type-filtered view focusing on infrastructure entities
 * - Platform-Centric: Hierarchical view with Platform → App → Server → Details layers
 * - Document Source: Filter graph by source document
 * - Environment: Group and filter by environment (Dev, Test, Prod)
 */

import React from 'react';
import { Tabs, Group, Text, Badge } from '@mantine/core';
import {
  IconGraph,
  IconServer,
  IconHierarchy,
  IconFileText,
  IconCloud,
} from '@tabler/icons-react';

export type GraphViewType = 
  | 'knowledge-graph' 
  | 'infrastructure' 
  | 'platform-centric' 
  | 'document-source' 
  | 'environment';

interface GraphViewSelectorProps {
  activeView: GraphViewType;
  onViewChange: (view: GraphViewType) => void;
  documentCount?: number;
  environmentCount?: number;
}

export const GraphViewSelector: React.FC<GraphViewSelectorProps> = ({
  activeView,
  onViewChange,
  documentCount = 0,
  environmentCount = 0,
}) => {
  return (
    <Tabs
      value={activeView}
      onChange={(value) => onViewChange(value as GraphViewType)}
      variant="outline"
      styles={{
        root: {
          marginBottom: '1rem',
        },
        tab: {
          fontWeight: 500,
          '&[data-active]': {
            borderColor: '#228be6',
            color: '#228be6',
          },
        },
      }}
    >
      <Tabs.List>
        <Tabs.Tab
          value="knowledge-graph"
          leftSection={<IconGraph size={16} />}
        >
          <Group gap="xs">
            <Text size="sm">Knowledge Graph</Text>
          </Group>
        </Tabs.Tab>

        <Tabs.Tab
          value="infrastructure"
          leftSection={<IconServer size={16} />}
        >
          <Group gap="xs">
            <Text size="sm">Infrastructure</Text>
          </Group>
        </Tabs.Tab>

        <Tabs.Tab
          value="platform-centric"
          leftSection={<IconHierarchy size={16} />}
        >
          <Group gap="xs">
            <Text size="sm">Platform-Centric</Text>
            <Badge size="xs" color="blue" variant="light">
              Hierarchical
            </Badge>
          </Group>
        </Tabs.Tab>

        <Tabs.Tab
          value="document-source"
          leftSection={<IconFileText size={16} />}
        >
          <Group gap="xs">
            <Text size="sm">Document Source</Text>
            {documentCount > 0 && (
              <Badge size="xs" color="grape" variant="light">
                {documentCount}
              </Badge>
            )}
          </Group>
        </Tabs.Tab>

        <Tabs.Tab
          value="environment"
          leftSection={<IconCloud size={16} />}
        >
          <Group gap="xs">
            <Text size="sm">Environment</Text>
            {environmentCount > 0 && (
              <Badge size="xs" color="teal" variant="light">
                {environmentCount}
              </Badge>
            )}
          </Group>
        </Tabs.Tab>
      </Tabs.List>

      {/* Tab panels with descriptions */}
      <Tabs.Panel value="knowledge-graph" pt="md">
        <Text size="sm" c="dimmed">
          View all entities and relationships as an interactive force-directed graph.
          Entities are sized by their connection count.
        </Text>
      </Tabs.Panel>

      <Tabs.Panel value="infrastructure" pt="md">
        <Text size="sm" c="dimmed">
          Focused view of infrastructure entities (servers, platforms, applications, IPs).
          Filters out non-infrastructure nodes for clarity.
        </Text>
      </Tabs.Panel>

      <Tabs.Panel value="platform-centric" pt="md">
        <Text size="sm" c="dimmed">
          Hierarchical visualization with 4 concentric layers: Platforms (center) → Applications → 
          Servers → Details (IP/OS). Useful for understanding platform architecture.
        </Text>
      </Tabs.Panel>

      <Tabs.Panel value="document-source" pt="md">
        <Text size="sm" c="dimmed">
          Filter the graph by source document to trace information back to its origin.
          Select a document to see only entities extracted from that file.
        </Text>
      </Tabs.Panel>

      <Tabs.Panel value="environment" pt="md">
        <Text size="sm" c="dimmed">
          Group entities by environment (Development, Test, Production) with color coding.
          Highlights cross-environment connections for dependency analysis.
        </Text>
      </Tabs.Panel>
    </Tabs>
  );
};

export default GraphViewSelector;
