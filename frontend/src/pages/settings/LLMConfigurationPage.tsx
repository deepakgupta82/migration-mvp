/**
 * LLM Configuration Page - Full page for LLM settings management
 */

import React from 'react';
import { IconRobot } from '@tabler/icons-react';
import { SettingsPageLayout } from '../../components/layout/SettingsPageLayout';
import { LLMConfigurationPanel } from '../../components/settings/LLMConfigurationPanel';

export const LLMConfigurationPage: React.FC = () => {
  return (
    <SettingsPageLayout
      title="LLM Configuration"
      description="Configure Large Language Model providers, API keys, and settings for AI-powered features."
      icon={<IconRobot size="1.5rem" />}
      breadcrumbText="LLM Configuration"
    >
      <LLMConfigurationPanel />
    </SettingsPageLayout>
  );
};
