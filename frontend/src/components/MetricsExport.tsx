/**
 * Metrics Export Component
 * Provides UI for exporting analytics data in various formats
 */

import React, { useState } from 'react';
import {
  Card,
  Text,
  Group,
  Stack,
  Button,
  Select,
  Checkbox,
  TextInput,
  Alert,
  Progress,
  Badge,
  Paper,
  Divider,
  ActionIcon,
  Tooltip
} from '@mantine/core';
import {
  IconDownload,
  IconFileText,
  IconTable,
  IconCode,
  IconFile,
  IconCheck,
  IconX,
  IconInfoCircle,
  IconAlertTriangle
} from '@tabler/icons-react';
import { MetricsExporter, downloadExport, exportMultipleFormats, ExportResult } from '../utils/metricsExport';
import { TimeRange } from '../types/metrics';

interface MetricsExportProps {
  projectId?: string;
  availableFormats?: ('json' | 'csv' | 'xml' | 'pdf')[];
  showAdvanced?: boolean;
}

interface ExportJob {
  id: string;
  format: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  result?: ExportResult;
  error?: string;
  startTime: number;
  endTime?: number;
}

export const MetricsExport: React.FC<MetricsExportProps> = ({
  projectId,
  availableFormats = ['json', 'csv', 'xml', 'pdf'],
  showAdvanced = false
}) => {
  const [timeRange, setTimeRange] = useState<TimeRange>('24h');
  const [selectedFormats, setSelectedFormats] = useState<string[]>(['json']);
  const [includeMetadata, setIncludeMetadata] = useState(true);
  const [customFilename, setCustomFilename] = useState('');
  const [exportJobs, setExportJobs] = useState<ExportJob[]>([]);
  const [isExporting, setIsExporting] = useState(false);

  const formatOptions = [
    { value: 'json', label: 'JSON', icon: <IconCode size={16} />, description: 'Structured data format' },
    { value: 'csv', label: 'CSV', icon: <IconTable size={16} />, description: 'Spreadsheet compatible' },
    { value: 'xml', label: 'XML', icon: <IconFileText size={16} />, description: 'Extensible markup' },
    { value: 'pdf', label: 'HTML Report', icon: <IconFile size={16} />, description: 'Formatted report' }
  ].filter(option => availableFormats.includes(option.value as any));

  const handleFormatToggle = (format: string) => {
    setSelectedFormats(prev =>
      prev.includes(format)
        ? prev.filter(f => f !== format)
        : [...prev, format]
    );
  };

  const handleSingleExport = async (format: string) => {
    const jobId = `export_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    const job: ExportJob = {
      id: jobId,
      format,
      status: 'pending',
      progress: 0,
      startTime: Date.now()
    };

    setExportJobs(prev => [...prev, job]);
    setIsExporting(true);

    try {
      // Update job status to processing
      setExportJobs(prev => prev.map(j =>
        j.id === jobId ? { ...j, status: 'processing', progress: 25 } : j
      ));

      const result = await MetricsExporter.export({
        format: format as any,
        timeRange,
        projectId,
        includeMetadata,
        compress: false,
        filename: customFilename || undefined
      });

      // Update job status to completed
      setExportJobs(prev => prev.map(j =>
        j.id === jobId ? {
          ...j,
          status: 'completed',
          progress: 100,
          result,
          endTime: Date.now()
        } : j
      ));

      // Download the file
      downloadExport(result);

    } catch (error) {
      // Update job status to failed
      setExportJobs(prev => prev.map(j =>
        j.id === jobId ? {
          ...j,
          status: 'failed',
          progress: 0,
          error: error instanceof Error ? error.message : 'Export failed',
          endTime: Date.now()
        } : j
      ));
    } finally {
      setIsExporting(false);
    }
  };

  const handleBatchExport = async () => {
    if (selectedFormats.length === 0) return;

    const jobId = `batch_export_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    const job: ExportJob = {
      id: jobId,
      format: `Batch (${selectedFormats.join(', ')})`,
      status: 'pending',
      progress: 0,
      startTime: Date.now()
    };

    setExportJobs(prev => [...prev, job]);
    setIsExporting(true);

    try {
      // Update job status to processing
      setExportJobs(prev => prev.map(j =>
        j.id === jobId ? { ...j, status: 'processing', progress: 10 } : j
      ));

      const results = await exportMultipleFormats(
        selectedFormats as any,
        projectId,
        timeRange
      );

      // Update job status to completed
      setExportJobs(prev => prev.map(j =>
        j.id === jobId ? {
          ...j,
          status: 'completed',
          progress: 100,
          endTime: Date.now()
        } : j
      ));

      // Download all files
      results.forEach(result => downloadExport(result));

    } catch (error) {
      // Update job status to failed
      setExportJobs(prev => prev.map(j =>
        j.id === jobId ? {
          ...j,
          status: 'failed',
          progress: 0,
          error: error instanceof Error ? error.message : 'Batch export failed',
          endTime: Date.now()
        } : j
      ));
    } finally {
      setIsExporting(false);
    }
  };

  const clearCompletedJobs = () => {
    setExportJobs(prev => prev.filter(job => job.status !== 'completed'));
  };

  const getJobStatusColor = (status: ExportJob['status']) => {
    switch (status) {
      case 'completed': return 'green';
      case 'failed': return 'red';
      case 'processing': return 'blue';
      default: return 'gray';
    }
  };

  const getJobStatusIcon = (status: ExportJob['status']) => {
    switch (status) {
      case 'completed': return <IconCheck size={16} />;
      case 'failed': return <IconX size={16} />;
      case 'processing': return <IconDownload size={16} />;
      default: return <IconInfoCircle size={16} />;
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDuration = (start: number, end?: number): string => {
    const duration = (end || Date.now()) - start;
    if (duration < 1000) return `${duration}ms`;
    return `${(duration / 1000).toFixed(1)}s`;
  };

  return (
    <Stack gap="md">
      <Card p="md" radius="md" withBorder>
        <Group justify="space-between" align="center" mb="md">
          <Group>
            <IconDownload size={24} />
            <div>
              <Text fw={600}>Export Analytics Data</Text>
              <Text size="sm" c="dimmed">Download metrics in various formats</Text>
            </div>
          </Group>
          {projectId && (
            <Badge variant="light" color="blue">
              Project: {projectId}
            </Badge>
          )}
        </Group>

        {/* Export Configuration */}
        <Stack gap="md">
          <Group grow>
            <Select
              label="Time Range"
              value={timeRange}
              onChange={(value) => value && setTimeRange(value as TimeRange)}
              data={[
                { value: '1h', label: 'Last Hour' },
                { value: '24h', label: 'Last 24 Hours' },
                { value: '7d', label: 'Last 7 Days' },
                { value: '30d', label: 'Last 30 Days' }
              ]}
            />

            {showAdvanced && (
              <TextInput
                label="Custom Filename"
                placeholder="analytics_report"
                value={customFilename}
                onChange={(e) => setCustomFilename(e.target.value)}
              />
            )}
          </Group>

          {showAdvanced && (
            <Checkbox
              label="Include metadata in export"
              checked={includeMetadata}
              onChange={(e) => setIncludeMetadata(e.currentTarget.checked)}
            />
          )}
        </Stack>
      </Card>

      {/* Format Selection */}
      <Card p="md" radius="md" withBorder>
        <Text fw={600} mb="md">Export Formats</Text>
        <Stack gap="sm">
          {formatOptions.map(format => (
            <Paper key={format.value} p="sm" withBorder radius="sm">
              <Group justify="space-between" align="center">
                <Group>
                  {format.icon}
                  <div>
                    <Text fw={600}>{format.label}</Text>
                    <Text size="sm" c="dimmed">{format.description}</Text>
                  </div>
                </Group>
                <Group>
                  <Button
                    size="sm"
                    variant="light"
                    onClick={() => handleSingleExport(format.value)}
                    loading={isExporting}
                    disabled={isExporting}
                  >
                    Export {format.label}
                  </Button>
                  <Checkbox
                    checked={selectedFormats.includes(format.value)}
                    onChange={() => handleFormatToggle(format.value)}
                  />
                </Group>
              </Group>
            </Paper>
          ))}
        </Stack>

        {selectedFormats.length > 1 && (
          <>
            <Divider my="md" />
            <Group justify="center">
              <Button
                size="lg"
                onClick={handleBatchExport}
                loading={isExporting}
                disabled={isExporting || selectedFormats.length === 0}
                leftSection={<IconDownload size={16} />}
              >
                Export Selected Formats ({selectedFormats.length})
              </Button>
            </Group>
          </>
        )}
      </Card>

      {/* Export Jobs Status */}
      {exportJobs.length > 0 && (
        <Card p="md" radius="md" withBorder>
          <Group justify="space-between" align="center" mb="md">
            <Text fw={600}>Export Jobs</Text>
            <Button size="xs" variant="light" onClick={clearCompletedJobs}>
              Clear Completed
            </Button>
          </Group>

          <Stack gap="sm">
            {exportJobs.map(job => (
              <Paper key={job.id} p="sm" withBorder radius="sm">
                <Group justify="space-between" align="center" mb="xs">
                  <Group>
                    {getJobStatusIcon(job.status)}
                    <div>
                      <Text fw={600}>{job.format}</Text>
                      <Text size="sm" c="dimmed">
                        {formatDuration(job.startTime, job.endTime)}
                      </Text>
                    </div>
                  </Group>
                  <Badge color={getJobStatusColor(job.status)} variant="light">
                    {job.status}
                  </Badge>
                </Group>

                {job.status === 'processing' && (
                  <Progress value={job.progress} size="sm" mb="xs" />
                )}

                {job.status === 'completed' && job.result && (
                  <Group gap="xs">
                    <Text size="sm" c="dimmed">Size:</Text>
                    <Text size="sm" fw={600}>{formatFileSize(job.result.size)}</Text>
                    <Text size="sm" c="dimmed">•</Text>
                    <Text size="sm" c="dimmed">Downloaded as:</Text>
                    <Text size="sm" fw={600}>{job.result.filename}</Text>
                  </Group>
                )}

                {job.status === 'failed' && job.error && (
                  <Alert color="red" icon={<IconAlertTriangle size={16} />}>
                    {job.error}
                  </Alert>
                )}
              </Paper>
            ))}
          </Stack>
        </Card>
      )}

      {/* Export Tips */}
      <Card p="md" radius="md" withBorder>
        <Alert icon={<IconInfoCircle size={16} />} title="Export Tips" color="blue">
          <Stack gap="xs">
            <Text size="sm">
              • JSON format is best for programmatic analysis and data import
            </Text>
            <Text size="sm">
              • CSV format works well with spreadsheet applications like Excel
            </Text>
            <Text size="sm">
              • XML format is suitable for structured data exchange
            </Text>
            <Text size="sm">
              • HTML reports provide formatted, human-readable summaries
            </Text>
          </Stack>
        </Alert>
      </Card>
    </Stack>
  );
};

export default MetricsExport;