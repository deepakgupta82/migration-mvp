/**
 * AI Agents Page - Full page for AI agents settings
 */

import React from 'react';
import { IconBrain } from '@tabler/icons-react';
import { SettingsPageLayout } from '../../components/layout/SettingsPageLayout';
import AIAgentsPanel from '../../components/settings/AIAgentsPanel';

export const AIAgentsPage: React.FC = () => {
  return (
    <SettingsPageLayout
      title="AI Agents"
      description="Configure and manage AI agents, their roles, and capabilities within the platform."
      icon={<IconBrain size="1.5rem" />}
      breadcrumbText="AI Agents"
    >
      <AIAgentsPanel />
    </SettingsPageLayout>
  );
};
