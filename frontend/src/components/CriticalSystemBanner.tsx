import React, { useState, useEffect, useRef } from 'react';
import { Alert, Group, Text, ActionIcon, Badge, Stack, Button } from '@mantine/core';
import { IconAlertTriangle, IconX, IconRefresh, IconSettings } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';

interface SystemHealth {
  status: 'healthy' | 'warning' | 'critical';
  message: string;
  count?: number;
  configured_count?: number;
  timestamp: string;
}

export const CriticalSystemBanner: React.FC = () => {
  const [llmHealth, setLlmHealth] = useState<SystemHealth | null>(null);
  const [isVisible, setIsVisible] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [componentVisible, setComponentVisible] = useState(true);
  const [isTabActive, setIsTabActive] = useState(true);
  const navigate = useNavigate();
  const lastCallRef = useRef<number>(0);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const observerRef = useRef<IntersectionObserver | null>(null);

  const checkLLMHealth = async () => {
    const now = Date.now();
    const debounceTime = 1000; // 1 second debounce
    if (now - lastCallRef.current < debounceTime) {
      return;
    }
    lastCallRef.current = now;

    try {
      setIsLoading(true);
  const response = await fetch('/api/health/llm-configurations');
      if (response.ok) {
        const health: SystemHealth = await response.json();
        setLlmHealth(health);

        // Show banner only for warning or critical status
        setIsVisible(health.status === 'warning' || health.status === 'critical');
      }
    } catch (error) {
      console.error('Failed to check LLM health:', error);
      // Show critical banner if health check fails
      setLlmHealth({
        status: 'critical',
        message: 'Unable to check LLM configuration status',
        count: 0,
        timestamp: new Date().toISOString()
      });
      setIsVisible(true);
    } finally {
      setIsLoading(false);
    }
  };

  // Check LLM health on component mount and conditionally
  useEffect(() => {
    // Initial health check
    checkLLMHealth();

    // Set up visibility change listener
    const handleVisibilityChange = () => {
      setIsTabActive(!document.hidden);
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);

    // Set up intersection observer for component visibility
    const element = document.getElementById('critical-system-banner');
    if (element) {
      observerRef.current = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            setComponentVisible(entry.isIntersecting);
          });
        },
        { threshold: 0.1 }
      );
      observerRef.current.observe(element);
    }

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      if (observerRef.current) {
        observerRef.current.disconnect();
      }
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  // Effect to manage polling interval based on visibility and tab activity
  useEffect(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    if (componentVisible && isTabActive) {
      // Check health every 10 minutes (600000 ms) when visible and tab active
      intervalRef.current = setInterval(checkLLMHealth, 600000);
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [componentVisible, isTabActive]);

  const handleDismiss = () => {
    setIsVisible(false);
  };

  const handleGoToSettings = () => {
    navigate('/settings');
    setIsVisible(false);
  };

  const getBannerColor = (status: string) => {
    switch (status) {
      case 'critical': return 'red';
      case 'warning': return 'orange';
      default: return 'blue';
    }
  };

  const getBannerIcon = (status: string) => {
    return <IconAlertTriangle size={20} />;
  };

  if (!isVisible || !llmHealth) {
    return null;
  }

  return (
    <Alert
      id="critical-system-banner"
      color={getBannerColor(llmHealth.status)}
      icon={getBannerIcon(llmHealth.status)}
      withCloseButton={false}
      style={{
        position: 'relative',
        zIndex: 100,
        borderRadius: 0,
        borderLeft: 'none',
        borderRight: 'none',
        borderTop: 'none',
        margin: 0,
        marginBottom: 0
      }}
    >
      <Group justify="space-between" wrap="nowrap" align="flex-start">
        <Stack gap="xs" style={{ flex: 1, minWidth: 0 }}>
          <Group gap="sm" wrap="nowrap">
            <Badge color={getBannerColor(llmHealth.status)} variant="filled" size="sm">
              {llmHealth.status.toUpperCase()}
            </Badge>
            <Text size="sm" fw={600} style={{ whiteSpace: 'normal', wordBreak: 'break-word' }}>
              LLM Configuration Issue
            </Text>
          </Group>

          <Text size="sm" style={{ wordBreak: 'break-word', overflowWrap: 'break-word' }}>
            {llmHealth.message}
            {llmHealth.count !== undefined && (
              <> ({llmHealth.count} total{llmHealth.configured_count !== undefined &&
                `, ${llmHealth.configured_count} configured`})</>
            )}
          </Text>

          {llmHealth.status === 'critical' && (
            <Text size="xs" c="dimmed" style={{ wordBreak: 'break-word', overflowWrap: 'break-word' }}>
              ⚠️ Platform functionality is severely limited without LLM configurations.
              Document generation, assessments, and AI features will not work.
            </Text>
          )}

          {llmHealth.status === 'warning' && (
            <Text size="xs" c="dimmed" style={{ wordBreak: 'break-word', overflowWrap: 'break-word' }}>
              ⚠️ Some LLM configurations need valid API keys to function properly.
            </Text>
          )}
        </Stack>

        <Group gap="xs" wrap="nowrap" style={{ flexShrink: 0 }}>
          <ActionIcon
            size="sm"
            variant="subtle"
            color={getBannerColor(llmHealth.status)}
            onClick={checkLLMHealth}
            loading={isLoading}
            title="Refresh status"
          >
            <IconRefresh size={14} />
          </ActionIcon>

          <Button
            size="xs"
            variant="light"
            color={getBannerColor(llmHealth.status)}
            leftSection={<IconSettings size={14} />}
            onClick={handleGoToSettings}
            style={{ whiteSpace: 'nowrap' }}
          >
            Fix in Settings
          </Button>

          <ActionIcon
            size="sm"
            variant="subtle"
            color={getBannerColor(llmHealth.status)}
            onClick={handleDismiss}
            title="Dismiss"
          >
            <IconX size={14} />
          </ActionIcon>
        </Group>
      </Group>
    </Alert>
  );
};

export default CriticalSystemBanner;
