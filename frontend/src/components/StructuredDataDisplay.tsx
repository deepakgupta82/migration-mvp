import React, { useState, useMemo } from 'react';
import {
  Card,
  Text,
  Group,
  Stack,
  TextInput,
  Badge,
  Paper,
  ScrollArea,
  Divider,
  ThemeIcon,
  Tooltip,
  Button,
  SegmentedControl,
  Box,
  Collapse,
  CopyButton,
  ActionIcon,
  JsonInput,
  Tabs,
} from '@mantine/core';
import {
  IconSearch,
  IconCopy,
  IconDownload,
  IconEye,
  IconEyeOff,
  IconChevronRight,
  IconChevronDown,
  IconBraces,
  IconList,
  IconTable,
  IconCode,
  IconFilter,
} from '@tabler/icons-react';

interface AnalysisResult {
  analysis_id: string;
  project_id: string;
  filename: string;
  analysis_type: string;
  summary?: string;
  categories: string[];
  key_insights: string[];
  structure_analysis?: Record<string, any>;
  content_preview?: string;
  quality_score?: number;
  processing_time: number;
  analysis_timestamp: string;
  metadata?: Record<string, any>;
  versions?: Array<{
    version_number: number;
    created_at: string;
    changes: string[];
  }>;
}

interface StructuredDataDisplayProps {
  analyses: AnalysisResult[];
  showSearch?: boolean;
  showExport?: boolean;
  showComparison?: boolean;
  compact?: boolean;
}

type ViewMode = 'tree' | 'table' | 'raw';

interface TreeNode {
  key: string;
  value: any;
  type: 'object' | 'array' | 'primitive' | 'null';
  path: string[];
  level: number;
  expanded?: boolean;
  children?: TreeNode[];
}

