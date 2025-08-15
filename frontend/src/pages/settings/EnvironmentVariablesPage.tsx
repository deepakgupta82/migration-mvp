/**
 * Environment Variables Page - Full page for environment settings
 */

import React from 'react';
import { IconSettings } from '@tabler/icons-react';
import { SettingsPageLayout } from '../../components/layout/SettingsPageLayout';
import EnvironmentVariablesPanel from '../../components/settings/EnvironmentVariablesPanel';

export const EnvironmentVariablesPage: React.FC = () => {
  return (
    <SettingsPageLayout
      title="Environment Variables"
      description="Manage environment variables, API keys, and configuration settings for the platform."
      icon={<IconSettings size="1.5rem" />}
      breadcrumbText="Environment Variables"
    >
      <EnvironmentVariablesPanel />
    </SettingsPageLayout>
  );
};
