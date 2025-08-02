import React, { useState, useEffect } from 'react';
import {
  Alert,
  Group,
  Text,
  ActionIcon,
  Badge,
  Collapse,
  Stack,
  Button,
  Loader,
} from '@mantine/core';
import {
  IconAlertTriangle,
  IconX,
  IconChevronDown,
  IconChevronUp,
  IconRefresh,
} from '@tabler/icons-react';

interface ServiceStatus {
  name: string;
  url: string;
  status: 'healthy' | 'unhealthy' | 'starting' | 'unknown';
  error?: string;
}

export const ServiceHealthBanner: React.FC = () => {
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [isVisible, setIsVisible] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isChecking, setIsChecking] = useState(false);

  const checkServiceHealth = async (service: { name: string; url: string }): Promise<ServiceStatus> => {
    try {
      const response = await fetch(service.url, {
        method: 'GET',
        timeout: 5000,
      });
      
      return {
        ...service,
        status: response.ok ? 'healthy' : 'unhealthy',
        error: response.ok ? undefined : `HTTP ${response.status}`,
      };
    } catch (error) {
      return {
        ...service,
        status: 'unhealthy',
        error: error instanceof Error ? error.message : 'Connection failed',
      };
    }
  };

  const checkAllServices = async () => {
    setIsChecking(true);
    
    const servicesToCheck = [
      { name: 'Backend API', url: 'http://localhost:8000/health' },
      { name: 'Project Service', url: 'http://localhost:8002/health' },
      { name: 'Reporting Service', url: 'http://localhost:8001/health' },
      { name: 'Weaviate', url: 'http://localhost:8080/v1/meta' },
      { name: 'Neo4j', url: 'http://localhost:7474' },
      { name: 'PostgreSQL', url: 'http://localhost:8002/health' }, // Check via project service
    ];

    const results = await Promise.all(
      servicesToCheck.map(service => checkServiceHealth(service))
    );

    setServices(results);
    
    // Show banner if any service is unhealthy
    const hasUnhealthyServices = results.some(service => service.status !== 'healthy');
    setIsVisible(hasUnhealthyServices);
    
    setIsChecking(false);
  };

  useEffect(() => {
    // Initial check
    checkAllServices();
    
    // Check every 30 seconds
    const interval = setInterval(checkAllServices, 30000);
    
    return () => clearInterval(interval);
  }, []);

  const unhealthyServices = services.filter(service => service.status !== 'healthy');
  const healthyCount = services.filter(service => service.status === 'healthy').length;

  if (!isVisible || services.length === 0) {
    return null;
  }

  return (
    <Alert
      color="orange"
      icon={<IconAlertTriangle size={16} />}
      withCloseButton
      onClose={() => setIsVisible(false)}
      styles={{
        root: {
          margin: 0,
          borderRadius: 0,
          borderLeft: 'none',
          borderRight: 'none',
          borderTop: 'none',
        },
      }}
    >
      <Group justify="space-between" wrap="nowrap">
        <Group gap="sm" wrap="nowrap">
          <Text size="sm" fw={500}>
            Service Issues Detected
          </Text>
          <Badge size="sm" color="orange" variant="light">
            {healthyCount}/{services.length} Services Healthy
          </Badge>
          <Text size="xs" c="dimmed">
            {unhealthyServices.map(s => s.name).join(', ')} unavailable
          </Text>
        </Group>
        
        <Group gap="xs" wrap="nowrap">
          <ActionIcon
            variant="subtle"
            size="sm"
            onClick={checkAllServices}
            loading={isChecking}
          >
            <IconRefresh size={14} />
          </ActionIcon>
          <ActionIcon
            variant="subtle"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
          >
            {isExpanded ? <IconChevronUp size={14} /> : <IconChevronDown size={14} />}
          </ActionIcon>
        </Group>
      </Group>

      <Collapse in={isExpanded}>
        <Stack gap="xs" mt="sm">
          {services.map((service) => (
            <Group key={service.name} justify="space-between" wrap="nowrap">
              <Group gap="xs" wrap="nowrap">
                <Text size="xs" fw={500} style={{ minWidth: '120px' }}>
                  {service.name}
                </Text>
                <Badge
                  size="xs"
                  color={
                    service.status === 'healthy' ? 'green' :
                    service.status === 'starting' ? 'yellow' : 'red'
                  }
                  variant="light"
                >
                  {service.status}
                </Badge>
              </Group>
              {service.error && (
                <Text size="xs" c="dimmed" style={{ fontFamily: 'monospace' }}>
                  {service.error}
                </Text>
              )}
            </Group>
          ))}
          
          <Group gap="xs" mt="xs">
            <Button
              size="xs"
              variant="light"
              color="blue"
              onClick={() => window.open('http://localhost:7474', '_blank')}
            >
              Neo4j Browser
            </Button>
            <Button
              size="xs"
              variant="light"
              color="blue"
              onClick={() => window.open('http://localhost:9001', '_blank')}
            >
              MinIO Console
            </Button>
            <Button
              size="xs"
              variant="light"
              color="orange"
              onClick={checkAllServices}
              loading={isChecking}
            >
              Refresh All
            </Button>
          </Group>
        </Stack>
      </Collapse>
    </Alert>
  );
};
