import React, { useState, useRef, useEffect } from "react";
import { Button, Group, Stack, Text, Paper, Loader, Table, Badge, Card, Divider, Alert, Menu, Modal, ScrollArea, ActionIcon, Collapse, SimpleGrid, Tooltip, Switch } from "@mantine/core";
import { Dropzone } from "@mantine/dropzone";
import { IconFile, IconFolder, IconUpload, IconRefresh, IconAlertCircle, IconSettings, IconTestPipe, IconChevronDown, IconRobot, IconDatabase, IconCheck, IconList, IconGrid3x3, IconLayoutGrid, IconTrash, IconEye, IconEyeOff, IconDownload, IconPlayerPlay, IconPlus } from "@tabler/icons-react";
import { v4 as uuidv4 } from "uuid";
import { apiService, ProjectFile } from "../services/api";
import { notifications } from "@mantine/notifications";
import LiveConsole from "./LiveConsole";
import ReportDisplay from "./ReportDisplay";
import LLMConfigurationModal from './LLMConfigurationModal';
import RightLogPane from './RightLogPane';
import { useNotifications } from '../contexts/NotificationContext';
import { useAssessment } from '../contexts/AssessmentContext';

type FileUploadProps = {
  projectId?: string;
  onFilesUploaded?: () => void;
};

// Helper function to convert MIME types or filename extensions to friendly names
const getFriendlyFileType = (mimeTypeOrExt?: string, filename?: string): string => {
  const typeMap: { [key: string]: string } = {
    'application/pdf': 'PDF',
    'pdf': 'PDF',
    'application/msword': 'Word',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'Word',
    'doc': 'Word',
    'docx': 'Word',
    'application/vnd.ms-excel': 'Excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'Excel',
    'xls': 'Excel',
    'xlsx': 'Excel',
    'application/vnd.ms-powerpoint': 'PowerPoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'PowerPoint',
    'ppt': 'PowerPoint',
    'pptx': 'PowerPoint',
    'text/plain': 'Text',
    'txt': 'Text',
    'text/csv': 'CSV',
    'csv': 'CSV',
    'application/json': 'JSON',
    'json': 'JSON',
    'application/zip': 'ZIP',
    'zip': 'ZIP',
    'md': 'Markdown',
    'markdown': 'Markdown',
  };

  // First try explicit mime/type lookup
  if (mimeTypeOrExt && typeMap[mimeTypeOrExt]) return typeMap[mimeTypeOrExt];
  // If a MIME like 'text/markdown'
  if (mimeTypeOrExt && mimeTypeOrExt.toLowerCase().includes('markdown')) return 'Markdown';
  // Try filename extension
  const ext = filename && filename.includes('.') ? filename.split('.').pop()!.toLowerCase() : undefined;
  if (ext && typeMap[ext]) return typeMap[ext];
  return mimeTypeOrExt || 'Unknown';
};

