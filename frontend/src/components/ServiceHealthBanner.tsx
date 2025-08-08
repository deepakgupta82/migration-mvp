import React, { useState, useEffect } from 'react';
import { Alert, Loader } from '@mantine/core';
import { IconCheck, IconExclamationMark, IconX } from '@tabler/icons-react';

interface ServiceHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  services: {
    backend: boolean;
    project_service: boolean;
    reporting_service: boolean;
  };
}

export const ServiceHealthBanner: React.FC = () => {
  const [health, setHealth] = useState<ServiceHealth | null>(null);
  const [loading, setLoading] = useState(true);

  const checkServiceHealth = async () => {
    try {
      const services = {
        backend: false,
        project_service: false,
        reporting_service: false,
      };

      // Check backend health
      try {
        const backendResponse = await fetch('http://localhost:8000/health', {
          method: 'GET',
          timeout: 5000
        } as any);
        services.backend = backendResponse.ok;
      } catch (error) {
        console.debug('Backend health check failed:', error);
        services.backend = false;
      }

      // Check project service health
      try {
        const projectResponse = await fetch('http://localhost:8002/health', {
          method: 'GET',
          timeout: 5000
        } as any);
        services.project_service = projectResponse.ok;
      } catch (error) {
        console.debug('Project service health check failed:', error);
        services.project_service = false;
      }

      // Check reporting service health
      try {
        const reportingResponse = await fetch('http://localhost:8001/health', {
          method: 'GET',
          timeout: 5000
        } as any);
        services.reporting_service = reportingResponse.ok;
      } catch (error) {
        console.debug('Reporting service health check failed:', error);
        services.reporting_service = false;
      }

      // Determine overall health status
      const healthyCount = Object.values(services).filter(Boolean).length;
      const totalCount = Object.values(services).length;

      let status: ServiceHealth['status'];
      if (healthyCount === totalCount) {
        status = 'healthy';
      } else if (healthyCount >= totalCount / 2) {
        status = 'degraded';
      } else {
        status = 'unhealthy';
      }

      setHealth({ status, services });
    } catch (error) {
      console.error('Health check failed:', error);
      setHealth({
        status: 'unhealthy',
        services: {
          backend: false,
          project_service: false,
          reporting_service: false,
        }
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkServiceHealth();
    // Check health every 30 seconds
    const interval = setInterval(checkServiceHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <Alert
        icon={<Loader size={18} />}
        color="blue"
        style={{ padding: '8px 16px', fontSize: '14px' }}
      >
        Checking system health...
      </Alert>
    );
  }

  if (!health) {
    return null;
  }

  if (health.status === 'healthy') {
    return (
      <Alert
        icon={<IconCheck size={18} />}
        color="green"
        style={{ padding: '8px 16px', fontSize: '14px' }}
      >
        All systems are running smoothly.
      </Alert>
    );
  }

  if (health.status === 'degraded') {
    const unhealthyServices = Object.entries(health.services)
      .filter(([_, healthy]) => !healthy)
      .map(([service, _]) => service.replace('_', ' '));

    return (
      <Alert
        icon={<IconExclamationMark size={18} />}
        color="orange"
        style={{ padding: '8px 16px', fontSize: '14px' }}
      >
        Some services are experiencing issues: {unhealthyServices.join(', ')}. Performance may be degraded.
      </Alert>
    );
  }

  return (
    <Alert
      icon={<IconX size={18} />}
      color="red"
      style={{ padding: '8px 16px', fontSize: '14px' }}
    >
      Critical system issues detected. Multiple services are unavailable.
    </Alert>
  );
};
