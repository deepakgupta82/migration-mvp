/**
 * LLM Configuration Context - Global state management for LLM configurations
 * Loads configurations on app startup and provides them throughout the app
 */

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { notifications } from '@mantine/notifications';

export interface LLMConfiguration {
  id: string;
  name: string;
  provider: string;
  model: string;
  status: 'configured' | 'needs_key';
  api_key?: string;
  temperature?: number;
  max_tokens?: number;
  description?: string;
  created_at?: string;
  updated_at?: string;
}

interface LLMConfigContextType {
  configurations: LLMConfiguration[];
  loading: boolean;
  error: string | null;
  reloadConfigurations: () => Promise<void>;
  isConfigured: boolean;
}

const LLMConfigContext = createContext<LLMConfigContextType | undefined>(undefined);

export const useLLMConfig = () => {
  const context = useContext(LLMConfigContext);
  if (context === undefined) {
    throw new Error('useLLMConfig must be used within a LLMConfigProvider');
  }
  return context;
};

interface LLMConfigProviderProps {
  children: ReactNode;
}

export const LLMConfigProvider: React.FC<LLMConfigProviderProps> = ({ children }) => {
  const [configurations, setConfigurations] = useState<LLMConfiguration[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadConfigurations = async () => {
    try {
      setLoading(true);
      setError(null);

      // First, try to force reload configurations from backend
      try {
        await fetch('http://localhost:8000/api/reload-llm-configs', {
          method: 'POST',
        });
      } catch (reloadError) {
        console.warn('Failed to force reload LLM configs:', reloadError);
      }

      // Then fetch the configurations
      const response = await fetch('http://localhost:8000/llm-configurations');
      if (response.ok) {
        const configs = await response.json();
        setConfigurations(configs);
        console.log(`Loaded ${configs.length} LLM configurations`);
      } else {
        throw new Error(`Failed to load configurations: ${response.status}`);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMessage);
      console.error('Failed to load LLM configurations:', err);
      
      // Show notification only if it's not the initial load
      if (configurations.length > 0) {
        notifications.show({
          title: 'Configuration Error',
          message: 'Failed to load LLM configurations. Please check your connection.',
          color: 'red',
        });
      }
    } finally {
      setLoading(false);
    }
  };

  const reloadConfigurations = async () => {
    await loadConfigurations();
  };

  // Load configurations on mount
  useEffect(() => {
    loadConfigurations();
  }, []);

  // Retry loading if backend becomes available
  useEffect(() => {
    if (error && configurations.length === 0) {
      const retryInterval = setInterval(() => {
        console.log('Retrying LLM configuration load...');
        loadConfigurations();
      }, 10000); // Retry every 10 seconds

      return () => clearInterval(retryInterval);
    }
  }, [error, configurations.length]);

  const isConfigured = configurations.some(config => config.status === 'configured');

  const value: LLMConfigContextType = {
    configurations,
    loading,
    error,
    reloadConfigurations,
    isConfigured,
  };

  return (
    <LLMConfigContext.Provider value={value}>
      {children}
    </LLMConfigContext.Provider>
  );
};
