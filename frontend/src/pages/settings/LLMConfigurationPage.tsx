/**
 * LLM Configuration Page - Full page for LLM settings management
 */

import React, { useState } from 'react';
import { Button } from '@mantine/core';
import { IconRobot, IconPlus } from '@tabler/icons-react';
import { SettingsPageLayout } from '../../components/layout/SettingsPageLayout';
import { LLMConfigurationPanel } from '../../components/settings/LLMConfigurationPanel';

export const LLMConfigurationPage: React.FC = () => {
  const [showAddForm, setShowAddForm] = useState(false);

  return (
    <SettingsPageLayout
      title="LLM Configuration"
      description="Configure Large Language Model providers, API keys, and settings for AI-powered features."
      icon={<IconRobot size="1.5rem" />}
      breadcrumbText="LLM Configuration"
      actions={
        <Button
          leftSection={<IconPlus size={16} />}
          size="sm"
          style={{ height: '32px' }} // Reduced by 10%
          onClick={() => setShowAddForm(true)}
        >
          Create LLM Configuration
        </Button>
      }
    >
      <LLMConfigurationPanel showAddForm={showAddForm} setShowAddForm={setShowAddForm} />
    </SettingsPageLayout>
  );
};
