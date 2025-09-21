import { useCallback } from 'react';
import { useLogContext } from '../contexts/LogContext';
import { useAssessment } from '../contexts/AssessmentContext';

/**
 * Custom hook for session cleanup middleware
 * Clears previous session data when starting new document processing
 */
export const useSessionCleanup = () => {
  const { clearLogs, subscribeToWebSocket } = useLogContext();
  const { setStatus, setProgress } = useAssessment();

  /**
   * Cleans up previous session data for a project
   * - Clears all logs for the project
   * - Resets assessment progress state
   * - Unsubscribes from WebSocket connections
   */
  const cleanupSession = useCallback((projectId: string) => {
    if (!projectId) {
      console.warn('useSessionCleanup: No projectId provided for cleanup');
      return;
    }

    console.log(`Cleaning up previous session data for project: ${projectId}`);

    try {
      // Clear all logs for the project
      clearLogs(undefined, projectId);

      // Reset assessment state
      setStatus('idle');
      setProgress(0);

      // Unsubscribe from WebSocket connections
      subscribeToWebSocket(projectId, false);

      console.log(`Session cleanup completed for project: ${projectId}`);
    } catch (error) {
      console.error('Error during session cleanup:', error);
    }
  }, [clearLogs, setStatus, setProgress, subscribeToWebSocket]);

  return { cleanupSession };
};