export const StructuredDataDisplay: React.FC<StructuredDataDisplayProps> = ({
  analyses,
  showSearch = true,
  showExport = true,
  showComparison = false,
  compact = false
}) => {
  const [viewMode, setViewMode] = useState<ViewMode>('tree');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedAnalysis, setSelectedAnalysis] = useState<string | null>(null);
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());
  const [filterType, setFilterType] = useState<'all' | 'objects' | 'arrays' | 'primitives'>('all');

  const analysesWithStructure = useMemo(() => {
    return analyses.filter(analysis => analysis.structure_analysis && Object.keys(analysis.structure_analysis).length > 0);
  }, [analyses]);

  const buildTree = (data: any, path: string[] = [], level: number = 0): TreeNode[] => {
    if (!data || typeof data !== 'object') return [];

    const nodes: TreeNode[] = [];

    for (const [key, value] of Object.entries(data)) {
      const currentPath = [...path, key];
      const pathString = currentPath.join('.');

      let type: TreeNode['type'] = 'primitive';
      let children: TreeNode[] | undefined;

      if (value === null) {
        type = 'null';
      } else if (Array.isArray(value)) {
        type = 'array';
        if (value.length > 0 && typeof value[0] === 'object') {
          children = value.slice(0, 3).map((item, index) =>
            buildTree(item, [...currentPath, index.toString()], level + 1)
          ).flat();
        }
      } else if (typeof value === 'object') {
        type = 'object';
        children = buildTree(value, currentPath, level + 1);
      }

      nodes.push({
        key,
        value,
        type,
        path: currentPath,
        level,
        expanded: expandedPaths.has(pathString),
        children
      });
    }

    return nodes;
  };

  const filteredTree = useMemo(() => {
    if (!selectedAnalysis) return [];

    const analysis = analysesWithStructure.find(a => a.analysis_id === selectedAnalysis);
    if (!analysis?.structure_analysis) return [];

    let tree = buildTree(analysis.structure_analysis);

    // Apply search filter
    if (searchTerm) {
      const filterNodes = (nodes: TreeNode[]): TreeNode[] => {
        return nodes.filter(node => {
          const matchesSearch = node.key.toLowerCase().includes(searchTerm.toLowerCase()) ||
                               JSON.stringify(node.value).toLowerCase().includes(searchTerm.toLowerCase());

          if (matchesSearch) return true;

          if (node.children) {
            node.children = filterNodes(node.children);
            return node.children.length > 0;
          }

          return false;
        });
      };
      tree = filterNodes(tree);
    }

    // Apply type filter
    if (filterType !== 'all') {
      const filterByType = (nodes: TreeNode[]): TreeNode[] => {
        return nodes.filter(node => {
          if (filterType === 'objects' && node.type === 'object') return true;
          if (filterType === 'arrays' && node.type === 'array') return true;
          if (filterType === 'primitives' && (node.type === 'primitive' || node.type === 'null')) return true;

          if (node.children) {
            node.children = filterByType(node.children);
            return node.children.length > 0;
          }

          return false;
        });
      };
      tree = filterByType(tree);
    }

    return tree;
  }, [selectedAnalysis, analysesWithStructure, searchTerm, filterType, expandedPaths]);

  const toggleExpanded = (pathString: string) => {
    const newExpanded = new Set(expandedPaths);
    if (newExpanded.has(pathString)) {
      newExpanded.delete(pathString);
    } else {
      newExpanded.add(pathString);
    }
    setExpandedPaths(newExpanded);
  };

  const renderTreeNode = (node: TreeNode): React.ReactNode => {
    const pathString = node.path.join('.');
    const hasChildren = node.children && node.children.length > 0;
    const isExpanded = node.expanded;

    return (
      <div key={pathString} style={{ marginLeft: node.level * 20 }}>
        <Group gap="xs" align="center" mb="xs">
          {hasChildren ? (
            <ActionIcon
              size="sm"
              variant="subtle"
              onClick={() => toggleExpanded(pathString)}
            >
              {isExpanded ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}
            </ActionIcon>
          ) : (
            <Box w={24} />
          )}

          <Badge
            size="xs"
            variant="light"
            color={
              node.type === 'object' ? 'blue' :
              node.type === 'array' ? 'green' :
              node.type === 'null' ? 'gray' : 'orange'
            }
          >
            {node.type}
          </Badge>

          <Text size="sm" fw={500} style={{ minWidth: 120 }}>
            {node.key}:
          </Text>

          {node.type === 'primitive' || node.type === 'null' ? (
            <Text size="sm" c={node.type === 'null' ? 'dimmed' : 'dark'}>
              {node.type === 'null' ? 'null' :
               typeof node.value === 'string' ? `"${node.value}"` :
               String(node.value)}
            </Text>
          ) : (
            <Text size="sm" c="dimmed">
              {node.type === 'object' ? `{${Object.keys(node.value).length} keys}` :
               node.type === 'array' ? `[${node.value.length} items]` : ''}
            </Text>
          )}
        </Group>

        {hasChildren && isExpanded && (
          <div>
            {node.children!.map(child => renderTreeNode(child))}
          </div>
        )}
      </div>
    );
  };

  const exportData = (format: 'json' | 'csv') => {
    if (!selectedAnalysis) return;

    const analysis = analysesWithStructure.find(a => a.analysis_id === selectedAnalysis);
    if (!analysis?.structure_analysis) return;

    if (format === 'json') {
      const dataStr = JSON.stringify(analysis.structure_analysis, null, 2);
      const dataBlob = new Blob([dataStr], { type: 'application/json' });
      const url = URL.createObjectURL(dataBlob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${analysis.filename}_structure.json`;
      link.click();
      URL.revokeObjectURL(url);
    }
  };

  if (!analyses || analyses.length === 0) {
    return (
      <Card p="md" radius="md" withBorder>
        <Text c="dimmed" ta="center">No structured data available</Text>
      </Card>
    );
  }

  if (compact) {
    return (
      <Card p="sm" radius="md" withBorder>
        <Group justify="space-between" align="center">
          <Group gap="xs">
            <ThemeIcon size={32} radius="md" variant="light" color="violet">
              <IconBraces size={18} />
            </ThemeIcon>
            <div>
              <Text size="sm" fw={600}>
                {analysesWithStructure.length} Structured Analyses
              </Text>
              <Text size="xs" c="dimmed">
                Interactive data viewer
              </Text>
            </div>
          </Group>
        </Group>
      </Card>
    );
  }

  return (
    <Stack gap="md">
      {/* Header with Analysis Selector */}
      <Card p="md" radius="md" withBorder>
        <Group justify="space-between" align="center" mb="md">
          <Text size="lg" fw={600}>Structured Data Analysis</Text>
          <Group gap="xs">
            {showExport && selectedAnalysis && (
              <>
                <Button
                  size="xs"
                  variant="light"
                  leftSection={<IconDownload size={14} />}
                  onClick={() => exportData('json')}
                >
                  Export JSON
                </Button>
                <CopyButton value={JSON.stringify(
                  analysesWithStructure.find(a => a.analysis_id === selectedAnalysis)?.structure_analysis || {},
                  null, 2
                )}>
                  {({ copied, copy }) => (
                    <Button
                      size="xs"
                      variant="light"
                      leftSection={<IconCopy size={14} />}
                      onClick={copy}
                      color={copied ? 'green' : 'blue'}
                    >
                      {copied ? 'Copied!' : 'Copy'}
                    </Button>
                  )}
                </CopyButton>
              </>
            )}
          </Group>
        </Group>

        <Group gap="xs" align="center">
          <Text size="sm" fw={500}>Select Analysis:</Text>
          <SegmentedControl
            size="sm"
            value={selectedAnalysis || ''}
            onChange={setSelectedAnalysis}
            data={analysesWithStructure.map(analysis => ({
              label: analysis.filename.length > 20
                ? analysis.filename.substring(0, 20) + '...'
                : analysis.filename,
              value: analysis.analysis_id
            }))}
          />
        </Group>
      </Card>

      {selectedAnalysis && (
        <>
          {/* Controls */}
          <Card p="sm" radius="md" withBorder>
            <Group justify="space-between" align="center">
              <Group gap="xs">
                <SegmentedControl
                  size="xs"
                  value={viewMode}
                  onChange={(value) => setViewMode(value as ViewMode)}
                  data={[
                    { label: 'Tree', value: 'tree' },
                    { label: 'Table', value: 'table' },
                    { label: 'Raw', value: 'raw' },
                  ]}
                />

                {showSearch && (
                  <TextInput
                    size="xs"
                    placeholder="Search..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    leftSection={<IconSearch size={14} />}
                    style={{ width: 200 }}
                  />
                )}

                <SegmentedControl
                  size="xs"
                  value={filterType}
                  onChange={(value) => setFilterType(value as typeof filterType)}
                  data={[
                    { label: 'All', value: 'all' },
                    { label: 'Objects', value: 'objects' },
                    { label: 'Arrays', value: 'arrays' },
                    { label: 'Values', value: 'primitives' },
                  ]}
                />
              </Group>

              <Group gap="xs">
                <Text size="xs" c="dimmed">
                  {filteredTree.length} items
                </Text>
              </Group>
            </Group>
          </Card>

          {/* Content */}
          <Card p="md" radius="md" withBorder>
            <ScrollArea h={600}>
              {viewMode === 'tree' && (
                <div>
                  {filteredTree.length > 0 ? (
                    filteredTree.map(node => renderTreeNode(node))
                  ) : (
                    <Text c="dimmed" ta="center" py="xl">
                      {searchTerm || filterType !== 'all' ? 'No matching data found' : 'No structured data available'}
                    </Text>
                  )}
                </div>
              )}

              {viewMode === 'table' && (
                <div>
                  {filteredTree.length > 0 ? (
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid #e9ecef' }}>
                          <th style={{ padding: '8px', textAlign: 'left', fontWeight: 600 }}>Path</th>
                          <th style={{ padding: '8px', textAlign: 'left', fontWeight: 600 }}>Type</th>
                          <th style={{ padding: '8px', textAlign: 'left', fontWeight: 600 }}>Value</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredTree.map((node, index) => (
                          <tr key={index} style={{ borderBottom: '1px solid #f1f3f4' }}>
                            <td style={{ padding: '8px' }}>
                              <Text size="sm" style={{ fontFamily: 'monospace' }}>
                                {node.path.join('.')}
                              </Text>
                            </td>
                            <td style={{ padding: '8px' }}>
                              <Badge size="xs" variant="light" color={
                                node.type === 'object' ? 'blue' :
                                node.type === 'array' ? 'green' :
                                node.type === 'null' ? 'gray' : 'orange'
                              }>
                                {node.type}
                              </Badge>
                            </td>
                            <td style={{ padding: '8px' }}>
                              <Text size="sm" lineClamp={2}>
                                {node.type === 'primitive' || node.type === 'null' ?
                                  (node.type === 'null' ? 'null' :
                                   typeof node.value === 'string' ? `"${node.value}"` :
                                   String(node.value)) :
                                  (node.type === 'object' ? `{${Object.keys(node.value).length} keys}` :
                                   node.type === 'array' ? `[${node.value.length} items]` : '')
                                }
                              </Text>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <Text c="dimmed" ta="center" py="xl">
                      {searchTerm || filterType !== 'all' ? 'No matching data found' : 'No structured data available'}
                    </Text>
                  )}
                </div>
              )}

              {viewMode === 'raw' && (
                <JsonInput
                  value={JSON.stringify(
                    analysesWithStructure.find(a => a.analysis_id === selectedAnalysis)?.structure_analysis || {},
                    null, 2
                  )}
                  readOnly
                  autosize
                  minRows={20}
                  maxRows={50}
                />
              )}
            </ScrollArea>
          </Card>
        </>
      )}

      {!selectedAnalysis && (
        <Card p="md" radius="md" withBorder>
          <Text c="dimmed" ta="center" py="xl">
            Select an analysis to view its structured data
          </Text>
        </Card>
      )}
    </Stack>
  );
};

export default StructuredDataDisplay;