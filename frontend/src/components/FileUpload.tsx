import React, { useState, useRef, useEffect } from "react";
import { Button, Group, Stack, Text, Paper, Loader, Table, Badge, Card, Divider, Alert } from "@mantine/core";
import { Dropzone } from "@mantine/dropzone";
import { IconFile, IconUpload, IconRefresh, IconAlertCircle, IconSettings, IconTestPipe } from "@tabler/icons-react";
import { v4 as uuidv4 } from "uuid";
import { apiService, ProjectFile } from "../services/api";
import { notifications } from "@mantine/notifications";
import LiveConsole from "./LiveConsole";
import ReportDisplay from "./ReportDisplay";
import LLMConfigurationModal from './LLMConfigurationModal';
import TestLLMModal from './TestLLMModal';
import RightLogPane from './RightLogPane';
import { useNotifications } from '../contexts/NotificationContext';

type FileUploadProps = {
  projectId?: string;
};

const FileUpload: React.FC<FileUploadProps> = ({ projectId: propProjectId }) => {
  const [files, setFiles] = useState<File[]>([]);
  const [uploadedFiles, setUploadedFiles] = useState<ProjectFile[]>([]);
  const [projectId, setProjectId] = useState<string>(propProjectId || "");
  const [isUploading, setIsUploading] = useState(false);
  const [isAssessing, setIsAssessing] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [finalReport, setFinalReport] = useState<string>("");
  const [isReportStreaming, setIsReportStreaming] = useState<boolean>(false);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [assessmentStartTime, setAssessmentStartTime] = useState<Date | null>(null);
  const [testingLLM, setTestingLLM] = useState(false);
  const [testLLMModalOpen, setTestLLMModalOpen] = useState(false);
  const [llmConfigModalOpen, setLlmConfigModalOpen] = useState(false);
  const [currentProject, setCurrentProject] = useState<any>(null);
  const [rightLogPaneOpen, setRightLogPaneOpen] = useState(false);
  const [agenticLogs, setAgenticLogs] = useState<any[]>([]);

  const wsRef = useRef<WebSocket | null>(null);
  const { addNotification } = useNotifications();

  // Fetch uploaded files when component mounts or projectId changes
  useEffect(() => {
    if (projectId) {
      fetchUploadedFiles();
      fetchProjectDetails();
    }
  }, [projectId]);

  const fetchProjectDetails = async () => {
    if (!projectId) return;
    try {
      const project = await apiService.getProject(projectId);
      setCurrentProject(project);
    } catch (error) {
      console.error('Error fetching project details:', error);
    }
  };

  const fetchUploadedFiles = async () => {
    if (!projectId) return;
    try {
      setLoadingFiles(true);
      const files = await apiService.getProjectFiles(projectId);
      setUploadedFiles(files);
    } catch (error) {
      console.error('Error fetching uploaded files:', error);
    } finally {
      setLoadingFiles(false);
    }
  };

  const handleDrop = (acceptedFiles: File[]) => {
    // Check for duplicate files
    const duplicateFiles = acceptedFiles.filter(newFile =>
      uploadedFiles.some(existingFile => existingFile.filename === newFile.name)
    );

    if (duplicateFiles.length > 0) {
      notifications.show({
        title: 'Duplicate Files Detected',
        message: `The following files already exist: ${duplicateFiles.map(f => f.name).join(', ')}`,
        color: 'orange',
      });
      // Filter out duplicate files
      const uniqueFiles = acceptedFiles.filter(newFile =>
        !uploadedFiles.some(existingFile => existingFile.filename === newFile.name)
      );
      setFiles(uniqueFiles);
    } else {
      setFiles(acceptedFiles);
    }

    // Only generate new project ID if not provided as prop
    if (!propProjectId) {
      setProjectId(uuidv4());
    }
    setLogs([]);
    setFinalReport("");
    setIsReportStreaming(false);
  };

  const handleUploadAndAssess = async () => {
    if (files.length === 0 || !projectId) {
      // If no files selected, prompt user to select files
      notifications.show({
        title: 'No Files Selected',
        message: 'Please select files to upload before starting assessment',
        color: 'orange',
      });
      return;
    }

    setIsUploading(true);
    try {
      // Upload files using the new API service
      await apiService.uploadFiles(projectId, files);

      // Track uploaded files in the database
      for (const file of files) {
        await apiService.addProjectFile(projectId, file.name, file.type);
      }

      // Refresh the uploaded files list
      await fetchUploadedFiles();

      // Show both Mantine notification and add to notification center
      const fileNames = files.map(f => f.name).join(', ');
      notifications.show({
        title: 'Success',
        message: 'Files uploaded successfully',
        color: 'green',
      });

      addNotification({
        title: 'Files Uploaded Successfully',
        message: `Uploaded ${files.length} file(s): ${fileNames}`,
        type: 'success',
        projectId: projectId,
        metadata: { fileCount: files.length, fileNames }
      });

      setIsUploading(false);
      setIsAssessing(true);
      setAssessmentStartTime(new Date());
      setAgenticLogs([]);

      // Open right log pane
      setRightLogPaneOpen(true);

      // Add assessment started notification
      addNotification({
        title: 'Assessment Started',
        message: 'Document analysis and migration assessment has begun',
        type: 'info',
        projectId: projectId,
        metadata: { startTime: new Date().toISOString() }
      });

      // Start assessment via WebSocket
      const ws = apiService.createAssessmentWebSocket(projectId);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        const msg = event.data;

        // Parse message to determine if it's agentic interaction
        try {
          const parsedMessage = JSON.parse(msg);
          if (parsedMessage.type === 'agentic_log') {
            setAgenticLogs(prev => [...prev, {
              timestamp: new Date().toISOString(),
              level: parsedMessage.level || 'info',
              message: parsedMessage.message,
              source: parsedMessage.source
            }]);
            return;
          }
        } catch {
          // If not JSON, continue with regular processing
        }

        if (msg === "FINAL_REPORT_MARKDOWN_START") {
          setFinalReport("");
          setIsReportStreaming(true);
        } else if (msg === "FINAL_REPORT_MARKDOWN_END") {
          setIsReportStreaming(false);
          setIsAssessing(false);
          notifications.show({
            title: 'Assessment Complete',
            message: 'Your migration assessment has been completed successfully',
            color: 'green',
          });

          addNotification({
            title: 'Assessment Completed Successfully',
            message: 'Migration assessment report is now available for review',
            type: 'success',
            projectId: projectId,
            metadata: {
              completedAt: new Date().toISOString(),
              startTime: assessmentStartTime?.toISOString()
            }
          });
        } else if (isReportStreaming) {
          setFinalReport((prev) => prev + msg + "\n");
        } else {
          setLogs((prev) => [...prev, msg]);
        }
      };

      ws.onclose = () => setIsAssessing(false);
      ws.onerror = () => {
        setIsAssessing(false);
        notifications.show({
          title: 'Error',
          message: 'Assessment connection failed',
          color: 'red',
        });

        addNotification({
          title: 'Assessment Connection Failed',
          message: 'Unable to connect to assessment service. Please check configuration.',
          type: 'error',
          projectId: projectId,
          metadata: { errorType: 'connection_failed' }
        });
      };

    } catch (err) {
      setIsUploading(false);
      setIsAssessing(false);
      notifications.show({
        title: 'Error',
        message: 'Failed to upload files or start assessment',
        color: 'red',
      });

      addNotification({
        title: 'Upload or Assessment Failed',
        message: `Error: ${err instanceof Error ? err.message : 'Unknown error occurred'}`,
        type: 'error',
        projectId: projectId,
        metadata: { errorType: 'upload_assessment_failed', error: String(err) }
      });

      setLogs((prev) => [...prev, "Error uploading files or starting assessment."]);
    }
  };

  const handleReassessment = () => {
    if (!projectId || uploadedFiles.length === 0) {
      notifications.show({
        title: 'No Files Available',
        message: 'Please upload files before starting reassessment',
        color: 'orange',
      });
      return;
    }

    // Open LLM configuration modal
    setLlmConfigModalOpen(true);
  };

  const handleTestLLM = () => {
    if (!projectId) {
      notifications.show({
        title: 'No Project Selected',
        message: 'Please select a project first',
        color: 'orange',
      });
      return;
    }

    // Open the enhanced Test LLM modal
    setTestLLMModalOpen(true);
  };

  const handleLLMConfigConfirm = async (llmConfig: any) => {
    setLlmConfigModalOpen(false);

    // Update project with LLM configuration
    try {
      await apiService.updateProject(projectId, {
        llm_provider: llmConfig.provider,
        llm_model: llmConfig.model,
        llm_api_key_id: llmConfig.apiKeyId,
        llm_temperature: llmConfig.temperature.toString(),
        llm_max_tokens: llmConfig.maxTokens.toString()
      });
    } catch (error) {
      console.error('Error updating project LLM configuration:', error);
      notifications.show({
        title: 'Configuration Error',
        message: 'Failed to save LLM configuration',
        color: 'red',
      });
      return;
    }

    setIsAssessing(true);
    setAssessmentStartTime(new Date());
    setLogs(["Starting assessment with project-specific LLM configuration..."]);
    setFinalReport("");
    setIsReportStreaming(false);

    try {
      // Start assessment via WebSocket for existing files
      const ws = apiService.createAssessmentWebSocket(projectId);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        const msg = event.data;

        // Parse message to determine if it's agentic interaction
        try {
          const parsedMessage = JSON.parse(msg);
          if (parsedMessage.type === 'agentic_log') {
            setAgenticLogs(prev => [...prev, {
              timestamp: new Date().toISOString(),
              level: parsedMessage.level || 'info',
              message: parsedMessage.message,
              source: parsedMessage.source
            }]);
            return;
          }
        } catch {
          // If not JSON, continue with regular processing
        }

        if (msg === "FINAL_REPORT_MARKDOWN_START") {
          setFinalReport("");
          setIsReportStreaming(true);
        } else if (msg === "FINAL_REPORT_MARKDOWN_END") {
          setIsReportStreaming(false);
          setIsAssessing(false);
          notifications.show({
            title: 'Reassessment Complete',
            message: 'Your migration reassessment has been completed successfully',
            color: 'green',
          });

          addNotification({
            title: 'Reassessment Completed Successfully',
            message: `Migration reassessment using ${llmConfig.provider}/${llmConfig.model} is now available for review`,
            type: 'success',
            projectId: projectId,
            metadata: {
              completedAt: new Date().toISOString(),
              startTime: assessmentStartTime?.toISOString(),
              llmProvider: llmConfig.provider,
              llmModel: llmConfig.model
            }
          });
        } else if (isReportStreaming) {
          setFinalReport((prev) => prev + msg + "\n");
        } else {
          setLogs((prev) => [...prev, msg]);
        }
      };

      ws.onclose = () => setIsAssessing(false);
      ws.onerror = () => {
        setIsAssessing(false);
        notifications.show({
          title: 'Error',
          message: 'Reassessment connection failed',
          color: 'red',
        });

        addNotification({
          title: 'Reassessment Connection Failed',
          message: 'Unable to connect to assessment service. Please check LLM configuration.',
          type: 'error',
          projectId: projectId,
          metadata: { errorType: 'connection_failed', llmConfig }
        });
      };

    } catch (err) {
      setIsAssessing(false);
      notifications.show({
        title: 'Error',
        message: 'Failed to start reassessment',
        color: 'red',
      });
      setLogs((prev) => [...prev, "Error starting reassessment."]);

      addNotification({
        title: 'Reassessment Failed',
        message: `Error: ${err instanceof Error ? err.message : 'Unknown error occurred'}`,
        type: 'error',
        projectId: projectId,
        metadata: { errorType: 'reassessment_failed', error: String(err), llmConfig }
      });
    }
  };

  const stopAssessment = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsAssessing(false);
    setIsReportStreaming(false);

    notifications.show({
      title: 'Assessment Stopped',
      message: 'Assessment was manually stopped',
      color: 'orange',
    });

    addNotification({
      title: 'Assessment Stopped',
      message: 'Assessment was manually stopped by user',
      type: 'warning',
      projectId: projectId,
      metadata: { stoppedAt: new Date().toISOString() }
    });

    setLogs(prev => [...prev, 'Assessment stopped by user']);
  };

  return (
    <Stack gap="lg">
      {/* File Upload Section */}
      <Card shadow="sm" p="md" radius="md" withBorder>
        <Text size="md" fw={600} mb="sm">
          Upload Documents
        </Text>
        <Dropzone
          onDrop={handleDrop}
          multiple
          accept={{
            'application/pdf': ['.pdf'],
            'application/msword': ['.doc'],
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
            'text/plain': ['.txt'],
            'text/csv': ['.csv'],
          }}
        >
          <Group justify="center" gap="md" style={{ minHeight: 80, pointerEvents: 'none' }}>
            <IconUpload size={32} color="#868e96" />
            <div>
              <Text size="md" inline>
                Drag documents here or click to select files
              </Text>
              <Text size="xs" c="dimmed" inline mt={4}>
                Attach infrastructure documents, network diagrams, application inventories, etc.
              </Text>
            </div>
          </Group>
        </Dropzone>

        {files.length > 0 && (
          <Paper p="md" mt="md" style={{ backgroundColor: '#f8f9fa' }}>
            <Text size="sm" fw={500} mb="xs">
              Selected Files ({files.length}):
            </Text>
            {files.map((file, index) => (
              <Group key={index} gap="xs" mb="xs">
                <IconFile size={16} />
                <Text size="sm">{file.name}</Text>
                <Badge size="xs" variant="light">
                  {(file.size / 1024 / 1024).toFixed(2)} MB
                </Badge>
              </Group>
            ))}
          </Paper>
        )}

        <Group mt="md">
          <Button
            leftSection={<IconUpload size={16} />}
            onClick={handleUploadAndAssess}
            disabled={isUploading || isAssessing}
            loading={isUploading}
            color={files.length === 0 ? 'orange' : 'blue'}
          >
            {isUploading ? 'Uploading...' : files.length === 0 ? 'Select Files to Upload' : 'Upload & Start Assessment'}
          </Button>

          {uploadedFiles.length > 0 && (
            <>
              <Button
                leftSection={<IconSettings size={16} />}
                onClick={handleReassessment}
                disabled={isAssessing || isUploading}
                variant="light"
                color="green"
              >
                Configure & Reassess Files
              </Button>

              <Button
                leftSection={<IconTestPipe size={16} />}
                onClick={handleTestLLM}
                disabled={isAssessing || isUploading}
                variant="outline"
                color="blue"
              >
                Test LLM
              </Button>
            </>
          )}

          {isAssessing && (
            <Group gap="xs">
              <Loader size="sm" />
              <Text size="sm" c="dimmed">Assessment in progress...</Text>
            </Group>
          )}
        </Group>
      </Card>

      {/* Uploaded Files Section */}
      <Card shadow="sm" p="lg" radius="md" withBorder>
        <Group justify="space-between" mb="md">
          <Text size="lg" fw={600}>
            Uploaded Files
          </Text>
          <Badge variant="light">
            {uploadedFiles.length} files
          </Badge>
        </Group>

        {loadingFiles ? (
          <Group justify="center" p="md">
            <Loader size="sm" />
            <Text size="sm" c="dimmed">Loading files...</Text>
          </Group>
        ) : uploadedFiles.length === 0 ? (
          <Text size="sm" c="dimmed" ta="center" p="md">
            No files uploaded yet. Upload documents to start the assessment.
          </Text>
        ) : (
          <Table>
            <thead>
              <tr>
                <th style={{ textAlign: 'left' }}>Filename</th>
                <th style={{ textAlign: 'left' }}>Type</th>
                <th style={{ textAlign: 'left' }}>Uploaded</th>
              </tr>
            </thead>
            <tbody>
              {uploadedFiles.map((file) => (
                <tr key={file.id}>
                  <td>
                    <Group gap="xs">
                      <IconFile size={16} />
                      <Text size="sm">{file.filename}</Text>
                    </Group>
                  </td>
                  <td>
                    <Badge size="sm" variant="light">
                      {file.file_type || 'Unknown'}
                    </Badge>
                  </td>
                  <td>
                    <Text size="sm" color="dimmed">
                      {new Date(file.upload_timestamp).toLocaleString()}
                    </Text>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}

        {/* Reassessment Alert for Projects with Files */}
        {uploadedFiles.length > 0 && !isAssessing && (
          <Alert color="blue" mt="md" icon={<IconAlertCircle size={16} />}>
            <Text size="sm">
              <strong>Files are ready for assessment.</strong> You can reassess existing files
              if there were any issues with the previous assessment, or upload additional files above.
            </Text>
          </Alert>
        )}
      </Card>

      {/* Assessment Progress */}
      {(logs.length > 0 || isAssessing) && (
        <Card shadow="sm" p="lg" radius="md" withBorder>
          <Group justify="space-between" mb="md">
            <Text size="lg" fw={600}>
              Assessment Progress
            </Text>
            {assessmentStartTime && (
              <Text size="sm" c="dimmed">
                Started: {assessmentStartTime.toLocaleString()}
              </Text>
            )}
          </Group>
          <LiveConsole logs={logs.length > 0 ? logs : ["Initializing assessment..."]} />
        </Card>
      )}

      {/* Final Report */}
      {finalReport && (
        <Card shadow="sm" p="lg" radius="md" withBorder>
          <Text size="lg" fw={600} mb="md">
            Assessment Report
          </Text>
          <ReportDisplay report={finalReport} />
        </Card>
      )}

      {/* LLM Configuration Modal */}
      <LLMConfigurationModal
        opened={llmConfigModalOpen}
        onClose={() => setLlmConfigModalOpen(false)}
        onConfirm={handleLLMConfigConfirm}
        projectId={projectId}
        currentConfig={currentProject ? {
          provider: currentProject.llm_provider,
          model: currentProject.llm_model,
          apiKeyId: currentProject.llm_api_key_id,
          temperature: parseFloat(currentProject.llm_temperature || '0.1'),
          maxTokens: parseInt(currentProject.llm_max_tokens || '4000')
        } : null}
      />

      {/* Test LLM Modal */}
      <TestLLMModal
        opened={testLLMModalOpen}
        onClose={() => setTestLLMModalOpen(false)}
        projectId={projectId}
      />

      {/* Right Log Pane */}
      <RightLogPane
        opened={rightLogPaneOpen}
        onClose={() => setRightLogPaneOpen(false)}
        assessmentLogs={logs}
        agenticLogs={agenticLogs}
        isAssessing={isAssessing}
        onStopAssessment={stopAssessment}
        projectName={currentProject?.name}
      />
    </Stack>
  );
};

export default FileUpload;
