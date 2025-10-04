import React, { useState, useRef, useEffect, forwardRef, useImperativeHandle } from "react";
import { Button, Group, Stack, Text, Paper, Loader, Table, Badge, Card, Divider, Alert, Menu, Modal, ScrollArea, ActionIcon, Collapse, SimpleGrid, Tooltip, Switch, Progress } from "@mantine/core";
import { Dropzone } from "@mantine/dropzone";
import { IconFile, IconFolder, IconUpload, IconRefresh, IconAlertCircle, IconSettings, IconTestPipe, IconChevronDown, IconRobot, IconDatabase, IconCheck, IconList, IconGrid3x3, IconLayoutGrid, IconTrash, IconEye, IconEyeOff, IconDownload, IconPlayerPlay, IconPlus } from "@tabler/icons-react";
import { v4 as uuidv4 } from "uuid";
import { apiService, ProjectFile } from "../services/api";
import LiveConsole from "./LiveConsole";
import ReportDisplay from "./ReportDisplay";
import LLMConfigurationModal from './LLMConfigurationModal';
import FactsViewerModal from './FactsViewerModal';
import AssessmentViewerModal from './AssessmentViewerModal';
import RightLogPane from './RightLogPane';
import { useNotifications } from '../contexts/NotificationContext';
import { useAssessment } from '../contexts/AssessmentContext';
import { useLogContext } from '../contexts/LogContext';
import { useWebSocket, MessageType, AssessmentMessage, ProcessingMessage, AnyStandardizedMessage } from '../services/WebSocketManager';
import { useProgressQueue, ProgressUpdate } from '../utils/ProgressUpdateQueue';
import { useSessionCleanup } from '../hooks/useSessionCleanup';

export type FileUploadHandle = {
  startProcessing: () => void;
  toggleProgress: () => void;
  getShowProgress: () => boolean;
};

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

