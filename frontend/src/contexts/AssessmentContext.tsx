import React, { createContext, useContext, useState, useEffect } from 'react';

interface AssessmentState {
  isRunning: boolean;
  projectId: string | null;
  startTime: Date | null;
  logs: string[];
  status: 'idle' | 'running' | 'completed' | 'failed';
  progress: number;
}

interface AssessmentContextType {
  assessmentState: AssessmentState;
  startAssessment: (projectId: string) => void;
  stopAssessment: () => void;
  addLog: (log: string) => void;
  setStatus: (status: AssessmentState['status']) => void;
  setProgress: (progress: number) => void;
}

const AssessmentContext = createContext<AssessmentContextType | undefined>(undefined);

export const AssessmentProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [assessmentState, setAssessmentState] = useState<AssessmentState>({
    isRunning: false,
    projectId: null,
    startTime: null,
    logs: [],
    status: 'idle',
    progress: 0,
  });

  const startAssessment = (projectId: string) => {
    setAssessmentState({
      isRunning: true,
      projectId,
      startTime: new Date(),
      logs: [`🚀 Assessment started for project ${projectId}`],
      status: 'running',
      progress: 0,
    });
  };

  const stopAssessment = () => {
    setAssessmentState(prev => ({
      ...prev,
      isRunning: false,
      status: prev.status === 'running' ? 'completed' : prev.status,
    }));
  };

  const addLog = (log: string) => {
    const timestamp = new Date().toLocaleTimeString();
    const logWithTimestamp = `[${timestamp}] ${log}`;
    
    setAssessmentState(prev => ({
      ...prev,
      logs: [...prev.logs, logWithTimestamp].slice(-50), // Keep only last 50 logs
    }));
  };

  const setStatus = (status: AssessmentState['status']) => {
    setAssessmentState(prev => ({
      ...prev,
      status,
      isRunning: status === 'running',
    }));
  };

  const setProgress = (progress: number) => {
    setAssessmentState(prev => ({
      ...prev,
      progress: Math.max(0, Math.min(100, progress)),
    }));
  };

  // Auto-fail assessment after 30 minutes
  useEffect(() => {
    if (assessmentState.isRunning && assessmentState.startTime) {
      const timeout = setTimeout(() => {
        if (assessmentState.status === 'running') {
          setStatus('failed');
          addLog('❌ Assessment timed out after 30 minutes');
        }
      }, 30 * 60 * 1000); // 30 minutes

      return () => clearTimeout(timeout);
    }
  }, [assessmentState.isRunning, assessmentState.startTime]);

  return (
    <AssessmentContext.Provider
      value={{
        assessmentState,
        startAssessment,
        stopAssessment,
        addLog,
        setStatus,
        setProgress,
      }}
    >
      {children}
    </AssessmentContext.Provider>
  );
};

export const useAssessment = () => {
  const context = useContext(AssessmentContext);
  if (context === undefined) {
    throw new Error('useAssessment must be used within an AssessmentProvider');
  }
  return context;
};
