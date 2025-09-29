/**
 * LLM Prompts Page - Full page wrapper for Prompt Management Panel
 */

import React from 'react';
import { IconMessage } from '@tabler/icons-react';
import { SettingsPageLayout } from '../../components/layout/SettingsPageLayout';
import PromptManagementPanel from '../../components/settings/PromptManagementPanel';

export const LLMPromptsPage: React.FC = () => {
  return (
    <SettingsPageLayout
      title="LLM Prompts"
      description="View and edit prompt templates used by backend services. Changes persist to JSON in the repo and services hot-reload on save."
      icon={<IconMessage size="1.5rem" />}
      breadcrumbText="LLM Prompts"
    >
      <PromptManagementPanel />
    </SettingsPageLayout>
  );
};

export default LLMPromptsPage;
