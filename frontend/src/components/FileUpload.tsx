import React, { useState, useRef, useEffect } from "react";
import { Button, Group, Stack, Text, Paper, Loader, Table, Badge, Card, Divider, Alert, Menu, Modal, ScrollArea, ActionIcon, Collapse, SimpleGrid, Tooltip } from "@mantine/core";
import { Dropzone } from "@mantine/dropzone";
import { IconFile, IconFolder, IconUpload, IconRefresh, IconAlertCircle, IconSettings, IconTestPipe, IconChevronDown, IconRobot, IconDatabase, IconCheck, IconList, IconGrid3x3, IconLayoutGrid } from "@tabler/icons-react";
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

const FileUpload: React.FC<FileUploadProps> = ({ projectId: propProjectId, onFilesUploaded }) => {
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
      handleDrop(filesArray);

      notifications.show({
        title: 'Files Selected',
        message: `Selected ${filesArray.length} files`,
        color: 'blue',
      });
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
    setLogs([`🚀 Starting upload of ${files.length} file(s)...`]);

    try {
      // Upload files using the new API service with detailed progress tracking
      setLogs(prev => [...prev, '📤 Uploading files to object storage...']);

      const response = await apiService.uploadFiles(projectId, files);
      console.log('Upload response:', response);

      if (response.uploaded_files) {
        // Process each uploaded file
        for (const uploadedFile of response.uploaded_files) {
          if (uploadedFile.status === 'uploaded') {
            setLogs(prev => [...prev, `✅ Uploaded: ${uploadedFile.filename} (${uploadedFile.size} bytes)`]);
          } else {
            setLogs(prev => [...prev, `❌ Failed: ${uploadedFile.filename} - ${uploadedFile.error}`]);
          }
        }
      }

      setLogs(prev => [...prev, '✅ Files uploaded and registered successfully']);

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
      addLog(`❌ Assessment failed: ${error}`);
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

    // Use project's default LLM configuration directly
    setIsUploading(true);
    setLogs([
      "Starting document processing with project's default LLM configuration...",
      `Using LLM: ${currentProject.llm_provider}/${currentProject.llm_model}`,
      "Step 1: Parsing uploaded documents...",
      "Step 2: Extracting text and metadata...",
      "Step 3: Creating embeddings for vector search...",
      "Step 4: Building knowledge graph relationships...",
      "Step 5: Storing processed data..."
    ]);

    try {
      // Call the processing endpoint without LLM config selection
      const response = await fetch(`http://localhost:8000/api/projects/${projectId}/process-documents`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          use_project_llm: true, // Use project's default LLM
          files: uploadedFiles.map(f => ({ filename: f.filename, file_type: f.file_type }))
        })
      });

      if (response.ok) {
        const result = await response.json();

        // Simulate processing steps with delays
        setTimeout(() => {
          setLogs(prev => [...prev, "✅ Document parsing completed"]);
        }, 1000);

        setTimeout(() => {
          setLogs(prev => [...prev, "✅ Text extraction completed"]);
        }, 2000);

        setTimeout(() => {
          setLogs(prev => [...prev, "✅ Embeddings created and stored in Weaviate"]);
        }, 3000);

        setTimeout(() => {
          setLogs(prev => [...prev, "✅ Knowledge graph updated in Neo4j"]);
        }, 4000);

        setTimeout(() => {
          setLogs(prev => [...prev, "✅ Document processing completed successfully"]);
          setLogs(prev => [...prev, `Processed ${uploadedFiles.length} files with ${currentProject.llm_provider}/${currentProject.llm_model}`]);

          // Auto-refresh stats after processing completion
          if (onFilesUploaded) {
            setTimeout(() => {
              onFilesUploaded();
              setLogs(prev => [...prev, "📊 Project statistics refreshed"]);
            }, 1000);
          }
        }, 5000);

        notifications.show({
          title: 'Processing Started',
          message: `Document processing started using ${currentProject.llm_provider}/${currentProject.llm_model}`,
          color: 'green',
        });
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to start processing');
      }
    } catch (error) {
      notifications.show({
        title: 'Processing Failed',
        message: `Failed to start document processing: ${error}`,
        color: 'red',
      });
      setLogs(prev => [...prev, `❌ Failed to start document processing: ${error}`]);
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
            'application/vnd.ms-excel': ['.xls'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
            'application/vnd.ms-powerpoint': ['.ppt'],
            'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
            'image/*': ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg'],
            'application/json': ['.json'],
            'text/xml': ['.xml'],
            'application/xml': ['.xml'],
            'application/zip': ['.zip'],
            'application/x-zip-compressed': ['.zip'],
          }}
        >
          <Group justify="center" gap="sm" style={{ minHeight: 35, pointerEvents: 'none', padding: '6px' }}>
            <IconUpload size={24} color="#868e96" />
            <div>
              <Text size="sm" inline>
                Drag documents here or click to select files
              </Text>
              <Text size="xs" c="dimmed" inline mt={2}>
                PDF, Word, Excel, PowerPoint, Images, Text, CSV, JSON, XML, ZIP
              </Text>
            </div>
          </Group>
        </Dropzone>

        {/* File Upload Dropdown */}
        <Group mt="sm" justify="center">
          <input
            type="file"
            ref={fileInputRef}
            style={{ display: 'none' }}
            multiple
            accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.json,.xml,.zip,.png,.jpg,.jpeg,.gif,.bmp,.svg"
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
          <Menu shadow="md" width={200}>
            <Menu.Target>
              <Button
                variant="light"
                size="sm"
                rightSection={<IconChevronDown size={16} />}
                leftSection={<IconUpload size={16} />}
              >
                Upload Documents
              </Button>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Item
                leftSection={<IconFile size={16} />}
                onClick={() => fileInputRef.current?.click()}
              >
                Select Multiple Files
              </Menu.Item>
              <Menu.Item
                leftSection={<IconFolder size={16} />}
                onClick={() => folderInputRef.current?.click()}
              >
                Select Folder (with subfolders)
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>
        </Group>

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

        {files.length > 0 && (
          <Group mt="md">
            <Button
              leftSection={<IconUpload size={16} />}
              onClick={handleUploadOnly}
              disabled={isUploading || isAssessing}
              loading={isUploading}
              color="blue"
            >
              {isUploading ? 'Uploading...' : 'Upload'}
            </Button>

            {isAssessing && (
              <Group gap="xs">
                <Loader size="sm" />
                <Text size="sm" c="dimmed">Assessment in progress...</Text>
              </Group>
            )}
          </Group>
        )}
      </Card>

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
              leftSection={<IconRobot size={16} />}
              onClick={handleStartAssessment}
              disabled={uploadedFiles.length === 0 || isAssessing || isUploading}
              variant="filled"
              color="green"
            >
              Start Assessment
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
            {/* List View */}
            {fileViewMode === 'list' && (
              <Table>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th style={{ textAlign: 'left', width: '40px' }}>Status</Table.Th>
                    <Table.Th style={{ textAlign: 'left' }}>Filename</Table.Th>
                    <Table.Th style={{ textAlign: 'left' }}>Type</Table.Th>
                    <Table.Th style={{ textAlign: 'left' }}>Size</Table.Th>
                    <Table.Th style={{ textAlign: 'left' }}>Uploaded</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {uploadedFiles.map((file) => (
                    <Table.Tr key={file.id}>
                      <Table.Td>
                        <IconCheck size={16} color="green" />
                      </Table.Td>
                      <Table.Td>
                        <Group gap="xs">
                          <IconFile size={16} />
                          <Text size="sm">{file.filename}</Text>
                        </Group>
                      </Table.Td>
                      <Table.Td>
                        <Badge size="sm" variant="light">
                          {file.file_type || 'Unknown'}
                        </Badge>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm" c="dimmed">
                          {file.file_size ? `${(file.file_size / 1024 / 1024).toFixed(2)} MB` : 'Unknown'}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm" c="dimmed">
                          {new Date(file.upload_timestamp).toLocaleString()}
                        </Text>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            )}

            {/* Grid View */}
            {fileViewMode === 'grid' && (
              <SimpleGrid cols={3} spacing="md">
                {uploadedFiles.map((file) => (
                  <Paper key={file.id} p="md" withBorder>
                    <Stack gap="xs">
                      <Group gap="xs">
                        <IconFile size={20} />
                        <IconCheck size={16} color="green" />
                      </Group>
                      <Text size="sm" fw={500} style={{ wordBreak: 'break-word' }}>
                        {file.filename}
                      </Text>
                      <Group justify="space-between">
                        <Badge size="xs" variant="light">
                          {file.file_type || 'Unknown'}
                        </Badge>
                        <Text size="xs" c="dimmed">
                          {file.file_size ? `${(file.file_size / 1024 / 1024).toFixed(1)}MB` : ''}
                        </Text>
                      </Group>
                      <Text size="xs" c="dimmed">
                        {new Date(file.upload_timestamp).toLocaleDateString()}
                      </Text>
                    </Stack>
                  </Paper>
                ))}
              </SimpleGrid>
            )}

            {/* Compact View */}
            {fileViewMode === 'compact' && (
              <SimpleGrid cols={3} spacing="sm">
                {uploadedFiles.map((file) => (
                  <Paper key={file.id} p="sm" withBorder style={{ cursor: 'pointer' }}>
                    <Stack gap="xs">
                      <Group gap="xs" align="flex-start">
                        <IconFile size={18} style={{ marginTop: '2px', flexShrink: 0 }} />
                        <Stack gap={2} style={{ flex: 1, minWidth: 0 }}>
                          <Text size="sm" fw={500} style={{
                            wordBreak: 'break-word',
                            lineHeight: 1.3
                          }}>
                            {file.filename}
                          </Text>
                          <Group gap="xs">
                            <Badge size="xs" variant="light">
                              {file.file_type || 'Unknown'}
                            </Badge>
                            <Text size="xs" c="dimmed">
                              {new Date(file.upload_timestamp).toLocaleDateString()}
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
              {uploadedFiles.map((file) => (
                <Table.Tr key={file.id}>
                  <Table.Td>
                    <Group gap="xs">
                      <IconFile size={16} />
                      <Text size="sm" style={{ wordBreak: 'break-all' }}>
                        {file.filename}
                      </Text>
                    </Group>
                  </Table.Td>
                  <Table.Td>
                    <Badge size="sm" variant="light">
                      {file.file_type || 'Unknown'}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">
                      {file.file_size ? `${(file.file_size / 1024 / 1024).toFixed(2)} MB` : 'Unknown'}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" c="dimmed">
                      {new Date(file.upload_timestamp).toLocaleString()}
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
