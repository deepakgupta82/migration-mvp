import React, { useState, useEffect, useCallback } from 'react';
import {
  Card,
  Text,
  Group,
  Badge,
  Stack,
  Progress,
  Button,
  Table,
  Loader,
  Alert,
  RingProgress,
  SimpleGrid,
  Paper,
  Divider,
  ActionIcon,
  Tooltip,
  Modal,
} from '@mantine/core';
import {
  IconRefresh,
  IconPlayerPlay,
  IconPlayerPause,
  IconX,
  IconEye,
  IconDownload,
  IconAlertCircle,
  IconCheck,
  IconClock,
  IconFileText,
  IconWifi,
  IconWifiOff,
} from '@tabler/icons-react';
import { apiService } from '../services/api';
import { useRealtimeAnalysis } from '../hooks/useRealtimeAnalysis.fixed';
import { notifications } from '@mantine/notifications';

interface BatchAnalysis {
  batch_id: string;
  project_id: string;
  analysis_type: string;
  status: string;
  total_files: number;
  completed_files: number;
  failed_files: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  estimated_completion?: string;
  progress_percentage?: number;
  message?: string; // Real-time message from WebSocket
  results?: Array<{
    analysis_id: string;
    filename: string;
    status: string;
    error_message?: string;
    processing_time?: number;
  }>;
}

