/**
 * Notification Interceptor Hook
 * Automatically intercepts user operations and generates enterprise-grade notifications
 */

import { useCallback } from 'react';
import { notifications as mantineNotifications } from '@mantine/notifications';
import { notificationService, OperationMetadata, NotificationOptions } from '../services/notificationService';

interface InterceptorOptions extends NotificationOptions {
  showToast?: boolean;
  toastTitle?: string;
  toastMessage?: string;
  toastColor?: string;
}

export const useNotificationInterceptor = () => {
  
  /**
   * Wrap any async operation with automatic notification generation
   */
  const interceptOperation = useCallback(async <T>(
    operation: () => Promise<T>,
    config: {
      operationType: string;
      operationName: string;
      successNotification?: (result: T, correlationId: string) => Promise<void>;
      errorNotification?: (error: any, correlationId: string) => Promise<void>;
      options?: InterceptorOptions;
    }
  ): Promise<{ result?: T; error?: any; correlationId: string }> => {
    
    const correlationId = notificationService.generateCorrelationId(config.operationType);
    
    try {
      // Execute the operation
      const result = await operation();
      
      // Generate success notification if provided
      if (config.successNotification) {
        await config.successNotification(result, correlationId);
      }
      
      // Show toast notification if enabled
      if (config.options?.showToast !== false) {
        mantineNotifications.show({
          title: config.options?.toastTitle || 'Success',
          message: config.options?.toastMessage || `${config.operationName} completed successfully`,
          color: config.options?.toastColor || 'green',
        });
      }
      
      return { result, correlationId };
      
    } catch (error: any) {
      // Generate error notification if provided
      if (config.errorNotification) {
        await config.errorNotification(error, correlationId);
      } else {
        // Default error notification
        await notificationService.notifyError(
          config.operationName,
          error.message || error.toString(),
          config.options?.metadata,
          { correlationId, ...config.options }
        );
      }
      
      // Show error toast notification
      if (config.options?.showToast !== false) {
        mantineNotifications.show({
          title: 'Error',
          message: config.options?.toastMessage || `${config.operationName} failed: ${error.message}`,
          color: 'red',
        });
      }
      
      return { error, correlationId };
    }
  }, []);

  // =============================================================================
  // PROJECT OPERATION INTERCEPTORS
  // =============================================================================

  const interceptProjectCreate = useCallback(async (
    operation: () => Promise<any>,
    projectName: string,
    options: InterceptorOptions = {}
  ) => {
    return interceptOperation(operation, {
      operationType: 'project-create',
      operationName: 'Project Creation',
      successNotification: async (result, correlationId) => {
        await notificationService.notifyProjectCreated(
          projectName,
          result.id || result.project_id || 'unknown',
          { correlationId, ...options }
        );
      },
      options: {
        showToast: true,
        toastTitle: 'Project Created',
        toastMessage: `Project "${projectName}" created successfully`,
        ...options
      }
    });
  }, [interceptOperation]);

  const interceptProjectUpdate = useCallback(async (
    operation: () => Promise<any>,
    projectName: string,
    projectId: string,
    changes: string[],
    options: InterceptorOptions = {}
  ) => {
    return interceptOperation(operation, {
      operationType: 'project-update',
      operationName: 'Project Update',
      successNotification: async (result, correlationId) => {
        await notificationService.notifyProjectUpdated(
          projectName,
          projectId,
          changes,
          { correlationId, ...options }
        );
      },
      options: {
        showToast: true,
        toastTitle: 'Project Updated',
        toastMessage: `Project "${projectName}" updated successfully`,
        ...options
      }
    });
  }, [interceptOperation]);

  const interceptProjectDelete = useCallback(async (
    operation: () => Promise<any>,
    projectName: string,
    options: InterceptorOptions = {}
  ) => {
    return interceptOperation(operation, {
      operationType: 'project-delete',
      operationName: 'Project Deletion',
      successNotification: async (result, correlationId) => {
        await notificationService.notifyProjectDeleted(
          projectName,
          { correlationId, ...options }
        );
      },
      options: {
        showToast: true,
        toastTitle: 'Project Deleted',
        toastMessage: `Project "${projectName}" deleted successfully`,
        toastColor: 'orange',
        ...options
      }
    });
  }, [interceptOperation]);

  // =============================================================================
  // DOCUMENT OPERATION INTERCEPTORS
  // =============================================================================

  const interceptDocumentUpload = useCallback(async (
    operation: () => Promise<any>,
    fileName: string,
    projectId: string,
    projectName: string,
    options: InterceptorOptions = {}
  ) => {
    return interceptOperation(operation, {
      operationType: 'document-upload',
      operationName: 'Document Upload',
      successNotification: async (result, correlationId) => {
        await notificationService.notifyDocumentUploaded(
          fileName,
          projectId,
          projectName,
          { correlationId, ...options }
        );
      },
      options: {
        showToast: true,
        toastTitle: 'Document Uploaded',
        toastMessage: `"${fileName}" uploaded successfully`,
        ...options
      }
    });
  }, [interceptOperation]);

  const interceptDocumentDelete = useCallback(async (
    operation: () => Promise<any>,
    fileName: string,
    projectId: string,
    projectName: string,
    options: InterceptorOptions = {}
  ) => {
    return interceptOperation(operation, {
      operationType: 'document-delete',
      operationName: 'Document Deletion',
      successNotification: async (result, correlationId) => {
        await notificationService.notifyDocumentDeleted(
          fileName,
          projectId,
          projectName,
          { correlationId, ...options }
        );
      },
      options: {
        showToast: true,
        toastTitle: 'Document Deleted',
        toastMessage: `"${fileName}" deleted successfully`,
        toastColor: 'orange',
        ...options
      }
    });
  }, [interceptOperation]);

  // =============================================================================
  // PROCESSING OPERATION INTERCEPTORS
  // =============================================================================

  const interceptProcessingStart = useCallback(async (
    operation: () => Promise<any>,
    projectId: string,
    projectName: string,
    fileCount: number,
    options: InterceptorOptions = {}
  ) => {
    return interceptOperation(operation, {
      operationType: 'processing-start',
      operationName: 'Document Processing',
      successNotification: async (result, correlationId) => {
        await notificationService.notifyProcessingStarted(
          projectId,
          projectName,
          fileCount,
          { correlationId, ...options }
        );
      },
      options: {
        showToast: true,
        toastTitle: 'Processing Started',
        toastMessage: `Processing ${fileCount} documents...`,
        toastColor: 'blue',
        ...options
      }
    });
  }, [interceptOperation]);

  const interceptProcessingComplete = useCallback(async (
    operation: () => Promise<any>,
    projectId: string,
    projectName: string,
    results: { filesProcessed: number; embeddingsCreated: number; graphNodesAdded: number },
    options: InterceptorOptions = {}
  ) => {
    return interceptOperation(operation, {
      operationType: 'processing-complete',
      operationName: 'Document Processing',
      successNotification: async (result, correlationId) => {
        await notificationService.notifyProcessingCompleted(
          projectId,
          projectName,
          results,
          { correlationId, ...options }
        );
      },
      options: {
        showToast: true,
        toastTitle: 'Processing Complete',
        toastMessage: `Successfully processed ${results.filesProcessed} documents`,
        ...options
      }
    });
  }, [interceptOperation]);

  // =============================================================================
  // DELIVERABLE OPERATION INTERCEPTORS
  // =============================================================================

  const interceptDeliverableGeneration = useCallback(async (
    operation: () => Promise<any>,
    deliverableName: string,
    projectId: string,
    projectName: string,
    options: InterceptorOptions = {}
  ) => {
    return interceptOperation(operation, {
      operationType: 'deliverable-generate',
      operationName: 'Deliverable Generation',
      successNotification: async (result, correlationId) => {
        await notificationService.notifyDeliverableGenerated(
          deliverableName,
          projectId,
          projectName,
          { correlationId, ...options }
        );
      },
      options: {
        showToast: true,
        toastTitle: 'Deliverable Generated',
        toastMessage: `"${deliverableName}" generated successfully`,
        ...options
      }
    });
  }, [interceptOperation]);

  // =============================================================================
  // LLM CONFIGURATION INTERCEPTORS
  // =============================================================================

  const interceptLLMConfigSave = useCallback(async (
    operation: () => Promise<any>,
    configName: string,
    provider: string,
    model: string,
    options: InterceptorOptions = {}
  ) => {
    return interceptOperation(operation, {
      operationType: 'llm-config-save',
      operationName: 'LLM Configuration Save',
      successNotification: async (result, correlationId) => {
        await notificationService.notifyLLMConfigSaved(
          configName,
          provider,
          model,
          { correlationId, ...options }
        );
      },
      options: {
        showToast: true,
        toastTitle: 'LLM Configuration Saved',
        toastMessage: `"${configName}" saved successfully`,
        ...options
      }
    });
  }, [interceptOperation]);

  const interceptLLMConfigTest = useCallback(async (
    operation: () => Promise<any>,
    configName: string,
    provider: string,
    model: string,
    options: InterceptorOptions = {}
  ) => {
    return interceptOperation(operation, {
      operationType: 'llm-config-test',
      operationName: 'LLM Configuration Test',
      successNotification: async (result, correlationId) => {
        await notificationService.notifyLLMConfigTested(
          configName,
          provider,
          model,
          true,
          { correlationId, ...options }
        );
      },
      errorNotification: async (error, correlationId) => {
        await notificationService.notifyLLMConfigTested(
          configName,
          provider,
          model,
          false,
          { correlationId, ...options }
        );
      },
      options: {
        showToast: true,
        toastTitle: 'LLM Test Complete',
        ...options
      }
    });
  }, [interceptOperation]);

  return {
    // Core interceptor
    interceptOperation,
    
    // Project operations
    interceptProjectCreate,
    interceptProjectUpdate,
    interceptProjectDelete,
    
    // Document operations
    interceptDocumentUpload,
    interceptDocumentDelete,
    
    // Processing operations
    interceptProcessingStart,
    interceptProcessingComplete,
    
    // Deliverable operations
    interceptDeliverableGeneration,
    
    // LLM configuration operations
    interceptLLMConfigSave,
    interceptLLMConfigTest,
  };
};

export default useNotificationInterceptor;