import React from 'react';
import { Alert } from '@mantine/core';
import { IconCheck, IconExclamationMark } from '@tabler/icons-react';

export const ServiceHealthBanner: React.FC = () => {
  const isHealthy = true; // Placeholder

  if (isHealthy) {
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

  return (
    <Alert
      icon={<IconExclamationMark size={18} />}
      color="orange"
      style={{ padding: '8px 16px', fontSize: '14px' }}
    >
      Some services are experiencing issues. Performance may be degraded.
    </Alert>
  );
};
