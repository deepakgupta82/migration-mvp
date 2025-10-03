/**
 * LLM Page - Consolidated page with tabs for Configuration and Usage
 * Combines LLM configuration management with project-level usage tracking
 */

import React, { useState } from 'react';
import { Tabs } from '@mantine/core';
import { IconRobot, IconActivity, IconSettings } from '@tabler/icons-react';
import { SettingsPageLayout } from '../../components/layout/SettingsPageLayout';
import { LLMConfigTab } from './LLMConfigTab';
import { LLMUsageTab } from './LLMUsageTab';

export const LLMPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string | null>('config');

  return (
    <SettingsPageLayout
      title="LLM Management"
      description="Configure Large Language Models and track usage across projects."
      icon={<IconRobot size="1.5rem" />}
      breadcrumbText="LLM"
    >
      <Tabs value={activeTab} onChange={setActiveTab} variant="default">
        <Tabs.List>
          <Tabs.Tab 
            value="config" 
            leftSection={<IconSettings size={16} />}
          >
            Configuration
          </Tabs.Tab>
          <Tabs.Tab 
            value="usage" 
            leftSection={<IconActivity size={16} />}
          >
            Usage & Costs
          </Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="config" pt="md">
          <LLMConfigTab />
        </Tabs.Panel>

        <Tabs.Panel value="usage" pt="md">
          <LLMUsageTab />
        </Tabs.Panel>
      </Tabs>
    </SettingsPageLayout>
  );
};

export default LLMPage;
