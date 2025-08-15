/**
 * Platform Services Page - Full page for service monitoring and management
 */

import React from 'react';
import { IconServer } from '@tabler/icons-react';
import { SettingsPageLayout } from '../../components/layout/SettingsPageLayout';
import { ServiceStatusPanel } from '../../components/settings/ServiceStatusPanel';

export const PlatformServicesPage: React.FC = () => {
  return (
    <SettingsPageLayout
      title="Platform Services"
      description="Monitor and manage all platform services including backend APIs, databases, and infrastructure components."
      icon={<IconServer size="1.5rem" />}
      breadcrumbText="Platform Services"
    >
      <ServiceStatusPanel />
    </SettingsPageLayout>
  );
};