const FileUpload: React.FC<FileUploadProps> = ({ projectId: propProjectId, onFilesUploaded }) => {
  const [files, setFiles] = useState<File[]>([]);
  const [uploadedFiles, setUploadedFiles] = useState<ProjectFile[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
  const [projectId, setProjectId] = useState<string>(propProjectId || "");
  const [isUploading, setIsUploading] = useState(false);
  const [isAssessing, setIsAssessing] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [finalReport, setFinalReport] = useState<string>("");
  const [isReportStreaming, setIsReportStreaming] = useState<boolean>(false);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [assessmentStartTime, setAssessmentStartTime] = useState<Date | null>(null);
  const [showDetailedFileList, setShowDetailedFileList] = useState(false);
  const [fileListExpanded, setFileListExpanded] = useState(false);
  const [fileViewMode, setFileViewMode] = useState<'list' | 'grid' | 'compact'>('list');
  const [testingLLM, setTestingLLM] = useState(false);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [llmConfigModalOpen, setLlmConfigModalOpen] = useState(false);
  const [currentProject, setCurrentProject] = useState<any>(null);
  const [rightLogPaneOpen, setRightLogPaneOpen] = useState(false);
  const [agenticLogs, setAgenticLogs] = useState<any[]>([]);
  const [clearingData, setClearingData] = useState(false);
  const [showAssessmentProgress, setShowAssessmentProgress] = useState(false);
  const [showUploadProgress, setShowUploadProgress] = useState(false);
  const [uploadLogs, setUploadLogs] = useState<string[]>([]);
  const [uploadStartTime, setUploadStartTime] = useState<Date | null>(null);
  const [reprocessFromSource, setReprocessFromSource] = useState<boolean>(false);
  const [migrationReportsExpanded, setMigrationReportsExpanded] = useState<boolean>(false);

  const wsRef = useRef<WebSocket | null>(null);
  const { addNotification } = useNotifications();
  const { startAssessment, addLog, setStatus } = useAssessment();

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
      // Use backend uploads listing (object storage) instead of project-service DB
      const files = await apiService.getProjectUploads(projectId);
      setUploadedFiles(files);
    } catch (error) {
      console.error('Error fetching uploaded files:', error);
    } finally {
      setLoadingFiles(false);
    }
  };

  const handleDrop = (acceptedFiles: File[], additive: boolean = false) => {
    // Check for duplicate files (both against uploaded files and currently selected files)
    const duplicateFiles = acceptedFiles.filter(newFile =>
      uploadedFiles.some(existingFile => existingFile.filename === newFile.name) ||
      (additive && files.some(existingFile => existingFile.name === newFile.name))
    );

    if (duplicateFiles.length > 0) {
      notifications.show({
        title: 'Duplicate Files Detected',
        message: `The following files already exist: ${duplicateFiles.map(f => f.name).join(', ')}`,
        color: 'orange',
      });
    }

    // Filter out duplicate files
    const uniqueFiles = acceptedFiles.filter(newFile =>
      !uploadedFiles.some(existingFile => existingFile.filename === newFile.name) &&
      !(additive && files.some(existingFile => existingFile.name === newFile.name))
    );

    if (additive) {
      // Add to existing files
      setFiles(prev => [...prev, ...uniqueFiles]);
    } else {
      // Replace existing files
      setFiles(uniqueFiles);
    }

    // Only generate new project ID if not provided as prop
    if (!propProjectId) {
      setProjectId(uuidv4());
    }
    setLogs([]);
    setFinalReport("");
    setIsReportStreaming(false);
  };

  const handleFolderUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = event.target.files;
    if (fileList) {
      const filesArray = Array.from(fileList);
      handleDrop(filesArray);

      notifications.show({
        title: 'Folder Uploaded',
        message: `Selected ${filesArray.length} files from folder structure`,
        color: 'blue',
      });
    }
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = event.target.files;
    if (fileList) {
      const filesArray = Array.from(fileList);
      handleDrop(filesArray, true); // Pass true to indicate additive selection

      notifications.show({
        title: 'Files Selected',
        message: `Selected ${filesArray.length} files`,
        color: 'blue',
      });
    }
  };

  const handleNativeToolDrop = async (acceptedFiles: File[], toolType: 'aws_migration_evaluator' | 'azure_migrate') => {
    if (acceptedFiles.length === 0) return;
    
    const file = acceptedFiles[0]; // Only one file allowed for native tools
    
    // Validate file type based on tool
    if (toolType === 'aws_migration_evaluator' && !file.name.toLowerCase().endsWith('.csv')) {
      notifications.show({
        title: 'Invalid File Type',
        message: 'AWS Migration Evaluator reports must be CSV files',
        color: 'red',
      });
      return;
    }
    
    if (toolType === 'azure_migrate' && !(/\.(csv|xls|xlsx)$/i.test(file.name))) {
      notifications.show({
        title: 'Invalid File Type', 
        message: 'Azure Migrate reports must be CSV, XLS, or XLSX files',
        color: 'red',
      });
      return;
    }
    
    if (!projectId) {
      setProjectId(uuidv4());
    }
    
    try {
      setIsUploading(true);
      setLogs([`🚀 Uploading ${toolType === 'aws_migration_evaluator' ? 'AWS Migration Evaluator' : 'Azure Migrate'} report...`]);
      
      // Upload the native tool report using the cloud tools service
      const formData = new FormData();
      formData.append('file', file);
      formData.append('tool_type', toolType);
      formData.append('project_id', projectId);
      
      const response = await fetch('http://localhost:8012/api/cloud-tools/upload-report', {
        method: 'POST',
        body: formData,
      });
      
      if (response.ok) {
        const result = await response.json();
        setLogs(prev => [...prev, `✅ ${toolType === 'aws_migration_evaluator' ? 'AWS Migration Evaluator' : 'Azure Migrate'} report uploaded successfully`]);
        setLogs(prev => [...prev, `📊 Processed ${result.records_count || 'unknown'} records`]);
        
        notifications.show({
          title: 'Report Uploaded Successfully',
          message: `${toolType === 'aws_migration_evaluator' ? 'AWS Migration Evaluator' : 'Azure Migrate'} report has been processed`,
          color: 'green',
        });
        
        addNotification({
          title: 'Native Tool Report Uploaded',
          message: `${toolType === 'aws_migration_evaluator' ? 'AWS Migration Evaluator' : 'Azure Migrate'} report uploaded and processed successfully`,
          type: 'success',
          projectId: projectId,
          metadata: {
            toolType,
            fileName: file.name,
            recordsCount: result.records_count
          }
        });
        
        // Refresh uploaded files
        await fetchUploadedFiles();
        
        // Trigger project stats refresh
        if (onFilesUploaded) {
          onFilesUploaded();
        }
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errorData.detail || `Failed to upload ${toolType} report`);
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      setLogs(prev => [...prev, `❌ Failed to upload ${toolType} report: ${errorMessage}`]);
      
      notifications.show({
        title: 'Upload Failed',
        message: `Failed to upload ${toolType === 'aws_migration_evaluator' ? 'AWS Migration Evaluator' : 'Azure Migrate'} report: ${errorMessage}`,
        color: 'red',
      });
      
      addNotification({
        title: 'Native Tool Report Upload Failed',
        message: `Error uploading ${toolType === 'aws_migration_evaluator' ? 'AWS Migration Evaluator' : 'Azure Migrate'} report: ${errorMessage}`,
        type: 'error',
        projectId: projectId,
        metadata: {
          toolType,
          fileName: file.name,
          errorType: 'upload_failed',
          error: errorMessage
        }
      });
    } finally {
      setIsUploading(false);
    }
  };

  const handleUploadOnly = async () => {
    if (!projectId || files.length === 0) {
      notifications.show({
        title: 'No Files Selected',
        message: 'Please select files to upload',
        color: 'orange',
      });
      return;
    }

    setIsUploading(true);
    setUploadStartTime(new Date());
    const initialLog = `🚀 Starting upload of ${files.length} file(s)...`;
    setLogs([initialLog]);
    setUploadLogs([initialLog]);

    try {
      // Upload files using the new API service with detailed progress tracking
      const uploadingLog = '📤 Uploading files to object storage...';
      setLogs(prev => [...prev, uploadingLog]);
      setUploadLogs(prev => [...prev, uploadingLog]);

      const response = await apiService.uploadFiles(projectId, files);
      console.log('Upload response:', response);

      if (response.uploaded_files) {
        // Process each uploaded file
        for (const uploadedFile of response.uploaded_files) {
          if (uploadedFile.status === 'uploaded') {
            const successLog = `✅ Uploaded: ${uploadedFile.filename} (${uploadedFile.size} bytes)`;
            setLogs(prev => [...prev, successLog]);
            setUploadLogs(prev => [...prev, successLog]);
          } else {
            const errorLog = `❌ Failed: ${uploadedFile.filename} - ${uploadedFile.error}`;
            setLogs(prev => [...prev, errorLog]);
            setUploadLogs(prev => [...prev, errorLog]);
          }
        }
      }

      const completedLog = '✅ Files uploaded and registered successfully';
      setLogs(prev => [...prev, completedLog]);
      setUploadLogs(prev => [...prev, completedLog]);

      // Count successful uploads (backend now handles registration automatically)
      const registeredCount = response.uploaded_files?.filter(f => f.status === 'uploaded').length || 0;

      // Clear selected files
      setFiles([]);

      // Refresh the uploaded files list
      setLogs(prev => [...prev, '🔄 Refreshing file list...']);
      await fetchUploadedFiles();

      // Trigger project stats refresh
      if (onFilesUploaded) {
        onFilesUploaded();
      }

      // Show success notification
      const fileNames = files.map(f => f.name).join(', ');
      setLogs(prev => [...prev, `🎉 Upload completed! ${registeredCount}/${files.length} files processed successfully`]);

      notifications.show({
        title: 'Upload Successful',
        message: `Successfully uploaded ${registeredCount}/${files.length} file(s)`,
        color: registeredCount === files.length ? 'green' : 'yellow',
      });

      addNotification({
        title: 'Files Uploaded Successfully',
        message: `Uploaded ${registeredCount}/${files.length} file(s): ${fileNames}`,
        type: 'success',
        projectId: projectId,
        metadata: { fileCount: files.length, fileNames, registeredCount }
      });

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
      setLogs(prev => [...prev, `❌ Upload failed: ${errorMessage}`]);

      console.error('Upload error:', err);

      notifications.show({
        title: 'Upload Failed',
        message: errorMessage,
        color: 'red',
      });

      addNotification({
        title: 'Upload Failed',
        message: `Error: ${errorMessage}`,
        type: 'error',
        projectId: projectId,
        metadata: { errorType: 'upload_failed', error: String(err) }
      });
    } finally {
      setIsUploading(false);
    }
  };

  // Function to validate knowledge graph data after processing
  const validateKnowledgeGraphData = async (projectId: string) => {
    try {
      addLog(`[INFO] Validating knowledge graph data for project ${projectId}...`);
      const response = await fetch(`http://localhost:8000/api/projects/${projectId}/graph`);

      if (response.ok) {
        const graphData = await response.json();
        console.log('Knowledge graph validation response:', graphData);

        const hasNodes = graphData.nodes && graphData.nodes.length > 0;
        const hasEdges = graphData.edges && graphData.edges.length > 0;

        if (hasNodes || hasEdges) {
          addLog(`[SUCCESS] Knowledge graph data validated: ${graphData.nodes?.length || 0} entities, ${graphData.edges?.length || 0} relationships`);

          // Also log some sample data for debugging
          if (graphData.nodes?.length > 0) {
            const sampleNodes = graphData.nodes.slice(0, 3).map((n: any) => n.label || n.name || n.id).join(', ');
            addLog(`[DEBUG] Sample entities: ${sampleNodes}`);
          }

          return true;
        } else {
          addLog(`[WARNING] No knowledge graph data found after processing. Response structure: ${JSON.stringify(Object.keys(graphData))}`);
          addLog(`[DEBUG] Full response: ${JSON.stringify(graphData).substring(0, 200)}...`);
          return false;
        }
      } else {
        const errorText = await response.text();
        addLog(`[WARNING] Could not validate knowledge graph data: ${response.status} - ${errorText}`);
        return false;
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      addLog(`[ERROR] Knowledge graph validation failed: ${errorMessage}`);
      console.error('Knowledge graph validation error:', error);
      return false;
    }
  };

  // Function to clear all embeddings and knowledge graph data for the project
  const handleClearProjectData = async () => {
    if (!projectId) return;

    const confirmed = window.confirm(
      'Are you sure you want to clear all embeddings and knowledge graph data for this project? This action cannot be undone.'
    );

    if (!confirmed) return;

    setClearingData(true);
    try {
      const response = await fetch(`http://localhost:8000/api/projects/${projectId}/clear-data`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const result = await response.json();
        const { weaviate_embeddings, neo4j_nodes, neo4j_relationships } = result;

        notifications.show({
          title: 'Data Cleared Successfully',
          message: `Cleared ${weaviate_embeddings} embeddings, ${neo4j_nodes} graph nodes, and ${neo4j_relationships} relationships.`,
          color: 'green',
        });
        addLog(`[SUCCESS] Project data cleared: ${weaviate_embeddings} embeddings, ${neo4j_nodes} nodes, ${neo4j_relationships} relationships`);

        // Refresh project stats after clearing
        if (onFilesUploaded) {
          setTimeout(() => {
            onFilesUploaded();
          }, 1000);
        }
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to clear data`);
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      notifications.show({
        title: 'Error',
        message: `Failed to clear project data: ${errorMessage}`,
        color: 'red',
      });
      addLog(`[ERROR] Failed to clear project data: ${errorMessage}`);
    } finally {
      setClearingData(false);
    }
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
        await apiService.addProjectFile(projectId, file.name, file.type, file.size);
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

      // Auto-show assessment progress
      setShowAssessmentProgress(true);

      // Start assessment in global context
      startAssessment(projectId);

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
        console.log('WebSocket message received:', msg); // Debug logging

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
            // Also add to regular logs for visibility
            setLogs(prev => [...prev, `[${parsedMessage.source}] ${parsedMessage.message}`]);
            return;
          }
        } catch {
          // If not JSON, continue with regular processing
        }

        if (msg === "PROCESSING_COMPLETED") {
          // Handle processing completion
          setIsAssessing(false);
          setStatus('completed');
          setLogs(prev => [...prev, "✅ Document processing completed successfully!"]);
          addLog('✅ Document processing completed successfully!');

          // Validate knowledge graph data was created
          setTimeout(async () => {
            await validateKnowledgeGraphData(projectId);
          }, 2000); // Wait 2 seconds for data to be fully committed

          notifications.show({
            title: '🎉 Processing Complete',
            message: 'Document processing completed! Your project is ready for analysis and document generation.',
            color: 'green',
            autoClose: 8000,
          });

          addNotification({
            title: 'Document Processing Completed',
            message: 'All documents have been processed and are ready for analysis. You can now generate reports and use the chat functionality.',
            type: 'success',
            projectId: projectId,
            metadata: {
              completedAt: new Date().toISOString(),
              startTime: assessmentStartTime?.toISOString(),
              processingType: 'document_processing'
            }
          });
        } else if (msg === "FINAL_REPORT_MARKDOWN_START") {
          setFinalReport("");
          setIsReportStreaming(true);
          setLogs(prev => [...prev, "📄 Starting report generation..."]);
        } else if (msg === "FINAL_REPORT_MARKDOWN_END") {
          setIsReportStreaming(false);
          setIsAssessing(false);
          setStatus('completed');
          setLogs(prev => [...prev, "✅ Assessment completed successfully!"]);
          addLog('✅ Assessment completed successfully!');

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
          // Add all messages to logs with timestamp
          const timestamp = new Date().toLocaleTimeString();
          setLogs((prev) => [...prev, `[${timestamp}] ${msg}`]);
          // Also add to global assessment context
          addLog(msg);
        }
      };

      ws.onclose = () => {
        setIsAssessing(false);
        setStatus('completed');
      };
      ws.onerror = () => {
        setIsAssessing(false);
        setStatus('failed');
        addLog('❌ Assessment connection failed');
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

  const handleStartAssessment = async () => {
    if (!projectId || uploadedFiles.length === 0) {
      notifications.show({
        title: 'No Files Available',
        message: 'Please upload files before starting assessment',
        color: 'orange',
      });
      return;
    }

    // Check if project has default LLM configuration
    if (!currentProject?.llm_provider) {
      notifications.show({
        title: 'LLM Configuration Required',
        message: 'Please configure a default LLM for this project in the Overview tab',
        color: 'orange',
      });
      return;
    }

    setIsAssessing(true);
    setAssessmentStartTime(new Date());
    setLogs([`Starting assessment with ${currentProject.llm_provider}/${currentProject.llm_model}...`]);
    setFinalReport("");
    setIsReportStreaming(false);
    setAgenticLogs([]);

    // Start assessment in global context
    startAssessment(projectId);

    try {
      // Start assessment via WebSocket for existing files
      const ws = apiService.createAssessmentWebSocket(projectId);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        const msg = event.data;
        console.log('WebSocket message received:', msg); // Debug logging

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
            // Also add to regular logs for visibility
            setLogs(prev => [...prev, `[${parsedMessage.source}] ${parsedMessage.message}`]);
            return;
          }
        } catch {
          // If not JSON, continue with regular processing
        }

        if (msg === "FINAL_REPORT_MARKDOWN_START") {
          setFinalReport("");
          setIsReportStreaming(true);
          setLogs(prev => [...prev, "📄 Starting report generation..."]);
        } else if (msg === "FINAL_REPORT_MARKDOWN_END") {
          setIsReportStreaming(false);
          setIsAssessing(false);
          setStatus('completed');
          setLogs(prev => [...prev, "✅ Assessment completed successfully!"]);
          addLog('✅ Assessment completed successfully!');

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
          // Add all messages to logs with timestamp
          const timestamp = new Date().toLocaleTimeString();
          setLogs((prev) => [...prev, `[${timestamp}] ${msg}`]);
          // Also add to global assessment context
          addLog(msg);
        }
      };

      ws.onclose = () => {
        setIsAssessing(false);
        setStatus('completed');
      };
      ws.onerror = () => {
        setIsAssessing(false);
        setStatus('failed');
        addLog('❌ Assessment connection failed');
        notifications.show({
          title: 'Error',
          message: 'Assessment connection failed',
          color: 'red',
        });
      };
    } catch (error) {
      setIsAssessing(false);
      setStatus('failed');
      const errorMessage = error instanceof Error ? error.message : String(error);
      addLog(`❌ Assessment failed: ${errorMessage}`);
      notifications.show({
        title: 'Assessment Error',
        message: 'Failed to start assessment',
        color: 'red',
      });
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

  const handleTestLLM = async () => {
    if (!projectId) {
      notifications.show({
        title: 'No Project Selected',
        message: 'Please select a project first',
        color: 'orange',
      });
      return;
    }

    if (!currentProject?.llm_provider) {
      notifications.show({
        title: 'LLM Configuration Required',
        message: 'Please configure a default LLM for this project in the Overview tab',
        color: 'orange',
      });
      return;
    }

    setTestingLLM(true);
    try {
      const response = await fetch(`http://localhost:8000/api/projects/${projectId}/test-llm`, {
        method: 'POST',
      });

      const result = await response.json();

      if (response.ok && result.status === 'success') {
        notifications.show({
          title: 'LLM Test Successful',
          message: `${currentProject.llm_provider}/${currentProject.llm_model} is working correctly`,
          color: 'green',
        });
      } else {
        notifications.show({
          title: 'LLM Test Failed',
          message: result.message || 'Failed to connect to LLM',
          color: 'red',
        });
      }
    } catch (error) {
      notifications.show({
        title: 'LLM Test Error',
        message: 'Failed to test LLM configuration',
        color: 'red',
      });
    } finally {
      setTestingLLM(false);
    }
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

  const handleStartProcessing = async () => {
    if (!projectId || uploadedFiles.length === 0) {
      notifications.show({
        title: 'No Files Available',
        message: 'Please upload files before starting processing',
        color: 'orange',
      });
      return;
    }

    // Check if project has default LLM configuration
    if (!currentProject?.llm_provider) {
      notifications.show({
        title: 'LLM Configuration Required',
        message: 'Please configure a default LLM for this project in the Overview tab',
        color: 'orange',
      });
      return;
    }

    setIsUploading(true);
    setShowAssessmentProgress(true); // Auto-show assessment progress
    setLogs([
      "🚀 Starting document processing with project's default LLM configuration...",
      `🤖 Using LLM: ${currentProject.llm_provider}/${currentProject.llm_model}`,
    ]);

    console.log('Starting document processing for project:', projectId);
    console.log('Using LLM configuration:', currentProject.llm_provider, '/', currentProject.llm_model);

    // Connect to WebSocket for real-time progress updates
    const wsUrl = `ws://localhost:8000/ws/process-documents/${projectId}?token=service-backend-token`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected for document processing');
      setLogs(prev => [...prev, "🔗 Connected to processing service..."]);
    };

    ws.onmessage = (event) => {
      const message = event.data;
      console.log('WebSocket message:', message);

      // Add real-time messages to logs
      setLogs(prev => [...prev, message]);

      // Check for completion
      if (message.includes('PROCESSING_COMPLETED') || message.includes('COMPLETE:')) {
        setIsUploading(false);

        // Auto-refresh stats after processing completion
        if (onFilesUploaded) {
          setTimeout(() => {
            onFilesUploaded();
            setLogs(prev => [...prev, "📊 Project statistics refreshed"]);
          }, 1000);
        }

        ws.close();
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setLogs(prev => [...prev, "❌ Connection error - falling back to HTTP processing"]);
    };

    try {
      // Call the processing endpoint to start the process
  console.log('Calling processing endpoint:', `http://localhost:8000/api/projects/${projectId}/process-documents`);
  const response = await fetch(`http://localhost:8000/api/projects/${projectId}/process-documents${reprocessFromSource ? '?reprocess=true' : ''}` , {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          use_project_llm: true, // Use project's default LLM
          files: uploadedFiles.map(f => ({ filename: f.filename, file_type: f.file_type }))
        })
      });

      console.log('Processing response status:', response.status);
      if (response.ok) {
        const result = await response.json();
        setLogs(prev => [...prev, "✅ Processing request submitted successfully"]);

        notifications.show({
          title: 'Processing Started',
          message: `Document processing started using ${currentProject.llm_provider}/${currentProject.llm_model}`,
          color: 'green',
        });
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        const correlationId = response.headers.get('X-Correlation-ID') || 'unknown';
        console.error('Processing failed with status:', response.status, 'CID:', correlationId, 'Error:', errorData);
        notifications.show({
          title: 'Processing Failed',
          message: `${errorData.detail || 'Failed to start processing'} — Correlation ID: ${correlationId} (click to copy)`,
          color: 'red',
          onClick: () => {
            if (correlationId && correlationId !== 'unknown') navigator.clipboard.writeText(correlationId);
          }
        });
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to start processing`);
      }
  } catch (error) {
      console.error('Processing error:', error);
      const errorMessage = error instanceof Error ? error.message : String(error);
      notifications.show({
        title: 'Processing Failed',
        message: `Failed to start document processing: ${errorMessage}`,
        color: 'red',
      });
      setLogs(prev => [...prev, `❌ Failed to start document processing: ${errorMessage}`]);
    } finally {
      setIsUploading(false);
    }
  };

  const handleLLMConfigSelected = async (configId: string) => {
    setIsUploading(true);
    setLogs(["Starting document processing with selected LLM configuration..."]);

    try {
      // Call the new processing endpoint with LLM config
      const response = await fetch(`http://localhost:8000/api/projects/${projectId}/process-documents`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          llm_config_id: configId
        })
      });

      if (response.ok) {
        notifications.show({
          title: 'Processing Started',
          message: 'Document processing has begun with selected LLM configuration.',
          color: 'green',
        });

        addNotification({
          title: 'Document Processing Started',
          message: `Creating project knowledge base using LLM configuration: ${configId}`,
          type: 'info',
          projectId: projectId,
          metadata: { startTime: new Date().toISOString(), llmConfigId: configId }
        });
        
        // Also create backend notification with correlation ID
        try {
          const correlationId = `doc-process-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
          await apiService.createNotification('user_001', projectId, {
            notification_type: 'info',
            title: 'Document Processing Started',
            message: `Creating project knowledge base using LLM configuration: ${configId}`,
            correlation_id: correlationId,
            metadata: { 
              startTime: new Date().toISOString(), 
              llmConfigId: configId,
              project_id: projectId,
              action: 'document_processing'
            }
          });
        } catch (error) {
          console.error('Failed to create backend notification:', error);
        }

        setLogs(prev => [...prev, "✅ Document processing initiated"]);
        setLogs(prev => [...prev, "📊 Creating knowledge base..."]);
        setLogs(prev => [...prev, "🔍 Extracting entities and relationships..."]);
        setLogs(prev => [...prev, "🤖 Using selected LLM configuration for enhanced processing..."]);
      } else {
        throw new Error('Failed to start processing');
      }
    } catch (error) {
      notifications.show({
        title: 'Processing Error',
        message: 'Failed to start document processing',
        color: 'red',
      });

      addNotification({
        title: 'Document Processing Failed',
        message: `Error: ${error instanceof Error ? error.message : 'Unknown error occurred'}`,
        type: 'error',
        projectId: projectId,
        metadata: { errorType: 'processing_failed', error: String(error) }
      });

      setLogs(prev => [...prev, "❌ Document processing failed"]);
    } finally {
      setIsUploading(false);
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

  const handleDownloadFile = async (file: ProjectFile) => {
    try {
      const response = await apiService.downloadFile(projectId, file.filename);
      const blob = new Blob([response]);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = file.filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      notifications.show({
        title: 'Download Started',
        message: `Downloading ${file.filename}`,
        color: 'blue',
      });
    } catch (error) {
      notifications.show({
        title: 'Download Failed',
        message: `Failed to download ${file.filename}`,
        color: 'red',
      });
    }
  };

  const handleDeleteFile = async (fileId: string) => {
    try {
      await apiService.deleteProjectFile(projectId, fileId);
      await fetchUploadedFiles();
      setSelectedFiles(prev => prev.filter(id => id !== fileId));

      notifications.show({
        title: 'File Deleted',
        message: 'File deleted successfully',
        color: 'green',
      });
    } catch (error) {
      notifications.show({
        title: 'Delete Failed',
        message: 'Failed to delete file',
        color: 'red',
      });
    }
  };

  const handleBulkDownload = async () => {
  const selectedFileObjects = uploadedFiles.filter(f => selectedFiles.includes(f.id || f.filename));
    for (const file of selectedFileObjects) {
      await handleDownloadFile(file);
    }
  };

  const handleBulkDelete = async () => {
    try {
      for (const fileId of selectedFiles) {
        await apiService.deleteProjectFile(projectId, fileId);
      }
      await fetchUploadedFiles();
      setSelectedFiles([]);

      notifications.show({
        title: 'Files Deleted',
        message: `${selectedFiles.length} file(s) deleted successfully`,
        color: 'green',
      });
    } catch (error) {
      notifications.show({
        title: 'Delete Failed',
        message: 'Failed to delete selected files',
        color: 'red',
      });
    }
  };

  const handleProcessSelected = async () => {
    if (selectedFiles.length === 0) {
      notifications.show({
        title: 'No Files Selected',
        message: 'Please select files to process',
        color: 'orange',
      });
      return;
    }

    try {
      setIsAssessing(true);
      setLogs([]);
      setShowAssessmentProgress(true);

      // Get selected file objects
  const selectedFileObjects = uploadedFiles.filter(f => selectedFiles.includes(f.id || f.filename));

      setLogs(prev => [...prev, `🚀 Starting processing of ${selectedFiles.length} selected files...`]);
      setLogs(prev => [...prev, `📁 Selected files: ${selectedFileObjects.map(f => f.filename).join(', ')}`]);

      // Open a WebSocket to receive progress updates for selected processing as well
      try {
        const wsUrl = `ws://localhost:8000/ws/process-documents/${projectId}?token=service-backend-token`;
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          setLogs(prev => [...prev, "🔗 Connected to processing service for live updates..."]);
        };

        ws.onmessage = (event) => {
          const message = event.data;
          setLogs(prev => [...prev, message]);
          if (message.includes('PROCESSING_COMPLETED') || message.includes('COMPLETE:')) {
            setIsAssessing(false);
            if (onFilesUploaded) {
              setTimeout(() => onFilesUploaded(), 1000);
            }
            try { ws.close(); } catch {}
          }
        };

        ws.onerror = () => {
          setLogs(prev => [...prev, "⚠️ WebSocket error while monitoring selected processing"]);
        };
      } catch {
        // Non-fatal if WS cannot connect; HTTP will still start processing
      }

    // Call the processing endpoint with selected files (explicit selected route)
    const response = await fetch(`http://localhost:8000/api/projects/${projectId}/process-selected`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
      file_names: selectedFileObjects.map(f => f.filename),
      reprocess: !!reprocessFromSource
        })
      });

  if (response.ok) {
        setLogs(prev => [...prev, "✅ Selected document processing initiated"]);
        setLogs(prev => [...prev, "📊 Creating knowledge base from selected files..."]);
        setLogs(prev => [...prev, "🔍 Extracting entities and relationships..."]);

        notifications.show({
          title: 'Processing Started',
          message: `Processing ${selectedFiles.length} selected files`,
          color: 'green',
        });
  } else {
        const correlationId = response.headers.get('X-Correlation-ID') || 'unknown';
        notifications.show({
          title: 'Processing Error',
          message: `Failed to start processing selected files — Correlation ID: ${correlationId} (click to copy)`,
          color: 'red',
          onClick: () => {
            if (correlationId && correlationId !== 'unknown') navigator.clipboard.writeText(correlationId);
          }
        });
        throw new Error('Failed to start processing selected files');
      }
    } catch (error) {
      notifications.show({
        title: 'Processing Error',
        message: 'Failed to start processing selected files',
        color: 'red',
      });
      setIsAssessing(false);
      setShowAssessmentProgress(false);
    }
  };

  return (
    <Stack gap="lg">
      {/* Simple toggle for reprocess */}
      <Group justify="space-between">
        <Text size="sm">Reprocess from source files (ignore cached Markdown)</Text>
        <Switch checked={reprocessFromSource} onChange={(e) => setReprocessFromSource(e.currentTarget.checked)} />
      </Group>
      
      {/* Native Tool Reports Section */}
      <Card shadow="sm" p="md" radius="md" withBorder style={{ backgroundColor: '#e7f5ff' }}>
        <Group justify="space-between" align="center" onClick={() => setMigrationReportsExpanded(!migrationReportsExpanded)} style={{ cursor: 'pointer' }}>
          <Text size="lg" fw={600} c="blue">
            📊 Upload AWS/Azure Migration tools report
          </Text>
          <ActionIcon variant="subtle" size="sm">
            {migrationReportsExpanded ? <IconChevronDown size={16} /> : <IconPlus size={16} />}
          </ActionIcon>
        </Group>
        
        <Collapse in={migrationReportsExpanded}>
        <Text size="sm" c="dimmed" mb="md" mt="sm">
          Upload reports from AWS Migration Evaluator or Azure Migrate for enhanced assessment capabilities.
        </Text>
        
        <SimpleGrid cols={2} spacing="md">
          {/* AWS Migration Evaluator */}
          <Card shadow="xs" p="md" radius="md" withBorder style={{ backgroundColor: '#fff3cd' }}>
            <Stack gap="sm">
              <Group gap="sm">
                <div style={{ 
                  width: 32, 
                  height: 32, 
                  backgroundColor: '#ff9900', 
                  borderRadius: '6px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'white',
                  fontWeight: 600,
                  fontSize: '12px'
                }}>
                  AWS
                </div>
                <div>
                  <Text size="md" fw={600}>AWS Migration Evaluator</Text>
                  <Text size="xs" c="dimmed">Upload CSV export from AWS Migration Evaluator</Text>
                </div>
              </Group>
              
              <Dropzone
                onDrop={(files) => handleNativeToolDrop(files, 'aws_migration_evaluator')}
                accept={{ 'text/csv': ['.csv'] }}
                maxFiles={1}
                multiple={false}
              >
                <Group justify="center" gap="sm" style={{ minHeight: 40, pointerEvents: 'none' }}>
                  <IconUpload size={16} color="#ff9900" />
                  <Text size="sm" c="orange">Drop AWS Migration Evaluator CSV here</Text>
                </Group>
              </Dropzone>
              
              <Text size="xs" c="dimmed">
                📁 Accepted: CSV files only
                <br />📋 Export your assessment data from AWS Migration Evaluator
              </Text>
            </Stack>
          </Card>
          
          {/* Azure Migrate */}
          <Card shadow="xs" p="md" radius="md" withBorder style={{ backgroundColor: '#e1f5fe' }}>
            <Stack gap="sm">
              <Group gap="sm">
                <div style={{ 
                  width: 32, 
                  height: 32, 
                  backgroundColor: '#0078d4', 
                  borderRadius: '6px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'white',
                  fontWeight: 600,
                  fontSize: '10px'
                }}>
                  AZ
                </div>
                <div>
                  <Text size="md" fw={600}>Azure Migrate</Text>
                  <Text size="xs" c="dimmed">Upload CSV/Excel export from Azure Migrate</Text>
                </div>
              </Group>
              
              <Dropzone
                onDrop={(files) => handleNativeToolDrop(files, 'azure_migrate')}
                accept={{ 
                  'text/csv': ['.csv'],
                  'application/vnd.ms-excel': ['.xls'],
                  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx']
                }}
                maxFiles={1}
                multiple={false}
              >
                <Group justify="center" gap="sm" style={{ minHeight: 40, pointerEvents: 'none' }}>
                  <IconUpload size={16} color="#0078d4" />
                  <Text size="sm" c="blue">Drop Azure Migrate report here</Text>
                </Group>
              </Dropzone>
              
              <Text size="xs" c="dimmed">
                📁 Accepted: CSV, XLS, XLSX files
                <br />📋 Export your assessment data from Azure Migrate
              </Text>
            </Stack>
          </Card>
        </SimpleGrid>
        
        <Alert color="blue" mt="md" icon={<IconAlertCircle size={16} />}>
          <Text size="sm">
            <strong>Enhanced Assessment:</strong> Native tool reports provide detailed infrastructure data for more accurate migration recommendations and cost estimates.
          </Text>
        </Alert>
        </Collapse>
      </Card>
      
      {/* File Upload Section - Compact */}
      <Card shadow="sm" p="sm" radius="md" withBorder>
        <Text size="md" fw={600} mb="xs">
          Upload Documents
        </Text>
        
        <Group gap="sm" align="stretch">
          {/* Select Files Button */}
          <Menu shadow="md" width={180}>
            <Menu.Target>
              <Button
                variant="light"
                size="sm"
                rightSection={<IconChevronDown size={14} />}
                leftSection={<IconUpload size={14} />}
              >
                Select Files
              </Button>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Item
                leftSection={<IconFile size={14} />}
                onClick={() => fileInputRef.current?.click()}
              >
                Multiple Files
              </Menu.Item>
              <Menu.Item
                leftSection={<IconFolder size={14} />}
                onClick={() => folderInputRef.current?.click()}
              >
                Folder
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>
          
          {/* Drag Zone */}
          <Dropzone
            onDrop={handleDrop}
            multiple
            accept={{
              'application/pdf': ['.pdf'],
              'application/msword': ['.doc'],
              'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
              'text/plain': ['.txt'],
              'text/csv': ['.csv'],
              'application/vnd.ms-excel': ['.xls'],
              'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
              'application/vnd.ms-powerpoint': ['.ppt'],
              'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
              'application/json': ['.json'],
              'application/zip': ['.zip'],
            }}
            style={{ flex: 1 }}
          >
            <Group justify="center" gap="sm" style={{ minHeight: 30, pointerEvents: 'none', padding: '4px' }}>
              <IconUpload size={20} color="#868e96" />
              <Text size="sm">Drag files here or click to upload</Text>
            </Group>
          </Dropzone>
        </Group>
        
        {/* Hidden file inputs */}
        <input
          type="file"
          ref={fileInputRef}
          style={{ display: 'none' }}
          multiple
          accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.json,.zip"
          onChange={handleFileSelect}
        />
        <input
          type="file"
          ref={folderInputRef}
          style={{ display: 'none' }}
          multiple
          {...({ webkitdirectory: 'true' } as any)}
          onChange={handleFolderUpload}
        />

        {/* Upload controls */}
        {files.length > 0 && (
          <Group gap="xs" mt="sm">
            <Text size="xs" c="dimmed">{files.length} files selected</Text>
            <Button
              size="sm"
              onClick={handleUploadOnly}
              disabled={isUploading || isAssessing}
              loading={isUploading}
              leftSection={<IconUpload size={14} />}
            >
              Upload
            </Button>
            <Button
              size="sm"
              variant="subtle"
              color="gray"
              leftSection={showUploadProgress ? <IconEyeOff size={14} /> : <IconEye size={14} />}
              onClick={() => setShowUploadProgress(!showUploadProgress)}
            >
              {showUploadProgress ? 'Hide' : 'Show'} Progress
            </Button>
          </Group>
        )}

        {/* Selected Files Preview - Elongated */}
        {files.length > 0 && (
          <Card shadow="sm" p="sm" radius="md" withBorder mt="sm">
            <Group justify="space-between" mb="xs">
              <Text size="sm" fw={600}>Selected Files ({files.length})</Text>
              <Button
                size="xs"
                variant="subtle"
                color="red"
                onClick={() => setFiles([])}
              >
                Clear All
              </Button>
            </Group>
            <ScrollArea h={files.length > 5 ? 300 : Math.max(150, files.length * 50)} style={{ minHeight: 150 }}>
              <Stack gap="xs">
                {files.map((file, index) => (
                  <Group key={index} justify="space-between" p="xs" style={{ backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
                    <Group gap="xs">
                      <IconFile size={16} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <Text size="sm" style={{ wordBreak: 'break-all' }}>{file.name}</Text>
                        <Text size="xs" c="dimmed">
                          {(file.size / 1024 / 1024).toFixed(2)} MB • {getFriendlyFileType(file.type, file.name)}
                        </Text>
                      </div>
                    </Group>
                    <ActionIcon
                      size="sm"
                      variant="subtle"
                      color="red"
                      onClick={() => setFiles(prev => prev.filter((_, i) => i !== index))}
                    >
                      <IconTrash size={14} />
                    </ActionIcon>
                  </Group>
                ))}
              </Stack>
            </ScrollArea>
          </Card>
        )}
      </Card>

      {/* Upload Progress - Conditionally shown */}
      {showUploadProgress && (uploadLogs.length > 0 || isUploading) && (
        <Card shadow="sm" p="md" radius="md" withBorder>
          <Group justify="space-between" mb="md">
            <Text size="lg" fw={600}>
              Upload Progress
            </Text>
            {uploadStartTime && (
              <Text size="sm" c="dimmed">
                Started: {uploadStartTime!.toLocaleString()}
              </Text>
            )}
          </Group>
          <LiveConsole logs={uploadLogs.length > 0 ? uploadLogs : ["Initializing upload..."]} />
        </Card>
      )}

      {/* Assessment Actions - Above Uploaded Files */}
      {uploadedFiles.length > 0 && (
        <Card shadow="sm" p="md" radius="md" withBorder style={{ backgroundColor: '#f8f9fa' }}>
          <Group gap="md" justify="center">
            <Button
              leftSection={<IconDatabase size={16} />}
              onClick={handleStartProcessing}
              disabled={uploadedFiles.length === 0 || isAssessing || isUploading}
              variant="filled"
              color="blue"
            >
              Start Processing
            </Button>

            <Button
              leftSection={<IconTrash size={16} />}
              onClick={handleClearProjectData}
              disabled={clearingData || isAssessing || isUploading}
              variant="outline"
              color="red"
              loading={clearingData}
            >
              Clear Embeddings/Graph Data
            </Button>

            <Button
              leftSection={showAssessmentProgress ? <IconEyeOff size={16} /> : <IconEye size={16} />}
              onClick={() => setShowAssessmentProgress(!showAssessmentProgress)}
              variant="subtle"
              color="gray"
            >
              {showAssessmentProgress ? 'Hide' : 'Show'} Progress
            </Button>

            {/* Test LLM and Configure LLM buttons removed as requested */}

            {isAssessing && (
              <Group gap="xs">
                <Loader size="sm" />
                <Text size="sm" c="dimmed">Assessment in progress...</Text>
              </Group>
            )}
          </Group>
        </Card>
      )}

      {/* Assessment Progress - Conditionally shown */}
      {showAssessmentProgress && (logs.length > 0 || isAssessing) && (
        <Card shadow="sm" p="md" radius="md" withBorder>
          <Group justify="space-between" mb="md">
            <Text size="lg" fw={600}>
              Assessment Progress
            </Text>
            {assessmentStartTime && (
              <Text size="sm" c="dimmed">
                Started: {assessmentStartTime!.toLocaleString()}
              </Text>
            )}
          </Group>
          <LiveConsole logs={logs.length > 0 ? logs : ["Initializing assessment..."]} />
        </Card>
      )}

      {/* Uploaded Files Section */}
      <Card shadow="sm" p="lg" radius="md" withBorder>
        <Group justify="space-between" mb="md">
          <Text size="lg" fw={600}>
            Uploaded Files
          </Text>
          <Group gap="sm">
            <Badge variant="light">
              {uploadedFiles.length} files
            </Badge>

            {/* View Mode Toggle */}
            <Group gap="xs">
              <Tooltip label="List View">
                <ActionIcon
                  variant={fileViewMode === 'list' ? 'filled' : 'light'}
                  size="sm"
                  onClick={() => setFileViewMode('list')}
                >
                  <IconList size={16} />
                </ActionIcon>
              </Tooltip>
              <Tooltip label="Grid View">
                <ActionIcon
                  variant={fileViewMode === 'grid' ? 'filled' : 'light'}
                  size="sm"
                  onClick={() => setFileViewMode('grid')}
                >
                  <IconGrid3x3 size={16} />
                </ActionIcon>
              </Tooltip>
              <Tooltip label="Compact View">
                <ActionIcon
                  variant={fileViewMode === 'compact' ? 'filled' : 'light'}
                  size="sm"
                  onClick={() => setFileViewMode('compact')}
                >
                  <IconLayoutGrid size={16} />
                </ActionIcon>
              </Tooltip>
            </Group>

            <Button
              size="xs"
              variant="light"
              leftSection={<IconRefresh size={14} />}
              onClick={fetchUploadedFiles}
              loading={loadingFiles}
              disabled={isUploading || isAssessing}
            >
              Refresh
            </Button>
          </Group>
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
          <>
            {/* Bulk Actions */}
            {selectedFiles.length > 0 && (
              <Group justify="space-between" mb="md" p="sm" style={{ backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
                <Text size="sm" fw={500}>
                  {selectedFiles.length} file(s) selected
                </Text>
                <Group gap="xs">
                  <Button
                    size="xs"
                    variant="filled"
                    color="green"
                    leftSection={<IconPlayerPlay size={14} />}
                    onClick={handleProcessSelected}
                    disabled={isAssessing || isUploading}
                  >
                    Process Selected
                  </Button>
                  <Button
                    size="xs"
                    variant="light"
                    color="blue"
                    leftSection={<IconDownload size={14} />}
                    onClick={handleBulkDownload}
                  >
                    Download Selected
                  </Button>
                  <Button
                    size="xs"
                    variant="light"
                    color="red"
                    leftSection={<IconTrash size={14} />}
                    onClick={handleBulkDelete}
                  >
                    Delete Selected
                  </Button>
                </Group>
              </Group>
            )}

            {/* List View */}
            {fileViewMode === 'list' && (
              <Table>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th style={{ textAlign: 'left', width: '40px' }}>
                      <input
                        type="checkbox"
                          checked={selectedFiles.length === uploadedFiles.length && uploadedFiles.length > 0}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedFiles(uploadedFiles.map(f => f.id || f.filename));
                            } else {
                              setSelectedFiles([]);
                            }
                          }}
                      />
                    </Table.Th>
                    <Table.Th style={{ textAlign: 'left', width: '40px' }}>
                      Status
                    </Table.Th>
                    <Table.Th style={{ textAlign: 'left' }}>Filename</Table.Th>
                    <Table.Th style={{ textAlign: 'left' }}>Type</Table.Th>
                    <Table.Th style={{ textAlign: 'left' }}>Size</Table.Th>
                    <Table.Th style={{ textAlign: 'left' }}>Uploaded</Table.Th>
                    <Table.Th style={{ textAlign: 'left' }}>Actions</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {uploadedFiles.filter(file => file && file.filename).map((file) => (
                    <Table.Tr key={file.id || file.filename}>
                      <Table.Td>
                        <input
                          type="checkbox"
                          checked={selectedFiles.includes(file.id || file.filename)}
                          onChange={(e) => {
                            const fileId = file.id || file.filename;
                            if (e.target.checked) {
                              setSelectedFiles(prev => [...prev, fileId]);
                            } else {
                              setSelectedFiles(prev => prev.filter(id => id !== fileId));
                            }
                          }}
                        />
                      </Table.Td>
                      <Table.Td>
                        <Tooltip label={file.processing_status === 'completed' ? 'Processing completed successfully' : file.processing_status === 'processing' ? 'Currently processing' : 'Not processed yet'}>
                          <input
                            type="checkbox"
                            checked={file.processing_status === 'completed'}
                            disabled
                            style={{ 
                              accentColor: file.processing_status === 'completed' ? 'green' : '#ccc',
                              cursor: 'default'
                            }}
                          />
                        </Tooltip>
                      </Table.Td>
                      <Table.Td>
                        <Group gap="xs">
                          <IconFile size={16} />
                          <Text size="sm">{String(file.filename || 'Unknown')}</Text>
                        </Group>
                      </Table.Td>
                      <Table.Td>
                        <Badge size="sm" variant="light">
                          {getFriendlyFileType(file.file_type, file.filename)}
                        </Badge>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm" c="dimmed">
                          {file.file_size ? `${(file.file_size / 1024 / 1024).toFixed(2)} MB` : 'Unknown'}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm" c="dimmed">
                          {file.uploaded_at ? new Date(file.uploaded_at).toLocaleString() : (file.upload_timestamp ? new Date(file.upload_timestamp).toLocaleString() : 'Unknown')}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        <Group gap="xs">
                          <Tooltip label="Download">
                            <ActionIcon
                              size="sm"
                              variant="subtle"
                              color="blue"
                              onClick={() => handleDownloadFile(file)}
                            >
                              <IconDownload size={14} />
                            </ActionIcon>
                          </Tooltip>
                          <Tooltip label="Delete">
                            <ActionIcon
                              size="sm"
                              variant="subtle"
                              color="red"
                              onClick={() => handleDeleteFile(file.filename)}
                            >
                              <IconTrash size={14} />
                            </ActionIcon>
                          </Tooltip>
                        </Group>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            )}

            {/* Grid View */}
            {fileViewMode === 'grid' && (
              <SimpleGrid cols={3} spacing="md">
                {uploadedFiles.filter(file => file && file.filename).map((file) => (
                  <Paper key={file.id || file.filename} p="md" withBorder>
                    <Stack gap="xs">
                      <Group gap="xs">
                        <IconFile size={20} />
                        <IconCheck size={16} color="green" />
                      </Group>
                      <Text size="sm" fw={500} style={{ wordBreak: 'break-word' }}>
                        {String(file.filename || 'Unknown')}
                      </Text>
                      <Group justify="space-between">
                        <Badge size="xs" variant="light">
                          {getFriendlyFileType(file.file_type, file.filename)}
                        </Badge>
                        <Text size="xs" c="dimmed">
                          {file.file_size ? `${(file.file_size / 1024 / 1024).toFixed(1)}MB` : ''}
                        </Text>
                      </Group>
                      <Text size="xs" c="dimmed">
                        {file.uploaded_at ? new Date(file.uploaded_at).toLocaleDateString() : (file.upload_timestamp ? new Date(file.upload_timestamp).toLocaleDateString() : '')}
                      </Text>
                    </Stack>
                  </Paper>
                ))}
              </SimpleGrid>
            )}

            {/* Compact View */}
            {fileViewMode === 'compact' && (
              <SimpleGrid cols={3} spacing="sm">
                {uploadedFiles.filter(file => file && file.filename).map((file) => (
                  <Paper key={file.id || file.filename} p="sm" withBorder style={{ cursor: 'pointer' }}>
                    <Stack gap="xs">
                      <Group gap="xs" align="flex-start">
                        <IconFile size={18} style={{ marginTop: '2px', flexShrink: 0 }} />
                        <Stack gap={2} style={{ flex: 1, minWidth: 0 }}>
                          <Text size="sm" fw={500} style={{
                            wordBreak: 'break-word',
                            lineHeight: 1.3
                          }}>
                            {String(file.filename || 'Unknown')}
                          </Text>
                          <Group gap="xs">
                            <Badge size="xs" variant="light">
                              {getFriendlyFileType(file.file_type, file.filename)}
                            </Badge>
                            <Text size="xs" c="dimmed">
                              {(file.uploaded_at ? new Date(file.uploaded_at).toLocaleDateString() : (file.upload_timestamp ? new Date(file.upload_timestamp).toLocaleDateString() : ''))}
                            </Text>
                          </Group>
                        </Stack>
                      </Group>
                    </Stack>
                  </Paper>
                ))}
              </SimpleGrid>
            )}
          </>
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

      {/* Note: Test LLM Modal and LLM Configuration Selector removed */}
      {/* Projects now use their default LLM configuration */}

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

      {/* Detailed File List Modal */}
      <Modal
        opened={showDetailedFileList}
        onClose={() => setShowDetailedFileList(false)}
        title="Detailed File List"
        size="lg"
      >
        <ScrollArea h={400}>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Filename</Table.Th>
                <Table.Th>Type</Table.Th>
                <Table.Th>Size</Table.Th>
                <Table.Th>Uploaded</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {uploadedFiles.filter(file => file && file.filename).map((file) => (
                <Table.Tr key={file.id || file.filename}>
                  <Table.Td>
                    <Group gap="xs">
                      <IconFile size={16} />
                      <Text size="sm" style={{ wordBreak: 'break-all' }}>
                        {String(file.filename || 'Unknown')}
                      </Text>
                    </Group>
                  </Table.Td>
                  <Table.Td>
                    <Badge size="sm" variant="light">
                      {getFriendlyFileType(file.file_type)}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">
                      {file.file_size ? `${(file.file_size / 1024 / 1024).toFixed(2)} MB` : 'Unknown'}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" c="dimmed">
                      {(file.uploaded_at ? new Date(file.uploaded_at).toLocaleString() : (file.upload_timestamp ? new Date(file.upload_timestamp).toLocaleString() : ''))}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </ScrollArea>

        <Group justify="space-between" mt="md">
          <Text size="sm" c="dimmed">
            Total: {uploadedFiles.length} files
          </Text>
          <Button onClick={() => setShowDetailedFileList(false)}>
            Close
          </Button>
        </Group>
      </Modal>
    </Stack>
  );
};

export default FileUpload;