interface BatchAnalysisMonitorProps {
  projectId: string;
  onAnalysisComplete?: (batchId: string, results: any[]) => void;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

export const BatchAnalysisMonitor: React.FC<BatchAnalysisMonitorProps> = ({
  projectId,
  onAnalysisComplete,
  autoRefresh = true,
  refreshInterval = 5000
}) => {
  const [batches, setBatches] = useState<BatchAnalysis[]>([]);
  const [selectedBatch, setSelectedBatch] = useState<BatchAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [detailsModalOpen, setDetailsModalOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  // WebSocket connection for real-time updates
  const {
    isConnected,
    connectionError,
    connect,
    disconnect
  } = useRealtimeAnalysis({
   projectId,
   onBatchUpdate: useCallback((progress: any) => {
     console.log('Received batch progress update:', progress);
     setBatches(prev => prev.map(batch =>
       batch.batch_id === progress.batch_id
         ? {
             ...batch,
             status: progress.status,
             progress_percentage: progress.progress_percentage,
             completed_files: progress.completed_files,
             total_files: progress.total_files,
             estimated_completion: progress.estimated_completion,
             message: progress.message
           }
         : batch
     ));
   }, []),
    onBatchComplete: useCallback(async (batchId: string, results: any[]) => {
      console.log('Batch completed:', batchId, results);
      // Refresh the batch details to get final results
      try {
        const batchDetails = await apiService.getBatchAnalysisStatus(projectId, batchId);
        setBatches(prev => prev.map(batch =>
          batch.batch_id === batchId ? batchDetails : batch
        ));
      } catch (error) {
        console.error('Failed to refresh batch details:', error);
      }
      if (onAnalysisComplete) {
        onAnalysisComplete(batchId, results);
      }
    }, [projectId, onAnalysisComplete]),
    autoConnect: autoRefresh
  });

  // Load batch analysis data
  const loadBatchData = async () => {
    try {
      setRefreshing(true);
      const response = await apiService.listAnalysisBatches(projectId);
      setBatches(response.batches || []);
    } catch (error) {
      console.error('Failed to load batch analysis data:', error);
      notifications.show({
        title: 'Error',
        message: 'Failed to load batch analysis data',
        color: 'red',
      });
    } finally {
      setRefreshing(false);
    }
  };

  // Load specific batch details
  const loadBatchDetails = async (batchId: string) => {
    try {
      const batchDetails = await apiService.getBatchAnalysisStatus(projectId, batchId);
      setSelectedBatch(batchDetails);

      // Update the batch in the list
      setBatches(prev => prev.map(batch =>
        batch.batch_id === batchId ? batchDetails : batch
      ));

      // Check if batch is completed
      if (batchDetails.status === 'completed' && onAnalysisComplete) {
        onAnalysisComplete(batchId, batchDetails.results);
      }

      return batchDetails;
    } catch (error) {
      console.error('Failed to load batch details:', error);
      notifications.show({
        title: 'Error',
        message: `Failed to load details for batch ${batchId}`,
        color: 'red',
      });
    }
  };

  // Auto-refresh active batches (fallback to polling if WebSocket fails)
  useEffect(() => {
    if (!autoRefresh || isConnected) return; // Skip polling if WebSocket is connected

    const interval = setInterval(async () => {
      const activeBatches = batches.filter(batch =>
        ['pending', 'running', 'processing'].includes(batch.status)
      );

      if (activeBatches.length > 0) {
        for (const batch of activeBatches) {
          await loadBatchDetails(batch.batch_id);
        }
      }
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [batches, autoRefresh, refreshInterval, isConnected]);

  // Initial load
  useEffect(() => {
    loadBatchData();
  }, [projectId]);

  const getStatusColor = (status: string): string => {
    switch (status.toLowerCase()) {
      case 'completed': return 'green';
      case 'running':
      case 'processing': return 'blue';
      case 'pending': return 'yellow';
      case 'failed': return 'red';
      case 'cancelled': return 'gray';
      default: return 'gray';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status.toLowerCase()) {
      case 'completed': return <IconCheck size={16} />;
      case 'running':
      case 'processing': return <IconPlayerPlay size={16} />;
      case 'pending': return <IconClock size={16} />;
      case 'failed': return <IconX size={16} />;
      case 'cancelled': return <IconPlayerPause size={16} />;
      default: return <IconAlertCircle size={16} />;
    }
  };

  const formatDuration = (startTime: string, endTime?: string): string => {
    const start = new Date(startTime);
    const end = endTime ? new Date(endTime) : new Date();
    const duration = end.getTime() - start.getTime();

    const seconds = Math.floor(duration / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);

    if (hours > 0) {
      return `${hours}h ${minutes % 60}m`;
    } else if (minutes > 0) {
      return `${minutes}m ${seconds % 60}s`;
    } else {
      return `${seconds}s`;
    }
  };

  const activeBatches = batches.filter(batch =>
    ['pending', 'running', 'processing'].includes(batch.status)
  );

  const completedBatches = batches.filter(batch =>
    ['completed', 'failed', 'cancelled'].includes(batch.status)
  );

  return (
    <Stack gap="md">
      {/* Header */}
      <Group justify="space-between" align="center">
        <div>
          <Text size="lg" fw={600}>Batch Analysis Monitor</Text>
          <Text size="sm" c="dimmed">
            Monitor and manage batch document analysis operations
          </Text>
        </div>
        <Group gap="xs">
          {/* Connection Status */}
          <Tooltip label={isConnected ? 'Real-time updates active' : connectionError || 'Real-time updates unavailable'}>
            <Badge
              variant="light"
              color={isConnected ? 'green' : 'orange'}
              leftSection={isConnected ? <IconWifi size={12} /> : <IconWifiOff size={12} />}
            >
              {isConnected ? 'Live' : 'Offline'}
            </Badge>
          </Tooltip>

          <Button
            size="sm"
            variant="light"
            leftSection={<IconRefresh size={14} />}
            onClick={loadBatchData}
            loading={refreshing}
          >
            Refresh
          </Button>
          {activeBatches.length > 0 && (
            <Badge variant="light" color="blue">
              {activeBatches.length} Active
            </Badge>
          )}
        </Group>
      </Group>

      {/* Active Batches */}
      {activeBatches.length > 0 && (
        <Card withBorder p="md">
          <Text size="md" fw={600} mb="md">Active Batches</Text>
          <Stack gap="md">
            {activeBatches.map((batch) => (
              <Paper key={batch.batch_id} p="md" withBorder>
                <Group justify="space-between" mb="sm">
                  <div>
                    <Group gap="xs">
                      {getStatusIcon(batch.status)}
                      <Text fw={600}>{batch.analysis_type} Analysis</Text>
                      <Badge color={getStatusColor(batch.status)} variant="light">
                        {batch.status}
                      </Badge>
                    </Group>
                    <Text size="sm" c="dimmed">
                      Batch ID: {batch.batch_id}
                    </Text>
                  </div>
                  <Button
                    size="sm"
                    variant="light"
                    leftSection={<IconEye size={14} />}
                    onClick={() => {
                      loadBatchDetails(batch.batch_id);
                      setDetailsModalOpen(true);
                    }}
                  >
                    View Details
                  </Button>
                </Group>

                <Stack gap="sm">
                  <Group justify="space-between">
                    <Text size="sm">
                      Progress: {batch.completed_files}/{batch.total_files} files
                    </Text>
                    <Text size="sm" c="dimmed">
                      {batch.progress_percentage ? batch.progress_percentage.toFixed(1) : '0.0'}%
                    </Text>
                  </Group>

                  <Progress
                    value={batch.progress_percentage || 0}
                    color={getStatusColor(batch.status)}
                    size="lg"
                  />

                  {/* Real-time progress message */}
                  {batch.message && (
                    <Alert color="blue" variant="light">
                      <Text size="xs">{batch.message}</Text>
                    </Alert>
                  )}

                  <Group gap="md">
                    <Text size="xs" c="dimmed">
                      Started: {new Date(batch.created_at).toLocaleString()}
                    </Text>
                    {batch.estimated_completion && (
                      <Text size="xs" c="dimmed">
                        Est. completion: {new Date(batch.estimated_completion).toLocaleString()}
                      </Text>
                    )}
                  </Group>
                </Stack>
              </Paper>
            ))}
          </Stack>
        </Card>
      )}

      {/* Completed Batches */}
      {completedBatches.length > 0 && (
        <Card withBorder p="md">
          <Text size="md" fw={600} mb="md">Completed Batches</Text>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Batch ID</Table.Th>
                <Table.Th>Type</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Files</Table.Th>
                <Table.Th>Duration</Table.Th>
                <Table.Th>Completed</Table.Th>
                <Table.Th>Actions</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {completedBatches.map((batch) => (
                <Table.Tr key={batch.batch_id}>
                  <Table.Td>
                    <Text size="sm" style={{ fontFamily: 'monospace' }}>
                      {batch.batch_id.substring(0, 8)}...
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Badge size="sm" variant="light">
                      {batch.analysis_type}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Badge color={getStatusColor(batch.status)} variant="light">
                      {batch.status}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">
                      {batch.completed_files}/{batch.total_files}
                      {batch.failed_files > 0 && (
                        <Text size="xs" c="red" span>
                          {' '}({batch.failed_files} failed)
                        </Text>
                      )}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" c="dimmed">
                      {formatDuration(batch.created_at, batch.completed_at)}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" c="dimmed">
                      {new Date(batch.completed_at || batch.created_at).toLocaleDateString()}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Group gap="xs">
                      <Tooltip label="View Details">
                        <ActionIcon
                          size="sm"
                          variant="light"
                          onClick={() => {
                            loadBatchDetails(batch.batch_id);
                            setDetailsModalOpen(true);
                          }}
                        >
                          <IconEye size={14} />
                        </ActionIcon>
                      </Tooltip>
                      <Tooltip label="Download Results">
                        <ActionIcon
                          size="sm"
                          variant="light"
                          color="blue"
                          onClick={() => {
                            // TODO: Implement download functionality
                            notifications.show({
                              title: 'Download',
                              message: 'Download functionality coming soon',
                              color: 'blue',
                            });
                          }}
                        >
                          <IconDownload size={14} />
                        </ActionIcon>
                      </Tooltip>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Card>
      )}

      {/* Empty State */}
      {batches.length === 0 && !loading && (
        <Card withBorder p="xl">
          <Stack gap="md" align="center">
            <IconFileText size={48} color="#868e96" />
            <div>
              <Text size="lg" fw={600} ta="center">No Batch Analyses Found</Text>
              <Text size="sm" c="dimmed" ta="center">
                Batch analysis operations will appear here when you start processing multiple documents
              </Text>
            </div>
          </Stack>
        </Card>
      )}

      {/* Batch Details Modal */}
      <Modal
        opened={detailsModalOpen}
        onClose={() => setDetailsModalOpen(false)}
        title="Batch Analysis Details"
        size="lg"
      >
        {selectedBatch && (
          <Stack gap="md">
            <Group justify="space-between">
              <div>
                <Text fw={600}>{selectedBatch.analysis_type} Analysis</Text>
                <Text size="sm" c="dimmed">
                  Batch ID: {selectedBatch.batch_id}
                </Text>
              </div>
              <Badge color={getStatusColor(selectedBatch.status)} variant="light">
                {selectedBatch.status}
              </Badge>
            </Group>

            <Divider />

            <SimpleGrid cols={4} spacing="md">
              <Card p="sm" withBorder>
                <Text size="xs" c="dimmed" tt="uppercase" fw={600}>Total Files</Text>
                <Text size="lg" fw={700}>{selectedBatch.total_files}</Text>
              </Card>
              <Card p="sm" withBorder>
                <Text size="xs" c="dimmed" tt="uppercase" fw={600}>Completed</Text>
                <Text size="lg" fw={700} c="green">{selectedBatch.completed_files}</Text>
              </Card>
              <Card p="sm" withBorder>
                <Text size="xs" c="dimmed" tt="uppercase" fw={600}>Failed</Text>
                <Text size="lg" fw={700} c="red">{selectedBatch.failed_files}</Text>
              </Card>
              <Card p="sm" withBorder>
                <Text size="xs" c="dimmed" tt="uppercase" fw={600}>Progress</Text>
                <Text size="lg" fw={700}>{selectedBatch.progress_percentage ? selectedBatch.progress_percentage.toFixed(1) : '0.0'}%</Text>
              </Card>
            </SimpleGrid>

            <Progress
              value={selectedBatch.progress_percentage || 0}
              color={getStatusColor(selectedBatch.status)}
              size="lg"
            />

            <Group gap="md">
              <Text size="sm" c="dimmed">
                Created: {new Date(selectedBatch.created_at).toLocaleString()}
              </Text>
              {selectedBatch.started_at && (
                <Text size="sm" c="dimmed">
                  Started: {new Date(selectedBatch.started_at).toLocaleString()}
                </Text>
              )}
              {selectedBatch.completed_at && (
                <Text size="sm" c="dimmed">
                  Completed: {new Date(selectedBatch.completed_at).toLocaleString()}
                </Text>
              )}
            </Group>

            {/* Results Table */}
            {selectedBatch.results && selectedBatch.results.length > 0 && (
              <Card withBorder>
                <Text size="md" fw={600} mb="md">Analysis Results</Text>
                <Table striped highlightOnHover>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Filename</Table.Th>
                      <Table.Th>Status</Table.Th>
                      <Table.Th>Processing Time</Table.Th>
                      <Table.Th>Error</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {selectedBatch.results.map((result, index) => (
                      <Table.Tr key={index}>
                        <Table.Td>
                          <Text size="sm" style={{ wordBreak: 'break-word' }}>
                            {result.filename}
                          </Text>
                        </Table.Td>
                        <Table.Td>
                          <Badge
                            size="xs"
                            color={result.status === 'completed' ? 'green' : 'red'}
                            variant="light"
                          >
                            {result.status}
                          </Badge>
                        </Table.Td>
                        <Table.Td>
                          <Text size="sm" c="dimmed">
                            {result.processing_time ? `${result.processing_time.toFixed(2)}s` : '-'}
                          </Text>
                        </Table.Td>
                        <Table.Td>
                          <Text size="sm" c="red">
                            {result.error_message || '-'}
                          </Text>
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Card>
            )}
          </Stack>
        )}
      </Modal>
    </Stack>
  );
};

export default BatchAnalysisMonitor;