const FileUpload = forwardRef<FileUploadHandle, FileUploadProps>(({ projectId: propProjectId, onFilesUploaded }, ref) => {
  const [files, setFiles] = useState<File[]>([]);
  const [uploadedFiles, setUploadedFiles] = useState<ProjectFile[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
  const [projectId, setProjectId] = useState<string>(propProjectId || "");
  const [isUploading, setIsUploading] = useState(false);
  const [isAssessing, setIsAssessing] = useState(false);
  const [finalReport, setFinalReport] = useState<string>("");
  const [isReportStreaming, setIsReportStreaming] = useState<boolean>(false);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [assessmentStartTime, setAssessmentStartTime] = useState<Date | null>(null);
  const [uploadStartTime, setUploadStartTime] = useState<Date | null>(null);
  const [showDetailedFileList, setShowDetailedFileList] = useState(false);
  const [fileListExpanded, setFileListExpanded] = useState(false);
  const [fileViewMode, setFileViewMode] = useState<'list' | 'grid' | 'compact'>('list');
  const [testingLLM, setTestingLLM] = useState(false);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [llmConfigModalOpen, setLlmConfigModalOpen] = useState(false);
  const [factsModalOpen, setFactsModalOpen] = useState(false);
  const [selectedFileForFacts, setSelectedFileForFacts] = useState<ProjectFile | null>(null);
  const [assessmentModalOpen, setAssessmentModalOpen] = useState(false);
  const [selectedFileForAssessment, setSelectedFileForAssessment] = useState<ProjectFile | null>(null);
  const [currentProject, setCurrentProject] = useState<any>(null);
  const [rightLogPaneOpen, setRightLogPaneOpen] = useState(false);
  const [clearingData, setClearingData] = useState(false);
  const [showAssessmentProgress, setShowAssessmentProgress] = useState(false);
  const [showUploadProgress, setShowUploadProgress] = useState(false);
  const [migrationReportsExpanded, setMigrationReportsExpanded] = useState<boolean>(false);

  const { addNotification } = useNotifications();
  const { startAssessment, addLog, addEvent, setStatus, setProgress, assessmentState } = useAssessment();
  const { addLogMessage, startSession, endSession, getLogsByProject, subscribeToWebSocket } = useLogContext();
  const { cleanupSession } = useSessionCleanup();

  // Progress queue for WebSocket updates to prevent race conditions
  const handleWebSocketProgressUpdate = React.useCallback((update: ProgressUpdate) => {
    // Route different types of progress updates appropriately
    if (update.type === 'processing' || update.type === 'websocket') {
      setProgress(update.progress);
    }
  }, [setProgress]);

  const { enqueue: enqueueWebSocketProgress } = useProgressQueue(handleWebSocketProgressUpdate, {
    debounceMs: 50,
    maxQueueSize: 30,
    enableBatching: true,
  });

  // WebSocket subscription is now handled by LogContext
  const { sendMessage: sendAssessmentMessage, isConnected: isAssessmentConnected } = useWebSocket(
    projectId,
    MessageType.ASSESSMENT,
    (message: AnyStandardizedMessage) => {
      handleAssessmentMessage(message);
    },
    !!projectId && isAssessing
  );

  const { sendMessage: sendProcessingMessage, isConnected: isProcessingConnected } = useWebSocket(
    projectId,
    MessageType.PROCESSING,
    (message: AnyStandardizedMessage) => {
      handleProcessingMessage(message);
    },
    !!projectId && (isUploading || isAssessing)
  );

  // Subscribe to centralized log WebSocket when project is available
  useEffect(() => {
    if (projectId) {
      subscribeToWebSocket(projectId, true);
    }
    return () => {
      if (projectId) {
        subscribeToWebSocket(projectId, false);
      }
    };
  }, [projectId, subscribeToWebSocket]);

  // Message handlers for WebSocket messages
  const handleAssessmentMessage = (message: AnyStandardizedMessage) => {
    console.log('Assessment WebSocket message received:', message);

    // Parse message to determine if it's agentic interaction
    if ((message as any).type === 'agentic_log') {
      addLogMessage('agent_activity', (message as any).level === 'error' ? 'ERROR' : 'INFO', (message as any).message, (message as any).source || 'agent', {
        projectId,
        level: (message as any).level,
        source: (message as any).source
      });
      return;
    }

    if ((message as any).type === "PROCESSING_COMPLETED") {
      // Handle processing completion
      setIsAssessing(false);
      setStatus('completed');
      addLogMessage('processing', 'SUCCESS', 'Document processing completed successfully!', 'system', { projectId });

      // Validate knowledge graph data was created
      setTimeout(async () => {
        await validateKnowledgeGraphData(projectId);
      }, 2000); // Wait 2 seconds for data to be fully committed

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
    } else if ((message as any).type === "FINAL_REPORT_MARKDOWN_START") {
      setFinalReport("");
      setIsReportStreaming(true);
      addLogMessage('assessment', 'INFO', 'Starting report generation...', 'system', { projectId });
    } else if ((message as any).type === "FINAL_REPORT_MARKDOWN_END") {
      setIsReportStreaming(false);
      setIsAssessing(false);
      setStatus('completed');
      addLogMessage('assessment', 'SUCCESS', 'Assessment completed successfully!', 'system', { projectId });

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
    } else {
      // Add all messages to logs
      const rawMsg: any = message as any;
      const display = rawMsg.message || rawMsg.output || rawMsg.status || message.type;
      addLogMessage('assessment', 'INFO', display, 'websocket', { projectId });
    }
  };

  const handleProcessingMessage = (message: AnyStandardizedMessage) => {
    // DEBUG: Comprehensive logging of ALL incoming messages
    console.log('[WebSocket DEBUG] ==================== NEW MESSAGE ====================');
    console.log('[WebSocket DEBUG] Message received:', message);
    console.log('[WebSocket DEBUG] Message type:', (message as any).type);
    console.log('[WebSocket DEBUG] Message data:', (message as any).data);
    console.log('[WebSocket DEBUG] Full message object:', JSON.stringify(message, null, 2));
    console.log('[WebSocket DEBUG] =================================================');

    // Handle processing_started event with correlation ID
    const rawMessage = message as any; // Type assertion for new event types
    if (rawMessage.type === 'processing_started' && rawMessage.data) {
      const { correlation_id, file_count, message: startMessage } = rawMessage.data;
      
      // FIRST: Clear old assessment logs by starting new assessment
      startAssessment(projectId);
      
      setIsAssessing(true);
      setStatus('running');
      
      // Display message with correlation ID for tracking
      const displayMessage = startMessage || 
        `🚀 Assessment started for project ${projectId} [corr_id: ${correlation_id}]`;
      
      addLogMessage('processing', 'INFO', displayMessage, 'system', {
        projectId,
        correlationId: correlation_id,
        fileCount: file_count,
        startTime: new Date().toISOString()
      });

      // Also add to Assessment UI (startAssessment already added initial log)
      // addLog(displayMessage);  // Commented out - startAssessment already adds a log

      console.log('Processing started:', {
        correlationId: correlation_id,
        fileCount: file_count,
        projectId
      });

      return;
    }

    // Handle file_processing_started event
    if (rawMessage.type === 'file_processing_started' && rawMessage.data) {
      const { filename, file_number, total_files, message: statusMessage } = rawMessage.data;
      
      // DEBUG: Log event reception
      console.log('[WebSocket DEBUG] file_processing_started event received:', {
        filename,
        file_number,
        total_files,
        statusMessage,
        rawMessage
      });
      
      addLogMessage('processing', 'INFO', statusMessage, 'system', {
        projectId,
        filename,
        fileNumber: file_number,
        totalFiles: total_files
      });

      // Update Assessment UI with event details (Fix #3 - Extract statistics from WebSocket)
      const eventData = {
        message: `📄 Processing file ${file_number}/${total_files}: ${filename}`,
        type: 'info' as const,
        phase: 'parsing' as const,
        details: {
          filename,
          file_number,
          total_files,
          document_processed: false // Will be true when complete
        }
      };
      
      console.log('[WebSocket DEBUG] Calling addEvent with:', eventData);
      addEvent(eventData);

      return;
    }

    // Handle jsonl_conversion_complete event
    if (rawMessage.type === 'jsonl_conversion_complete' && rawMessage.data) {
      const { filename, file_number, total_files, element_count, message: statusMessage } = rawMessage.data;
      
      // DEBUG: Log event reception
      console.log('[WebSocket DEBUG] jsonl_conversion_complete event received:', {
        filename,
        file_number,
        total_files,
        element_count,
        statusMessage,
        rawMessage
      });
      
      addLogMessage('processing', 'SUCCESS', statusMessage, 'system', {
        projectId,
        filename,
        fileNumber: file_number,
        totalFiles: total_files,
        elementCount: element_count
      });

      // Update Assessment UI with statistics (Fix #3 - Extract element_count from WebSocket)
      const eventData = {
        message: `✅ JSONL conversion complete: ${element_count} elements extracted from ${filename}`,
        type: 'success' as const,
        phase: 'parsing' as const,
        details: {
          filename,
          file_number,
          total_files,
          elements_count: element_count, // This will increment totalElements in statistics
          document_processed: true
        }
      };
      
      console.log('[WebSocket DEBUG] Calling addEvent with:', eventData);
      addEvent(eventData);

      return;
    }

    // Handle entity_extraction_complete event
    if (rawMessage.type === 'entity_extraction_complete' && rawMessage.data) {
      const { filename, file_number, total_files, entity_count, message: statusMessage } = rawMessage.data;
      
      // DEBUG: Log event reception
      console.log('[WebSocket DEBUG] entity_extraction_complete event received:', {
        filename,
        file_number,
        total_files,
        entity_count,
        statusMessage,
        rawMessage
      });
      
      addLogMessage('processing', 'SUCCESS', statusMessage, 'system', {
        projectId,
        filename,
        fileNumber: file_number,
        totalFiles: total_files,
        entityCount: entity_count
      });

      // Update Assessment UI with entity statistics (Fix #3 - Extract entity_count from WebSocket)
      const eventData = {
        message: `✅ Entity extraction complete: ${entity_count} entities extracted from ${filename}`,
        type: 'success' as const,
        phase: 'entity' as const,
        details: {
          filename,
          file_number,
          total_files,
          entities_count: entity_count, // This will increment entitiesExtracted in statistics
          document_processed: true
        }
      };
      
      console.log('[WebSocket DEBUG] Calling addEvent with:', eventData);
      addEvent(eventData);

      return;
    }

    // Handle integration_status event
    if (rawMessage.type === 'integration_status' && rawMessage.data) {
      const { filename, file_number, total_files, vector_status, graph_status, message: statusMessage } = rawMessage.data;
      
      // DEBUG: Log event reception
      console.log('[WebSocket DEBUG] integration_status event received:', {
        filename,
        file_number,
        total_files,
        vector_status,
        graph_status,
        statusMessage,
        rawMessage
      });
      
      addLogMessage('processing', 'INFO', statusMessage, 'system', {
        projectId,
        filename,
        fileNumber: file_number,
        totalFiles: total_files,
        vectorStatus: vector_status,
        graphStatus: graph_status
      });

      // Update Assessment UI with integration status (Fix #13 - Extract statistics from graph_status)
      const statusIcon = (vector_status?.status === 'success' && graph_status?.status === 'success') ? '✅' : '🔄';
      
      // Extract statistics from integration results
      const vectorDocsProcessed = vector_status?.documents_processed || 0;
      const entitiesCount = graph_status?.entities_count || 0;
      const relationshipsCount = graph_status?.relationships_count || 0;
      
      addEvent({
        message: `${statusIcon} Integration: Vector=${vectorDocsProcessed} embeddings, Graph=${entitiesCount} entities/${relationshipsCount} relationships`,
        type: (vector_status?.status === 'success' && graph_status?.status === 'success') ? 'success' : 'info',
        phase: 'graph',
        details: {
          filename,
          file_number,
          total_files,
          vector_status,
          graph_status,
          embeddings_created: vectorDocsProcessed,
          entities_count: entitiesCount,
          relationships_count: relationshipsCount
        }
      });

      return;
    }

    // Handle ProgressTracker operation_progress messages
    if (message.type === 'operation_progress' && message.data) {
      const progressData = message.data;

      // Queue progress update to prevent race conditions
      enqueueWebSocketProgress({
        type: 'processing',
        progress: progressData.progress_percentage || 0,
        priority: 'normal',
        metadata: {
          operationName: progressData.operation_name,
          currentStep: progressData.current_step,
          totalSteps: progressData.total_steps,
          message: progressData.message
        }
      });

      setStatus('running');

      const progressMessage = `${progressData.operation_name} - Step ${progressData.current_step}/${progressData.total_steps} (${progressData.progress_percentage}%) - ${progressData.message}`;
      addLogMessage('processing', 'INFO', progressMessage, 'progress_tracker', {
        projectId,
        operationName: progressData.operation_name,
        currentStep: progressData.current_step,
        totalSteps: progressData.total_steps,
        progressPercentage: progressData.progress_percentage
      });

      console.log('Progress update queued:', {
        operation: progressData.operation_name,
        progress: progressData.progress_percentage,
        step: `${progressData.current_step}/${progressData.total_steps}`,
        message: progressData.message
      });

      return;
    }

    // Handle document_processing_progress messages from backend (detailed progress)
    if (rawMessage.type === 'document_processing_progress' && rawMessage.data) {
      const { filename, stage, progress, message, details } = rawMessage.data;

      // Map backend stages to user-friendly display messages with emojis
      const stageMessages: Record<string, string> = {
        'jsonl_created': `📄 JSONL created: ${message || 'Structured data extracted'}`,
        'vector_embeddings_created': `🔗 Vector embeddings created: ${message || 'Embeddings generated'}`,
        'graph_extraction_completed': `🕸️ Entity extraction completed: ${message || 'Entities and relationships extracted'}`,
        'integration_completed': `🔄 Service integrations completed`,
        'updating_stats': `📊 Updating project statistics`,
        'finalizing': `🏁 Finalizing processing`,
        'document_processing_start': `🚀 Document processing started: ${message || 'Initializing'}`,
        'document_processing_complete': `✅ Document processing completed: ${message || 'All steps finished'}`
      };

      const displayMessage = stageMessages[stage as string] || message || `Processing: ${stage}`;

      // Update progress bar if progress value is provided
      if (typeof progress === 'number' && progress >= 0 && progress <= 100) {
        setProgress(progress);
      }

      // Add detailed log message
      addLogMessage('processing', 'INFO', displayMessage, 'system', {
        projectId,
        filename,
        stage,
        progress,
        details
      });

      console.log('[WebSocket DEBUG] Processed document_processing_progress:', {
        stage,
        progress,
        displayMessage,
        filename
      });

      return;
    }

    // Handle plain text messages (backward compatibility)
  const rawProcessing: any = message as any;
  const msg = rawProcessing.message || message.type;

    if (msg === "PROCESSING_COMPLETED") {
      setIsUploading(false);
      setStatus('completed');

      // Queue final progress update
      enqueueWebSocketProgress({
        type: 'processing',
        progress: 100,
        priority: 'high', // High priority for completion
        metadata: { completion: true }
      });

      // Auto-refresh stats after processing completion
      if (onFilesUploaded) {
        setTimeout(() => {
          onFilesUploaded();
          addLogMessage('system', 'INFO', 'Project statistics refreshed', 'system', { projectId });
        }, 1000);
      }
    } else if (msg.includes('PROGRESS:')) {
      const progressMatch = msg.match(/PROGRESS:\s*(\d+)/);
      if (progressMatch) {
        const progress = parseInt(progressMatch[1], 10);

        // Queue progress update for backward compatibility messages
        enqueueWebSocketProgress({
          type: 'websocket',
          progress: progress,
          priority: 'normal',
          metadata: { source: 'legacy_progress_message' }
        });
      }
    } else {
      // Enhanced fallback to handle document_processing_progress in raw messages
      if (rawProcessing.type === 'document_processing_progress' && rawProcessing.data) {
        const data = rawProcessing.data;
        const stageMessages: Record<string, string> = {
          'jsonl_created': `📄 JSONL created: ${data.message || 'Structured data extracted'}`,
          'vector_embeddings_created': `🔗 Vectors: ${data.message || 'Embeddings created'}`,
          'graph_extraction_completed': `🕸️ Graph: ${data.message || 'Entities extracted'}`,
          'integration_completed': `✅ Integration: ${data.message || 'Services updated'}`
        };
        const fallbackMessage = (data.stage && stageMessages[data.stage as string]) || data.message || data.details || msg;
        addLogMessage('processing', 'INFO', fallbackMessage, 'websocket', { projectId });
      } else {
        // Add to logs
        addLogMessage('processing', 'INFO', msg, 'websocket', { projectId });
      }
    }
  };

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
      addNotification({
        title: 'Duplicate Files Detected',
        message: `The following files already exist: ${duplicateFiles.map(f => f.name).join(', ')}`,
        type: 'warning',
        projectId: projectId,
        metadata: { duplicateFiles: duplicateFiles.map(f => f.name) }
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
    setFinalReport("");
    setIsReportStreaming(false);
  };

  const handleFolderUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = event.target.files;
    if (fileList) {
      const filesArray = Array.from(fileList);
      handleDrop(filesArray);

      addNotification({
        title: 'Folder Uploaded',
        message: `Selected ${filesArray.length} files from folder structure`,
        type: 'info',
        projectId: projectId,
        metadata: { fileCount: filesArray.length, source: 'folder_upload' }
      });
    }
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = event.target.files;
    if (fileList) {
      const filesArray = Array.from(fileList);
      handleDrop(filesArray, true); // Pass true to indicate additive selection

      addNotification({
        title: 'Files Selected',
        message: `Selected ${filesArray.length} files`,
        type: 'info',
        projectId: projectId,
        metadata: { fileCount: filesArray.length, source: 'file_select' }
      });
    }
  };

  const handleNativeToolDrop = async (acceptedFiles: File[], toolType: 'aws_migration_evaluator' | 'azure_migrate') => {
    if (acceptedFiles.length === 0) return;
    
    const file = acceptedFiles[0]; // Only one file allowed for native tools
    
    // Validate file type based on tool
    if (toolType === 'aws_migration_evaluator' && !file.name.toLowerCase().endsWith('.csv')) {
      addNotification({
        title: 'Invalid File Type',
        message: 'AWS Migration Evaluator reports must be CSV files',
        type: 'error',
        projectId: projectId,
        metadata: { toolType, fileName: file.name, errorType: 'invalid_file_type' }
      });
      return;
    }
    
    if (toolType === 'azure_migrate' && !(/\.(csv|xls|xlsx)$/i.test(file.name))) {
      addNotification({
        title: 'Invalid File Type', 
        message: 'Azure Migrate reports must be CSV, XLS, or XLSX files',
        type: 'error',
        projectId: projectId,
        metadata: { toolType, fileName: file.name, errorType: 'invalid_file_type' }
      });
      return;
    }
    
    if (!projectId) {
      setProjectId(uuidv4());
    }
    
    try {
      setIsUploading(true);
      addLogMessage('upload', 'INFO', `🚀 Uploading ${toolType === 'aws_migration_evaluator' ? 'AWS Migration Evaluator' : 'Azure Migrate'} report...`, 'upload', { projectId });

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
        addLogMessage('upload', 'SUCCESS', `✅ ${toolType === 'aws_migration_evaluator' ? 'AWS Migration Evaluator' : 'Azure Migrate'} report uploaded successfully`, 'upload', { projectId });
        addLogMessage('upload', 'INFO', `📊 Processed ${result.records_count || 'unknown'} records`, 'upload', { projectId });
        
        addNotification({
          title: 'Report Uploaded Successfully',
          message: `${toolType === 'aws_migration_evaluator' ? 'AWS Migration Evaluator' : 'Azure Migrate'} report has been processed`,
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
      addLogMessage('upload', 'ERROR', `❌ Failed to upload ${toolType} report: ${errorMessage}`, 'upload', { projectId, error: errorMessage });
      
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
      addNotification({
        title: 'No Files Selected',
        message: 'Please select files to upload',
        type: 'warning',
        projectId: projectId,
        metadata: { errorType: 'no_files_selected' }
      });
      return;
    }

    setIsUploading(true);
    setUploadStartTime(new Date());
    const initialLog = `Starting upload of ${files.length} file(s)...`;
    addLogMessage('upload', 'INFO', initialLog, 'upload', { projectId, fileCount: files.length });

    try {
      // Upload files using the new API service with detailed progress tracking
      const uploadingLog = '📤 Uploading files to object storage...';
      addLogMessage('upload', 'INFO', uploadingLog, 'upload', { projectId });

      const response = await apiService.uploadFiles(projectId, files);
      console.log('Upload response:', response);

      if (response.uploaded_files) {
        // Process each uploaded file
        for (const uploadedFile of response.uploaded_files) {
          if (uploadedFile.status === 'uploaded') {
            const successLog = `Uploaded: ${uploadedFile.filename} (${uploadedFile.size} bytes)`;
            addLogMessage('upload', 'SUCCESS', successLog, 'upload', { projectId, filename: uploadedFile.filename, size: uploadedFile.size });
          } else {
            const errorLog = `Failed: ${uploadedFile.filename} - ${uploadedFile.error}`;
            addLogMessage('upload', 'ERROR', errorLog, 'upload', { projectId, filename: uploadedFile.filename, error: uploadedFile.error });
          }
        }
      }

      const completedLog = 'Files uploaded and registered successfully';
      addLogMessage('upload', 'SUCCESS', completedLog, 'upload', { projectId });

      // Count successful uploads (backend now handles registration automatically)
      const registeredCount = response.uploaded_files?.filter(f => f.status === 'uploaded').length || 0;

      // Clear selected files
      setFiles([]);

      // Refresh the uploaded files list
      addLogMessage('system', 'INFO', 'Refreshing file list...', 'system', { projectId });
      await fetchUploadedFiles();

      // Trigger project stats refresh
      if (onFilesUploaded) {
        onFilesUploaded();
      }

      // Show success notification
      const fileNames = files.map(f => f.name).join(', ');
      addLogMessage('upload', 'SUCCESS', `Upload completed! ${registeredCount}/${files.length} files processed successfully`, 'upload', {
        projectId,
        registeredCount,
        totalCount: files.length,
        fileNames
      });

      addNotification({
        title: 'Upload Successful',
        message: `Successfully uploaded ${registeredCount}/${files.length} file(s)`,
        type: registeredCount === files.length ? 'success' : 'warning',
        projectId: projectId,
        metadata: { fileCount: files.length, fileNames, registeredCount }
      });

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
      addLogMessage('upload', 'ERROR', `Upload failed: ${errorMessage}`, 'upload', { projectId, error: String(err) });

      console.error('Upload error:', err);

      addNotification({
        title: 'Upload Failed',
        message: errorMessage,
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
      addLogMessage('system', 'INFO', `Validating knowledge graph data for project ${projectId}...`, 'validation', { projectId });
      const response = await fetch(`http://localhost:8000/api/projects/${projectId}/graph`);

      if (response.ok) {
        const graphData = await response.json();
        console.log('Knowledge graph validation response:', graphData);

        const hasNodes = graphData.nodes && graphData.nodes.length > 0;
        const hasEdges = graphData.edges && graphData.edges.length > 0;

        if (hasNodes || hasEdges) {
          addLogMessage('system', 'SUCCESS', `Knowledge graph data validated: ${graphData.nodes?.length || 0} entities, ${graphData.edges?.length || 0} relationships`, 'validation', {
            projectId,
            nodeCount: graphData.nodes?.length || 0,
            edgeCount: graphData.edges?.length || 0
          });

          // Also log some sample data for debugging
          if (graphData.nodes?.length > 0) {
            const sampleNodes = graphData.nodes.slice(0, 3).map((n: any) => n.label || n.name || n.id).join(', ');
            addLogMessage('system', 'DEBUG', `Sample entities: ${sampleNodes}`, 'validation', { projectId });
          }

          return true;
        } else {
          addLogMessage('system', 'WARNING', `No knowledge graph data found after processing. Response structure: ${JSON.stringify(Object.keys(graphData))}`, 'validation', { projectId });
          addLogMessage('system', 'DEBUG', `Full response: ${JSON.stringify(graphData).substring(0, 200)}...`, 'validation', { projectId });
          return false;
        }
      } else {
        const errorText = await response.text();
        addLogMessage('system', 'WARNING', `Could not validate knowledge graph data: ${response.status} - ${errorText}`, 'validation', { projectId, status: response.status });
        return false;
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      addLogMessage('system', 'ERROR', `Knowledge graph validation failed: ${errorMessage}`, 'validation', { projectId, error: errorMessage });
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

        addNotification({
          title: 'Data Cleared Successfully',
          message: `Cleared ${weaviate_embeddings} embeddings, ${neo4j_nodes} graph nodes, and ${neo4j_relationships} relationships.`,
          type: 'success',
          projectId: projectId,
          metadata: { weaviate_embeddings, neo4j_nodes, neo4j_relationships }
        });
        addLogMessage('system', 'SUCCESS', `Project data cleared: ${weaviate_embeddings} embeddings, ${neo4j_nodes} nodes, ${neo4j_relationships} relationships`, 'system', { projectId });

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
      addNotification({
        title: 'Error',
        message: `Failed to clear project data: ${errorMessage}`,
        type: 'error',
        projectId: projectId,
        metadata: { errorType: 'clear_data_failed', error: errorMessage }
      });
      addLogMessage('system', 'ERROR', `Failed to clear project data: ${errorMessage}`, 'system', { projectId, error: errorMessage });
    } finally {
      setClearingData(false);
    }
  };

  const handleUploadAndAssess = async () => {
    if (files.length === 0 || !projectId) {
      // If no files selected, prompt user to select files
      addNotification({
        title: 'No Files Selected',
        message: 'Please select files to upload before starting assessment',
        type: 'warning',
        projectId: projectId,
        metadata: { errorType: 'no_files_selected' }
      });
      return;
    }

    // Clean up previous session data before starting new upload and assessment
    cleanupSession(projectId);

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

      // WebSocket connection is now handled by the centralized manager
      // Messages will be received through the subscription callbacks

    } catch (err) {
      setIsUploading(false);
      setIsAssessing(false);
      addNotification({
        title: 'Upload or Assessment Failed',
        message: `Error: ${err instanceof Error ? err.message : 'Unknown error occurred'}`,
        type: 'error',
        projectId: projectId,
        metadata: { errorType: 'upload_assessment_failed', error: String(err) }
      });

      addLogMessage('upload', 'ERROR', 'Error uploading files or starting assessment', 'upload', { projectId });
    }
  };

  const handleStartAssessment = async () => {
    if (!projectId || uploadedFiles.length === 0) {
      addNotification({
        title: 'No Files Available',
        message: 'Please upload files before starting assessment',
        type: 'warning',
        projectId: projectId,
        metadata: { errorType: 'no_files_available' }
      });
      return;
    }

    // Check if project has default LLM configuration
    if (!currentProject?.llm_provider) {
      addNotification({
        title: 'LLM Configuration Required',
        message: 'Please configure a default LLM for this project in the Overview tab',
        type: 'warning',
        projectId: projectId,
        metadata: { errorType: 'llm_config_required' }
      });
      return;
    }

    // Clean up previous session data before starting new assessment
    cleanupSession(projectId);

    setIsAssessing(true);
    setAssessmentStartTime(new Date());
    addLogMessage('assessment', 'INFO', `Starting assessment with ${currentProject.llm_provider}/${currentProject.llm_model}...`, 'assessment', { projectId });
    setFinalReport("");
    setIsReportStreaming(false);

    // Start assessment in global context
    startAssessment(projectId);

    try {
      // WebSocket connection is now handled by the centralized manager
      // Messages will be received through the subscription callbacks
    } catch (error) {
      setIsAssessing(false);
      setStatus('failed');
      const errorMessage = error instanceof Error ? error.message : String(error);
      addLog(`❌ Assessment failed: ${errorMessage}`);

      addNotification({
        title: 'Assessment Failed',
        message: `Failed to start assessment: ${errorMessage}`,
        type: 'error',
        projectId: projectId,
        metadata: { errorType: 'assessment_failed', error: errorMessage }
      });
    }
  };

  const handleReassessment = () => {
    if (!projectId || uploadedFiles.length === 0) {
      addNotification({
        title: 'No Files Available',
        message: 'Please upload files before starting reassessment',
        type: 'warning',
        projectId: projectId,
        metadata: { errorType: 'no_files_available' }
      });
      return;
    }

    // Open LLM configuration modal
    setLlmConfigModalOpen(true);
  };

  const handleTestLLM = async () => {
    if (!projectId) {
      addNotification({
        title: 'No Project Selected',
        message: 'Please select a project first',
        type: 'warning',
        projectId: projectId,
        metadata: { errorType: 'no_project_selected' }
      });
      return;
    }

    if (!currentProject?.llm_provider) {
      addNotification({
        title: 'LLM Configuration Required',
        message: 'Please configure a default LLM for this project in the Overview tab',
        type: 'warning',
        projectId: projectId,
        metadata: { errorType: 'llm_config_required' }
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
        addNotification({
          title: 'LLM Test Successful',
          message: `${currentProject.llm_provider}/${currentProject.llm_model} is working correctly`,
          type: 'success',
          projectId: projectId,
          metadata: { llmProvider: currentProject.llm_provider, llmModel: currentProject.llm_model }
        });
      } else {
        addNotification({
          title: 'LLM Test Failed',
          message: result.message || 'Failed to connect to LLM',
          type: 'error',
          projectId: projectId,
          metadata: { errorType: 'llm_test_failed', error: result.message }
        });
      }
    } catch (error) {
      addNotification({
        title: 'LLM Test Error',
        message: 'Failed to test LLM configuration',
        type: 'error',
        projectId: projectId,
        metadata: { errorType: 'llm_test_error', error: String(error) }
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
      addNotification({
        title: 'Configuration Error',
        message: 'Failed to save LLM configuration',
        type: 'error',
        projectId: projectId,
        metadata: { errorType: 'config_save_failed', error: String(error) }
      });
      return;
    }

    // Clean up previous session data before starting new assessment
    cleanupSession(projectId);

    setIsAssessing(true);
    setAssessmentStartTime(new Date());
    addLogMessage('assessment', 'INFO', 'Starting assessment with project-specific LLM configuration...', 'assessment', { projectId });
    setFinalReport("");
    setIsReportStreaming(false);

    try {
      // WebSocket connection is now handled by the centralized manager
      // Messages will be received through the subscription callbacks
    } catch (err) {
      setIsAssessing(false);
      addLogMessage('assessment', 'ERROR', 'Error starting reassessment', 'assessment', { projectId });

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
      addNotification({
        title: 'No Files Available',
        message: 'Please upload files before starting processing',
        type: 'warning',
        projectId: projectId,
        metadata: { errorType: 'no_files_available' }
      });
      return;
    }

    // Check if project has default LLM configuration
    if (!currentProject?.llm_provider) {
      addNotification({
        title: 'LLM Configuration Required',
        message: 'Please configure a default LLM for this project in the Overview tab',
        type: 'warning',
        projectId: projectId,
        metadata: { errorType: 'llm_config_required' }
      });
      return;
    }

    // Clean up previous session data before starting new processing
    cleanupSession(projectId);

    setIsUploading(true);
    setShowAssessmentProgress(true); // Auto-show assessment progress
    addLogMessage('processing', 'INFO', "Starting document processing with project's default LLM configuration...", 'processing', { projectId });
    addLogMessage('processing', 'INFO', `Using LLM: ${currentProject.llm_provider}/${currentProject.llm_model}`, 'processing', { projectId });

    console.log('Starting document processing for project:', projectId);
    console.log('Using LLM configuration:', currentProject.llm_provider, '/', currentProject.llm_model);

    // WebSocket connection is now handled by the centralized manager
    // Messages will be received through the subscription callbacks

    try {
      // Call the processing endpoint to start the process
      console.log('⚠️ Process All is deprecated. Use Process Selected instead.');
      addLogMessage('system', 'WARNING', '"Process All" functionality has been removed. Please use "Process Selected" instead.', 'system', { projectId });
      // console.log('Calling processing endpoint:', `http://localhost:8000/api/projects/${projectId}/process-all`);
      // const response = await fetch(`http://localhost:8000/api/projects/${projectId}/process-all` , {
      //   method: 'POST',
      //   headers: {
      //     'Content-Type': 'application/json',
      //   },
      //   body: JSON.stringify({
      //     use_project_llm: true, // Use project's default LLM
      //     files: uploadedFiles.map(f => ({ filename: f.filename, file_type: f.file_type }))
      //   })
      // });

      // console.log('Processing response status:', response.status);
      // if (response.ok) {
      //   const result = await response.json();
      //   setLogs(prev => [...prev, "✅ Processing request submitted successfully"]);

      //   notifications.show({
      //     title: 'Processing Started',
      //     message: `Document processing started using ${currentProject.llm_provider}/${currentProject.llm_model}`,
      //     color: 'green',
      //   });
      // } else {
      //   const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
      //   const correlationId = response.headers.get('X-Correlation-ID') || 'unknown';
      //   console.error('Processing failed with status:', response.status, 'CID:', correlationId, 'Error:', errorData);
      //   notifications.show({
      //     title: 'Processing Failed',
      //     message: `${errorData.detail || 'Failed to start processing'} — Correlation ID: ${correlationId} (click to copy)`,
      //     color: 'red',
      //     onClick: () => {
      //       if (correlationId && correlationId !== 'unknown') navigator.clipboard.writeText(correlationId);
      //     }
      //   });
      //   throw new Error(errorData.detail || `HTTP ${response.status}: Failed to start processing`);
      // }
  } catch (error) {
      console.error('Processing error:', error);
      const errorMessage = error instanceof Error ? error.message : String(error);
      addNotification({
        title: 'Processing Failed',
        message: `Failed to start document processing: ${errorMessage}`,
        type: 'error',
        projectId: projectId,
        metadata: { errorType: 'processing_failed', error: errorMessage }
      });
      addLogMessage('processing', 'ERROR', `Failed to start document processing: ${errorMessage}`, 'processing', { projectId, error: errorMessage });
    } finally {
      setIsUploading(false);
    }
  };

  const handleLLMConfigSelected = async (configId: string) => {
    setIsUploading(true);
    addLogMessage('system', 'WARNING', 'Process All is deprecated. Use Process Selected instead.', 'system', { projectId });

    try {
      // Call the new processing endpoint with LLM config
      addLogMessage('system', 'WARNING', '"Process All" functionality has been removed. Please use "Process Selected" instead.', 'system', { projectId });
      // const response = await fetch(`http://localhost:8000/api/projects/${projectId}/process-all`, {
      //   method: 'POST',
      //   headers: {
      //     'Content-Type': 'application/json',
      //   },
      //   body: JSON.stringify({
      //     llm_config_id: configId
      //   })
      // });

      // if (response.ok) {
        addNotification({
          title: 'Processing Started',
          message: 'Document processing has begun with selected LLM configuration.',
          type: 'success',
          projectId: projectId,
          metadata: { startTime: new Date().toISOString(), configId: configId }
        });

        addNotification({
          title: 'Document Processing Started',
          message: `Creating project knowledge base using LLM configuration: ${configId}`,
          type: 'info',
          projectId: projectId,
          metadata: { startTime: new Date().toISOString(), configId: configId }
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
              configId: configId,
              project_id: projectId,
              action: 'document_processing'
            }
          });
        } catch (error) {
          console.error('Failed to create backend notification:', error);
        }

        addLogMessage('processing', 'SUCCESS', 'Document processing initiated', 'processing', { projectId });
        addLogMessage('processing', 'INFO', 'Creating knowledge base...', 'processing', { projectId });
        addLogMessage('processing', 'INFO', 'Extracting entities and relationships...', 'processing', { projectId });
        addLogMessage('processing', 'INFO', 'Using selected LLM configuration for enhanced processing...', 'processing', { projectId });
        // } else {
        //   throw new Error('Failed to start processing');
        // }
    } catch (error) {
      // Process All deprecated - show deprecation message
      addLogMessage('system', 'ERROR', 'Process All has been deprecated. Use Process Selected instead.', 'system', { projectId });
    } finally {
      setIsUploading(false);
    }
  };

  const stopAssessment = () => {
    // Close WebSocket connections through the centralized manager
    if (projectId) {
      // Note: The WebSocket manager will handle cleanup automatically when subscriptions are removed
      // But we can explicitly disconnect if needed
    }
    setIsAssessing(false);
    setIsReportStreaming(false);

    addNotification({
      title: 'Assessment Stopped',
      message: 'Assessment was manually stopped',
      type: 'warning',
      projectId: projectId,
      metadata: { stoppedAt: new Date().toISOString() }
    });

    addLogMessage('assessment', 'INFO', 'Assessment stopped by user', 'assessment', { projectId });
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

      addNotification({
        title: 'Download Started',
        message: `Downloading ${file.filename}`,
        type: 'info',
        projectId: projectId,
        metadata: { fileName: file.filename, action: 'download_started' }
      });
    } catch (error) {
      addNotification({
        title: 'Download Failed',
        message: `Failed to download ${file.filename}`,
        type: 'error',
        projectId: projectId,
        metadata: { fileName: file.filename, errorType: 'download_failed', error: String(error) }
      });
    }
  };

  const handleViewAssessment = (file: ProjectFile) => {
    setSelectedFileForAssessment(file);
    setAssessmentModalOpen(true);
  };

  const handleCloseAssessmentModal = () => {
    setAssessmentModalOpen(false);
    setSelectedFileForAssessment(null);
  };

  const handleViewFacts = (file: ProjectFile) => {
    setSelectedFileForFacts(file);
    setFactsModalOpen(true);
  };

  const handleCloseFactsModal = () => {
    setFactsModalOpen(false);
    setSelectedFileForFacts(null);
  };

  const handleDeleteFile = async (fileId: string) => {
    try {
      const response = await apiService.deleteProjectFile(projectId, fileId);
      await fetchUploadedFiles();
      setSelectedFiles(prev => prev.filter(id => id !== fileId));

      // Show detailed success message
      let successMessage = 'File deleted successfully';
      if (response && typeof response === 'object') {
        const deletedFiles = response.deleted_files?.length || 0;
        const embeddings = response.embeddings_deleted || 0;
        const nodes = response.graph_nodes_deleted || 0;
        if (deletedFiles > 0 || embeddings > 0 || nodes > 0) {
          successMessage = `File deleted successfully: ${deletedFiles} files, ${embeddings} embeddings, ${nodes} graph nodes removed`;
        }
      }

      addNotification({
        title: 'File Deleted',
        message: successMessage,
        type: 'success',
        projectId: projectId,
        metadata: { fileId, deletedFiles: response?.deleted_files?.length || 0, embeddingsDeleted: response?.embeddings_deleted || 0, graphNodesDeleted: response?.graph_nodes_deleted || 0 }
      });
    } catch (error) {
      addNotification({
        title: 'Delete Failed',
        message: 'Failed to delete file',
        type: 'error',
        projectId: projectId,
        metadata: { fileId, errorType: 'delete_failed', error: String(error) }
      });
    }
  };

  const handleBulkDelete = async () => {
    try {
      // For bulk deletion, we could use the new bulk endpoint, but for now we'll use individual deletes
      // with better error handling
      const deletionResults = {
        successful: 0,
        failed: 0,
        errors: [] as string[]
      };

      for (const fileId of selectedFiles) {
        try {
          await apiService.deleteProjectFile(projectId, fileId);
          deletionResults.successful++;
        } catch (error) {
          deletionResults.failed++;
          const errorMessage = error instanceof Error ? error.message : String(error);
          deletionResults.errors.push(`Failed to delete file: ${errorMessage}`);
        }
      }

      await fetchUploadedFiles();
      setSelectedFiles([]);

      if (deletionResults.failed === 0) {
        addNotification({
          title: 'Files Deleted',
          message: `${selectedFiles.length} file(s) deleted successfully`,
          type: 'success',
          projectId: projectId,
          metadata: { fileCount: selectedFiles.length, successful: deletionResults.successful }
        });
      } else {
        addNotification({
          title: 'Delete Partially Failed',
          message: `${deletionResults.successful} deleted, ${deletionResults.failed} failed. Check logs for details.`,
          type: 'warning',
          projectId: projectId,
          metadata: { successful: deletionResults.successful, failed: deletionResults.failed, errors: deletionResults.errors }
        });
      }
    } catch (error) {
      addNotification({
        title: 'Delete Failed',
        message: 'Failed to delete selected files',
        type: 'error',
        projectId: projectId,
        metadata: { errorType: 'bulk_delete_failed', error: String(error) }
      });
    }
  };

  const handleBulkDownload = async () => {
    // This is a placeholder function for bulk download functionality
    // Implementation would depend on backend support for bulk download
    addNotification({
      title: 'Bulk Download',
      message: 'Bulk download functionality not yet implemented',
      type: 'info',
      projectId: projectId,
      metadata: { action: 'bulk_download_not_implemented' }
    });
  };

  const handleProcessSelected = async () => {
    if (selectedFiles.length === 0) {
      addNotification({
        title: 'No Files Selected',
        message: 'Please select files to process',
        type: 'warning',
        projectId: projectId,
        metadata: { errorType: 'no_files_selected' }
      });
      return;
    }

    try {
      // Clean up previous session data before starting new processing
      cleanupSession(projectId);

      setIsAssessing(true);
      setShowAssessmentProgress(true);

      // Get selected file objects
      const selectedFileObjects = uploadedFiles.filter(f => selectedFiles.includes(f.id || f.filename));

      addLogMessage('processing', 'INFO', `Starting processing of ${selectedFiles.length} selected files...`, 'processing', { projectId, fileCount: selectedFiles.length });
      addLogMessage('processing', 'INFO', `Selected files: ${selectedFileObjects.map(f => f.filename).join(', ')}`, 'processing', { projectId });

      // WebSocket connection is now handled by the centralized manager
      // Messages will be received through the subscription callbacks

      // Call the processing endpoint with selected files (explicit selected route)
      const result = await apiService.processSelectedDocuments(
        projectId,
        selectedFileObjects.map(f => f.filename)
      );

      if (result) {
        addLogMessage('processing', 'SUCCESS', 'Selected document processing initiated', 'processing', { projectId });
        addLogMessage('processing', 'INFO', 'Creating knowledge base from selected files...', 'processing', { projectId });
        addLogMessage('processing', 'INFO', 'Extracting entities and relationships...', 'processing', { projectId });

        addNotification({
          title: 'Processing Started',
          message: `Processing ${selectedFiles.length} selected files`,
          type: 'success',
          projectId: projectId,
          metadata: { startTime: new Date().toISOString(), selectedFiles: selectedFiles.length }
        });
      } else {
        addNotification({
          title: 'Processing Error',
          message: 'Failed to start processing selected files',
          type: 'error',
          projectId: projectId,
          metadata: { errorType: 'processing_start_failed', selectedFiles: selectedFiles.length }
        });
        throw new Error('Failed to start processing selected files');
      }
    } catch (error) {
      addNotification({
        title: 'Processing Error',
        message: 'Failed to start processing selected files',
        type: 'error',
        projectId: projectId,
        metadata: { errorType: 'processing_failed', error: String(error) }
      });
      setIsAssessing(false);
      setShowAssessmentProgress(false);
    }
  };

  // Expose imperative API to parent (ProjectDetailView)
  useImperativeHandle(ref, () => ({
    startProcessing: () => {
      // Kick off processing and ensure progress panel can be shown if desired
      handleStartProcessing();
    },
    toggleProgress: () => {
      setShowAssessmentProgress((prev) => !prev);
    },
    getShowProgress: () => showAssessmentProgress,
  }), [showAssessmentProgress, handleStartProcessing]);

  return (
    <Stack gap="lg">
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
          
          {/* Upload Button - Next to Select Files */}
          {files.length > 0 && (
            <Button
              size="sm"
              onClick={handleUploadOnly}
              disabled={isUploading || isAssessing}
              loading={isUploading}
              leftSection={<IconUpload size={14} />}
            >
              Upload ({files.length})
            </Button>
          )}
          
          {/* Spacer to push progress button to the right */}
          <div style={{ flex: 1 }} />
          
          {/* Show Upload Progress Button - Right aligned (upload only) */}
          {files.length > 0 && (
            <Button
              size="sm"
              variant="subtle"
              color="gray"
              leftSection={showUploadProgress ? <IconEyeOff size={14} /> : <IconEye size={14} />}
              onClick={() => setShowUploadProgress(!showUploadProgress)}
            >
              {showUploadProgress ? 'Hide' : 'Show'} Upload Progress
            </Button>
          )}
          
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
              'application/xml': ['.xml'],
              'text/xml': ['.xml'],
              'text/markdown': ['.md', '.markdown'],
              'application/zip': ['.zip'],
              'image/png': ['.png'],
              'image/jpeg': ['.jpg', '.jpeg'],
              'image/gif': ['.gif'],
              'image/tiff': ['.tif', '.tiff'],
            }}
            style={{ flex: 2 }}
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
          accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.json,.xml,.md,.markdown,.png,.jpg,.jpeg,.gif,.tif,.tiff,.zip"
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

        {/* Upload controls - Remove the old section since buttons are now inline */}
        {files.length > 0 && (
          <Group gap="xs" mt="sm">
            <Text size="xs" c="dimmed">{files.length} files selected</Text>
          </Group>
        )}

        {/* Selected Files Preview - Elongated */}
        {files.length > 0 && (
          <Card shadow="sm" p="xs" radius="md" withBorder mt="sm">
            <Group justify="space-between" mb={4}>
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
            <ScrollArea h={files.length > 5 ? 300 : files.length * 45 + 20}>
              <Stack gap={4}>
                {files.map((file, index) => (
                  <Group key={index} justify="space-between" p={6} style={{ backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
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
      {showUploadProgress && (isUploading) && (
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
          <LiveConsole logs={["Upload in progress..."]} />
        </Card>
      )}

  {/* Assessment Actions card removed; controls moved to top header via parent */}

  {/* Assessment Progress - Conditionally shown just above Uploaded Files */}
      {showAssessmentProgress && (assessmentState.events.length > 0 || isAssessing) && (
        <Card shadow="sm" p="md" radius="md" withBorder>
          <Group justify="space-between" mb="md">
            <Group gap="sm">
              <Text size="lg" fw={600}>
                Assessment Progress
              </Text>
              {assessmentState.progress > 0 && (
                <Badge variant="light" color={assessmentState.status === 'completed' ? 'green' : 'blue'}>
                  {assessmentState.progress}%
                </Badge>
              )}
            </Group>
            {assessmentStartTime && (
              <Text size="sm" c="dimmed">
                Started: {assessmentStartTime!.toLocaleString()}
              </Text>
            )}
          </Group>
          
          {/* Progress Bar */}
          {assessmentState.progress > 0 && (
            <Progress 
              value={assessmentState.progress} 
              color={assessmentState.status === 'failed' ? 'red' : assessmentState.status === 'completed' ? 'green' : 'blue'}
              mb="md"
              size="lg"
            />
          )}
          
          {/* Status Badge */}
          <Group justify="space-between" mb="sm">
            <Badge 
              color={
                assessmentState.status === 'completed' ? 'green' : 
                assessmentState.status === 'failed' ? 'red' : 
                assessmentState.status === 'running' ? 'blue' : 'gray'
              }
              variant="filled"
            >
              {assessmentState.status.charAt(0).toUpperCase() + assessmentState.status.slice(1)}
            </Badge>
            {assessmentState.isRunning && <Loader size="sm" />}
          </Group>
          
          <LiveConsole logs={assessmentState.events.length > 0 ? assessmentState.events.map(event => event.message) : ["Initializing assessment..."]} />
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

            {/* Clear Embeddings button moved into header */}
            <Button
              size="xs"
              variant="light"
              color="red"
              leftSection={<IconTrash size={14} />}
              onClick={handleClearProjectData}
              loading={clearingData}
              disabled={clearingData || isAssessing || isUploading}
            >
              Clear Embeddings
            </Button>

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
                          <Tooltip label="View Facts">
                            <ActionIcon
                              size="sm"
                              variant="subtle"
                              color="blue"
                              disabled={file.processing_status !== 'completed'}
                              onClick={() => handleViewFacts(file)}
                            >
                              <IconList size={14} />
                            </ActionIcon>
                          </Tooltip>
                          <Tooltip label="View Assessment">
                            <ActionIcon
                              size="sm"
                              variant="subtle"
                              color="green"
                              disabled={file.processing_status !== 'completed'}
                              onClick={() => handleViewAssessment(file)}
                            >
                              <IconEye size={14} />
                            </ActionIcon>
                          </Tooltip>
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
          <ReportDisplay
            report={finalReport}
            analysis={null}
            useJsonl={false}
          />
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

      {/* Facts Viewer Modal */}
      <FactsViewerModal
        opened={factsModalOpen}
        onClose={handleCloseFactsModal}
        projectId={projectId}
        filename={selectedFileForFacts?.filename || ''}
      />

      {/* Assessment Viewer Modal */}
      <AssessmentViewerModal
        opened={assessmentModalOpen}
        onClose={handleCloseAssessmentModal}
        projectId={projectId}
        filename={selectedFileForAssessment?.filename || ''}
      />

      {/* Note: Test LLM Modal and LLM Configuration Selector removed */}
      {/* Projects now use their default LLM configuration */}

      {/* Right Log Pane */}
      <RightLogPane
        opened={rightLogPaneOpen}
        onClose={() => setRightLogPaneOpen(false)}
        assessmentLogs={[]}
        agenticLogs={[]}
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
});

export default FileUpload;
