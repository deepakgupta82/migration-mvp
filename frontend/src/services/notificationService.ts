/**
 * Enterprise-Grade Notification Service
 * Automatically generates notifications for all user operations with correlation IDs
 */

import { apiService } from './api';

export interface OperationMetadata {
  projectId?: string;
  projectName?: string;
  fileName?: string;
  deliverableName?: string;
  configName?: string;
  operation?: string;
  details?: Record<string, any>;
  // Additional properties for comprehensive tracking
  changes?: string[];
  fileCount?: number;
  results?: {
    filesProcessed?: number;
    embeddingsCreated?: number;
    graphNodesAdded?: number;
  };
  error?: string;
  provider?: string;
  model?: string;
  event?: string;
  testResult?: string;
  failedOperation?: string;
  clientName?: string;
  // LLM Configuration specific properties
  isEditing?: boolean;
  configId?: string;
}

export interface NotificationOptions {
  correlationId?: string;
  metadata?: OperationMetadata;
  suppressToast?: boolean; // Skip Mantine toast if already handled
}

class EnterpriseNotificationService {
  private userId = 'user_001'; // Would come from auth context in real app
  
  /**
   * Generate a unique correlation ID for tracking operations
   */
  generateCorrelationId(operation: string): string {
    const timestamp = Date.now();
    const random = Math.random().toString(36).substr(2, 8);
    return `${operation}-${timestamp}-${random}`;
  }

  /**
   * Create a notification with correlation ID and metadata
   */
  private async createNotification(
    type: 'success' | 'error' | 'warning' | 'info',
    title: string,
    message: string,
    options: NotificationOptions = {}
  ): Promise<void> {
    try {
      const workspaceId = options.metadata?.projectId || 'default';
      const correlationId = options.correlationId || this.generateCorrelationId('generic');

      await apiService.createNotification(this.userId, workspaceId, {
        notification_type: type,
        title,
        message,
        correlation_id: correlationId,
        metadata: {
          ...options.metadata,
          timestamp: new Date().toISOString(),
          user_id: this.userId
        }
      });
    } catch (error) {
      console.error('Failed to create notification:', error);
    }
  }

  // =============================================================================
  // PROJECT OPERATIONS
  // =============================================================================

  async notifyProjectCreated(
    projectName: string,
    projectId: string,
    options: NotificationOptions = {}
  ): Promise<string> {
    const correlationId = options.correlationId || this.generateCorrelationId('project-create');
    
    await this.createNotification(
      'success',
      'Project Created Successfully',
      `New project "${projectName}" has been created and is ready for file uploads.`,
      {
        correlationId,
        metadata: {
          projectId,
          projectName,
          operation: 'project_create',
          ...options.metadata
        }
      }
    );

    return correlationId;
  }

  async notifyProjectUpdated(
    projectName: string,
    projectId: string,
    changes: string[],
    options: NotificationOptions = {}
  ): Promise<string> {
    const correlationId = options.correlationId || this.generateCorrelationId('project-update');
    
    await this.createNotification(
      'info',
      'Project Updated',
      `Project "${projectName}" has been updated. Changes: ${changes.join(', ')}.`,
      {
        correlationId,
        metadata: {
          projectId,
          projectName,
          operation: 'project_update',
          changes,
          ...options.metadata
        }
      }
    );

    return correlationId;
  }

  async notifyProjectDeleted(
    projectName: string,
    options: NotificationOptions = {}
  ): Promise<string> {
    const correlationId = options.correlationId || this.generateCorrelationId('project-delete');
    
    await this.createNotification(
      'warning',
      'Project Deleted',
      `Project "${projectName}" has been permanently deleted along with all associated data.`,
      {
        correlationId,
        metadata: {
          projectName,
          operation: 'project_delete',
          ...options.metadata
        }
      }
    );

    return correlationId;
  }

  // =============================================================================
  // DOCUMENT OPERATIONS
  // =============================================================================

  async notifyDocumentUploaded(
    fileName: string,
    projectId: string,
    projectName: string,
    options: NotificationOptions = {}
  ): Promise<string> {
    const correlationId = options.correlationId || this.generateCorrelationId('document-upload');
    
    await this.createNotification(
      'success',
      'Document Uploaded',
      `Document "${fileName}" has been successfully uploaded to project "${projectName}".`,
      {
        correlationId,
        metadata: {
          projectId,
          projectName,
          fileName,
          operation: 'document_upload',
          ...options.metadata
        }
      }
    );

    return correlationId;
  }

  async notifyDocumentDeleted(
    fileName: string,
    projectId: string,
    projectName: string,
    options: NotificationOptions = {}
  ): Promise<string> {
    const correlationId = options.correlationId || this.generateCorrelationId('document-delete');
    
    await this.createNotification(
      'warning',
      'Document Deleted',
      `Document "${fileName}" has been deleted from project "${projectName}".`,
      {
        correlationId,
        metadata: {
          projectId,
          projectName,
          fileName,
          operation: 'document_delete',
          ...options.metadata
        }
      }
    );

    return correlationId;
  }

  // =============================================================================
  // DOCUMENT PROCESSING OPERATIONS
  // =============================================================================

  async notifyProcessingStarted(
    projectId: string,
    projectName: string,
    fileCount: number,
    options: NotificationOptions = {}
  ): Promise<string> {
    const correlationId = options.correlationId || this.generateCorrelationId('processing-start');
    
    await this.createNotification(
      'info',
      'Document Processing Started',
      `Processing ${fileCount} document(s) in project "${projectName}". This may take several minutes.`,
      {
        correlationId,
        metadata: {
          projectId,
          projectName,
          fileCount,
          operation: 'processing_start',
          ...options.metadata
        }
      }
    );

    return correlationId;
  }

