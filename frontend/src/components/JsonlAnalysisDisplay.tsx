import React, { useState, useEffect } from 'react';
import {
  Card,
  Text,
  Group,
  Badge,
  Stack,
  Progress,
  Divider,
  Accordion,
  Code,
  ThemeIcon,
  RingProgress,
  SimpleGrid,
  Paper,
  Alert,
  Button,
} from '@mantine/core';
import {
  IconBrain,
  IconTag,
  IconBulb,
  IconFileText,
  IconClock,
  IconInfoCircle,
  IconCheck,
  IconAlertTriangle,
  IconRefresh,
} from '@tabler/icons-react';
import { useRealtimeAnalysis, type AnalysisProgress, type BatchProgress } from '../hooks/useRealtimeAnalysis.fixed';

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

interface JsonlAnalysisDisplayProps {
  analysis?: AnalysisResult;
  projectId?: string;
  analysisId?: string;
  showMetadata?: boolean;
  compact?: boolean;
  enableRealtime?: boolean;
}

export const JsonlAnalysisDisplay: React.FC<JsonlAnalysisDisplayProps> = ({
  analysis,
  projectId,
  analysisId,
  showMetadata = true,
  compact = false,
  enableRealtime = true
}) => {
  const [expandedSections, setExpandedSections] = useState<string[]>(['summary']);
  const [currentAnalysis, setCurrentAnalysis] = useState<AnalysisResult | undefined>(analysis);
  const [analysisProgress, setAnalysisProgress] = useState<any>(null);
  const [batchProgress, setBatchProgress] = useState<any>(null);

  // Initialize real-time analysis hook if projectId is provided
  const realtimeAnalysis = useRealtimeAnalysis({
    projectId: projectId || '',
    onAnalysisUpdate: (progress: AnalysisProgress) => {
      console.log('Analysis progress update:', progress);
      setAnalysisProgress(progress);
      if (progress.status === 'completed' && progress.analysis_id === analysisId) {
        // Refresh analysis data when completed
        // This would typically trigger a refetch of the analysis data
      }
    },
    onBatchUpdate: (progress: BatchProgress) => {
      console.log('Batch progress update:', progress);
      setBatchProgress(progress);
    },
    onAnalysisComplete: (completedAnalysisId: string, result: any) => {
      console.log('Analysis completed:', completedAnalysisId, result);
      if (result && completedAnalysisId === analysisId) {
        setCurrentAnalysis(result);
      }
    },
    autoConnect: enableRealtime && !!projectId
  });

  // Update current analysis when prop changes
  useEffect(() => {
    setCurrentAnalysis(analysis);
  }, [analysis]);

  const getQualityScoreColor = (score?: number): string => {
    if (!score) return 'gray';
    if (score >= 0.8) return 'green';
    if (score >= 0.6) return 'yellow';
    if (score >= 0.4) return 'orange';
    return 'red';
  };

  const getQualityScoreLabel = (score?: number): string => {
    if (!score) return 'Unknown';
    if (score >= 0.8) return 'Excellent';
    if (score >= 0.6) return 'Good';
    if (score >= 0.4) return 'Fair';
    return 'Poor';
  };

  const formatProcessingTime = (seconds: number): string => {
    if (seconds < 1) return `${(seconds * 1000).toFixed(0)}ms`;
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds.toFixed(1)}s`;
  };

  if (!currentAnalysis) {
    return (
      <Alert icon={<IconInfoCircle size={16} />} color="blue">
        No analysis data available
      </Alert>
    );
  }

  // TypeScript non-null assertion since we checked above
  const analysisData = currentAnalysis!;

  return (
    <Stack gap="md">
      {/* Header */}
      <Group justify="space-between" align="flex-start">
        <div>
          <Group gap="sm" mb="xs">
            <ThemeIcon size={32} radius="md" variant="light" color="blue">
              <IconBrain size={18} />
            </ThemeIcon>
            <div>
              <Text size="lg" fw={600}>{analysisData.filename}</Text>
              <Text size="sm" c="dimmed">
                Analysis ID: {analysisData.analysis_id} • Type: {analysisData.analysis_type}
              </Text>
            </div>
          </Group>
        </div>

        {/* Quality Score */}
        {analysisData.quality_score !== undefined && (
          <Card p="sm" radius="md" withBorder style={{ minWidth: 120 }}>
            <Group gap="xs" justify="center">
              <RingProgress
                size={40}
                thickness={4}
                sections={[
                  {
                    value: analysisData.quality_score * 100,
                    color: getQualityScoreColor(analysisData.quality_score)
                  }
                ]}
                label={
                  <Text  ta="center" fw={600}>
                    {Math.round(analysisData.quality_score * 100)}
                  </Text>
                }
              />
              <div>
                <Text size="sm" fw={600}>
                  {getQualityScoreLabel(analysisData.quality_score)}
                </Text>
                <Text  c="dimmed">Quality Score</Text>
              </div>
            </Group>
          </Card>
        )}
      </Group>

      <Divider />

      {/* Real-time Progress Indicators */}
      {enableRealtime && projectId && (
        <Card p="md" radius="md" withBorder style={{ backgroundColor: '#f8f9fa' }}>
          <Group justify="space-between" align="center" mb="xs">
            <Group gap="xs">
              <ThemeIcon size={24} radius="xl" variant="light" color={realtimeAnalysis.isConnected ? 'green' : 'orange'}>
                {realtimeAnalysis.isConnected ? <IconCheck size={14} /> : <IconRefresh size={14} />}
              </ThemeIcon>
              <Text size="sm" fw={600}>
                Real-time Updates
              </Text>
            </Group>
            <Badge  variant="light" color={realtimeAnalysis.isConnected ? 'green' : 'orange'}>
              {realtimeAnalysis.isConnected ? 'Connected' : 'Disconnected'}
            </Badge>
          </Group>

          {/* Analysis Progress */}
          {analysisProgress && (
            <Stack gap="xs" mt="sm">
              <Group justify="space-between" align="center">
                <Text size="sm" fw={500}>
                  {analysisProgress.current_step || 'Processing...'}
                </Text>
                <Text size="sm" c="dimmed">
                  {analysisProgress.progress_percentage || 0}%
                </Text>
              </Group>
              <Progress
                value={analysisProgress.progress_percentage || 0}
                size="sm"
                color={analysisProgress.status === 'completed' ? 'green' : 'blue'}
              />
              {analysisProgress.message && (
                <Text  c="dimmed">
                  {analysisProgress.message}
                </Text>
              )}
              {analysisProgress.estimated_completion && (
                <Text  c="dimmed">
                  Est. completion: {new Date(analysisProgress.estimated_completion).toLocaleTimeString()}
                </Text>
              )}
            </Stack>
          )}

          {/* Batch Progress */}
          {batchProgress && (
            <Stack gap="xs" mt="sm">
              <Group justify="space-between" align="center">
                <Text size="sm" fw={500}>
                  Batch: {batchProgress.current_file || 'Processing files...'}
                </Text>
                <Text size="sm" c="dimmed">
                  {batchProgress.completed_files || 0}/{batchProgress.total_files || 0}
                </Text>
              </Group>
              <Progress
                value={batchProgress.progress_percentage || 0}
                size="sm"
                color={batchProgress.status === 'completed' ? 'green' : 'blue'}
              />
              {batchProgress.message && (
                <Text  c="dimmed">
                  {batchProgress.message}
                </Text>
              )}
            </Stack>
          )}

          {/* Connection Error */}
          {realtimeAnalysis.connectionError && (
            <Alert icon={<IconAlertTriangle size={16} />} color="orange" mt="xs">
              {realtimeAnalysis.connectionError}
              <Button
                
                variant="light"
                ml="xs"
                onClick={realtimeAnalysis.reconnect}
                leftSection={<IconRefresh size={12} />}
              >
                Reconnect
              </Button>
            </Alert>
          )}
        </Card>
      )}

      <Divider />

      {/* Main Content */}
      <Accordion
        value={expandedSections}
        onChange={setExpandedSections}
        multiple
        variant="separated"
      >
        {/* Summary */}
        {analysisData.summary && (
          <Accordion.Item value="summary">
            <Accordion.Control icon={<IconFileText size={16} />}>
              <Group gap="xs">
                <Text fw={600}>Summary</Text>
                <Badge  variant="light" color="blue">
                  {analysisData.summary.length} chars
                </Badge>
              </Group>
            </Accordion.Control>
            <Accordion.Panel>
              <Text size="sm" style={{ lineHeight: 1.6 }}>
                {analysisData.summary}
              </Text>
            </Accordion.Panel>
          </Accordion.Item>
        )}

        {/* Categories */}
        {analysisData.categories && analysisData.categories.length > 0 && (
          <Accordion.Item value="categories">
            <Accordion.Control icon={<IconTag size={16} />}>
              <Group gap="xs">
                <Text fw={600}>Categories</Text>
                <Badge  variant="light" color="orange">
                  {analysisData.categories.length}
                </Badge>
              </Group>
            </Accordion.Control>
            <Accordion.Panel>
              <Group gap="xs" wrap="wrap">
                {analysisData.categories.map((category, index) => (
                  <Badge
                    key={index}
                    variant="light"
                    color="orange"
                    size="sm"
                  >
                    {category}
                  </Badge>
                ))}
              </Group>
            </Accordion.Panel>
          </Accordion.Item>
        )}

        {/* Key Insights */}
        {analysisData.key_insights && analysisData.key_insights.length > 0 && (
          <Accordion.Item value="insights">
            <Accordion.Control icon={<IconBulb size={16} />}>
              <Group gap="xs">
                <Text fw={600}>Key Insights</Text>
                <Badge  variant="light" color="green">
                  {analysisData.key_insights.length}
                </Badge>
              </Group>
            </Accordion.Control>
            <Accordion.Panel>
              <Stack gap="sm">
                {analysisData.key_insights.map((insight, index) => (
                  <Group key={index} gap="xs" align="flex-start">
                    <ThemeIcon size={20} radius="xl" variant="light" color="green">
                      <IconCheck size={12} />
                    </ThemeIcon>
                    <Text size="sm" style={{ flex: 1, lineHeight: 1.5 }}>
                      {insight}
                    </Text>
                  </Group>
                ))}
              </Stack>
            </Accordion.Panel>
          </Accordion.Item>
        )}

        {/* Structure Analysis */}
        {analysisData.structure_analysis && (
          <Accordion.Item value="structure">
            <Accordion.Control icon={<IconInfoCircle size={16} />}>
              <Group gap="xs">
                <Text fw={600}>Structure Analysis</Text>
                <Badge  variant="light" color="violet">
                  JSON
                </Badge>
              </Group>
            </Accordion.Control>
            <Accordion.Panel>
              <Code block style={{ fontSize: '12px', maxHeight: '300px', overflow: 'auto' }}>
                {JSON.stringify(analysisData.structure_analysis, null, 2)}
              </Code>
            </Accordion.Panel>
          </Accordion.Item>
        )}

        {/* Content Preview */}
        {analysisData.content_preview && (
          <Accordion.Item value="preview">
            <Accordion.Control icon={<IconFileText size={16} />}>
              <Group gap="xs">
                <Text fw={600}>Content Preview</Text>
                <Badge  variant="light" color="gray">
                  {analysisData.content_preview.length} chars
                </Badge>
              </Group>
            </Accordion.Control>
            <Accordion.Panel>
              <Paper p="sm" withBorder style={{ backgroundColor: '#f8f9fa' }}>
                <Text size="sm" style={{ fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
                  {analysisData.content_preview}
                </Text>
              </Paper>
            </Accordion.Panel>
          </Accordion.Item>
        )}

        {/* Versions */}
        {analysisData.versions && analysisData.versions.length > 1 && (
          <Accordion.Item value="versions">
            <Accordion.Control icon={<IconClock size={16} />}>
              <Group gap="xs">
                <Text fw={600}>Version History</Text>
                <Badge  variant="light" color="blue">
                  {analysisData.versions.length} versions
                </Badge>
              </Group>
            </Accordion.Control>
            <Accordion.Panel>
              <Stack gap="xs">
                {analysisData.versions.map((version) => (
                  <Card key={version.version_number} p="xs" withBorder>
                    <Group justify="space-between" align="center">
                      <div>
                        <Text size="sm" fw={600}>
                          Version {version.version_number}
                        </Text>
                        <Text  c="dimmed">
                          {new Date(version.created_at).toLocaleString()}
                        </Text>
                      </div>
                      <Badge  variant="light" color="blue">
                        {version.changes.length} changes
                      </Badge>
                    </Group>
                    {version.changes.length > 0 && (
                      <Text  c="dimmed" mt="xs">
                        Changes: {version.changes.join(', ')}
                      </Text>
                    )}
                  </Card>
                ))}
              </Stack>
            </Accordion.Panel>
          </Accordion.Item>
        )}
      </Accordion>

      {/* Metadata */}
      {showMetadata && (
        <>
          <Divider />
          <SimpleGrid cols={3} spacing="md">
            <Group gap="xs">
              <IconClock size={16} />
              <div>
                <Text  c="dimmed" tt="uppercase" fw={600}>
                  Processing Time
                </Text>
                <Text size="sm" fw={500}>
                  {formatProcessingTime(analysisData.processing_time)}
                </Text>
              </div>
            </Group>

            <Group gap="xs">
              <IconClock size={16} />
              <div>
                <Text  c="dimmed" tt="uppercase" fw={600}>
                  Analysis Date
                </Text>
                <Text size="sm" fw={500}>
                  {new Date(analysisData.analysis_timestamp).toLocaleString()}
                </Text>
              </div>
            </Group>

            {analysisData.metadata && Object.keys(analysisData.metadata).length > 0 && (
              <Group gap="xs">
                <IconInfoCircle size={16} />
                <div>
                  <Text  c="dimmed" tt="uppercase" fw={600}>
                    Metadata
                  </Text>
                  <Text size="sm" fw={500}>
                    {Object.keys(analysisData.metadata).length} fields
                  </Text>
                </div>
              </Group>
            )}
          </SimpleGrid>
        </>
      )}
    </Stack>
  );
};

export default JsonlAnalysisDisplay;