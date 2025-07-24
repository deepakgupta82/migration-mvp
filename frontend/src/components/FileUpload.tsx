import React, { useState, useRef, useEffect } from "react";
import { Button, Group, Stack, Text, Paper, Loader, Table, Badge, Card, Divider } from "@mantine/core";
import { Dropzone } from "@mantine/dropzone";
import { IconFile, IconUpload } from "@tabler/icons-react";
import { apiService, ProjectFile } from "../services/api";
import { notifications } from "@mantine/notifications";
import LiveConsole from "./LiveConsole";
import ReportDisplay from "./ReportDisplay";

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

  const wsRef = useRef<WebSocket | null>(null);

  // Fetch uploaded files when component mounts or projectId changes
  useEffect(() => {
    if (projectId) {
      fetchUploadedFiles();
    }
  }, [projectId]);

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
    setFiles(acceptedFiles);
    // Only generate new project ID if not provided as prop
    if (!propProjectId) {
      setProjectId(uuidv4());
    }
    setLogs([]);
    setFinalReport("");
    setIsReportStreaming(false);
  };

  const handleUploadAndAssess = async () => {
    if (files.length === 0 || !projectId) return;

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

      notifications.show({
        title: 'Success',
        message: 'Files uploaded successfully',
        color: 'green',
      });

      setIsUploading(false);
      setIsAssessing(true);

      // Start assessment via WebSocket
      const ws = apiService.createAssessmentWebSocket(projectId);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        const msg = event.data;
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
      };

    } catch (err) {
      setIsUploading(false);
      setIsAssessing(false);
      notifications.show({
        title: 'Error',
        message: 'Failed to upload files or start assessment',
        color: 'red',
      });
      setLogs((prev) => [...prev, "Error uploading files or starting assessment."]);
    }
  };

  return (
    <Stack spacing="lg">
      {/* File Upload Section */}
      <Card shadow="sm" p="lg" radius="md" withBorder>
        <Text size="lg" weight={600} mb="md">
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
          <Group position="center" spacing="xl" style={{ minHeight: 120, pointerEvents: 'none' }}>
            <IconUpload size={50} color="#868e96" />
            <div>
              <Text size="xl" inline>
                Drag documents here or click to select files
              </Text>
              <Text size="sm" color="dimmed" inline mt={7}>
                Attach infrastructure documents, network diagrams, application inventories, etc.
              </Text>
            </div>
          </Group>
        </Dropzone>

        {files.length > 0 && (
          <Paper p="md" mt="md" style={{ backgroundColor: '#f8f9fa' }}>
            <Text size="sm" weight={500} mb="xs">
              Selected Files ({files.length}):
            </Text>
            {files.map((file, index) => (
              <Group key={index} spacing="xs" mb="xs">
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
            leftIcon={<IconUpload size={16} />}
            onClick={handleUploadAndAssess}
            disabled={files.length === 0 || isUploading || isAssessing}
            loading={isUploading}
          >
            {isUploading ? 'Uploading...' : 'Upload & Start Assessment'}
          </Button>
          {isAssessing && (
            <Group spacing="xs">
              <Loader size="sm" />
              <Text size="sm" color="dimmed">Assessment in progress...</Text>
            </Group>
          )}
        </Group>
      </Card>

      {/* Uploaded Files Section */}
      <Card shadow="sm" p="lg" radius="md" withBorder>
        <Group position="apart" mb="md">
          <Text size="lg" weight={600}>
            Uploaded Files
          </Text>
          <Badge variant="light">
            {uploadedFiles.length} files
          </Badge>
        </Group>

        {loadingFiles ? (
          <Group position="center" p="md">
            <Loader size="sm" />
            <Text size="sm" color="dimmed">Loading files...</Text>
          </Group>
        ) : uploadedFiles.length === 0 ? (
          <Text size="sm" color="dimmed" ta="center" p="md">
            No files uploaded yet. Upload documents to start the assessment.
          </Text>
        ) : (
          <Table>
            <thead>
              <tr>
                <th>Filename</th>
                <th>Type</th>
                <th>Uploaded</th>
              </tr>
            </thead>
            <tbody>
              {uploadedFiles.map((file) => (
                <tr key={file.id}>
                  <td>
                    <Group spacing="xs">
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
      </Card>

      {/* Assessment Progress */}
      {logs.length > 0 && (
        <Card shadow="sm" p="lg" radius="md" withBorder>
          <Text size="lg" weight={600} mb="md">
            Assessment Progress
          </Text>
          <LiveConsole logs={logs} />
        </Card>
      )}

      {/* Final Report */}
      {finalReport && (
        <Card shadow="sm" p="lg" radius="md" withBorder>
          <Text size="lg" weight={600} mb="md">
            Assessment Report
          </Text>
          <ReportDisplay report={finalReport} />
        </Card>
      )}
    </Stack>
  );
};

export default FileUpload;