  async notifyProcessingCompleted(
    projectId: string,
    projectName: string,
    results: {
      filesProcessed: number;
      embeddingsCreated: number;
      graphNodesAdded: number;
    },
    options: NotificationOptions = {}
  ): Promise<string> {
    const correlationId = options.correlationId || this.generateCorrelationId('processing-complete');
    
    await this.createNotification(
      'success',
      'Document Processing Completed',
      `Successfully processed ${results.filesProcessed} documents in "${projectName}". Created ${results.embeddingsCreated} embeddings and ${results.graphNodesAdded} knowledge graph nodes.`,
      {
        correlationId,
        metadata: {
          projectId,
          projectName,
          operation: 'processing_complete',
          results,
          ...options.metadata
        }
      }
    );

    return correlationId;
  }

  async notifyProcessingFailed(
    projectId: string,
    projectName: string,
    error: string,
    options: NotificationOptions = {}
  ): Promise<string> {
    const correlationId = options.correlationId || this.generateCorrelationId('processing-error');
    
    await this.createNotification(
      'error',
      'Document Processing Failed',
      `Processing failed for project "${projectName}". Error: ${error}`,
      {
        correlationId,
        metadata: {
          projectId,
          projectName,
          error,
          operation: 'processing_error',
          ...options.metadata
        }
      }
    );

    return correlationId;
  }

  // =============================================================================
  // DELIVERABLE OPERATIONS
  // =============================================================================

  async notifyDeliverableGenerated(
    deliverableName: string,
    projectId: string,
    projectName: string,
    options: NotificationOptions = {}
  ): Promise<string> {
    const correlationId = options.correlationId || this.generateCorrelationId('deliverable-generate');
    
    await this.createNotification(
      'success',
      'Deliverable Generated',
      `Deliverable "${deliverableName}" has been successfully generated for project "${projectName}".`,
      {
        correlationId,
        metadata: {
          projectId,
          projectName,
          deliverableName,
          operation: 'deliverable_generate',
          ...options.metadata
        }
      }
    );

    return correlationId;
  }

  async notifyDeliverableFailed(
    deliverableName: string,
    projectId: string,
    projectName: string,
    error: string,
    options: NotificationOptions = {}
  ): Promise<string> {
    const correlationId = options.correlationId || this.generateCorrelationId('deliverable-error');
    
    await this.createNotification(
      'error',
      'Deliverable Generation Failed',
      `Failed to generate deliverable "${deliverableName}" for project "${projectName}". Error: ${error}`,
      {
        correlationId,
        metadata: {
          projectId,
          projectName,
          deliverableName,
          error,
          operation: 'deliverable_error',
          ...options.metadata
        }
      }
    );

    return correlationId;
  }

  // =============================================================================
  // LLM CONFIGURATION OPERATIONS
  // =============================================================================

  async notifyLLMConfigSaved(
    configName: string,
    provider: string,
    model: string,
    options: NotificationOptions = {}
  ): Promise<string> {
    const correlationId = options.correlationId || this.generateCorrelationId('llm-config-save');
    
    await this.createNotification(
      'success',
      'LLM Configuration Saved',
      `LLM configuration "${configName}" (${provider}/${model}) has been saved successfully.`,
      {
        correlationId,
        metadata: {
          configName,
          provider,
          model,
          operation: 'llm_config_save',
          ...options.metadata
        }
      }
    );

    return correlationId;
  }

  async notifyLLMConfigTested(
    configName: string,
    provider: string,
    model: string,
    success: boolean,
    options: NotificationOptions = {}
  ): Promise<string> {
    const correlationId = options.correlationId || this.generateCorrelationId('llm-config-test');
    
    await this.createNotification(
      success ? 'success' : 'error',
      `LLM Configuration ${success ? 'Test Passed' : 'Test Failed'}`,
      `LLM configuration "${configName}" (${provider}/${model}) test ${success ? 'completed successfully' : 'failed'}.`,
      {
        correlationId,
        metadata: {
          configName,
          provider,
          model,
          testResult: success ? 'passed' : 'failed',
          operation: 'llm_config_test',
          ...options.metadata
        }
      }
    );

    return correlationId;
  }

  // =============================================================================
  // GENERIC ERROR NOTIFICATIONS
  // =============================================================================

  async notifyError(
    operation: string,
    error: string,
    context: OperationMetadata = {},
    options: NotificationOptions = {}
  ): Promise<string> {
    const correlationId = options.correlationId || this.generateCorrelationId('error');
    
    await this.createNotification(
      'error',
      'Operation Failed',
      `${operation} failed: ${error}`,
      {
        correlationId,
        metadata: {
          operation: 'error',
          error,
          failedOperation: operation,
          ...context,
          ...options.metadata
        }
      }
    );

    return correlationId;
  }

  // =============================================================================
  // SYSTEM OPERATIONS
  // =============================================================================

  async notifySystemEvent(
    event: string,
    message: string,
    type: 'info' | 'warning' | 'error' = 'info',
    options: NotificationOptions = {}
  ): Promise<string> {
    const correlationId = options.correlationId || this.generateCorrelationId('system-event');
    
    await this.createNotification(
      type,
      'System Event',
      `${event}: ${message}`,
      {
        correlationId,
        metadata: {
          event,
          operation: 'system_event',
          ...options.metadata
        }
      }
    );

    return correlationId;
  }
}

// Export singleton instance
export const notificationService = new EnterpriseNotificationService();
export default notificationService;