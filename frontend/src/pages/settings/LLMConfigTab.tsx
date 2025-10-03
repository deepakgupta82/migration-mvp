/**
 * LLM Configuration Tab - Configuration management for LLM providers
 */

import React, { useState } from 'react';
import { Button, Stack } from '@mantine/core';
import { IconPlus } from '@tabler/icons-react';
import { LLMConfigurationPanel } from '../../components/settings/LLMConfigurationPanel';

export const LLMConfigTab: React.FC = () => {
  const [showAddForm, setShowAddForm] = useState(false);

  return (
    <Stack gap="md">
      <Button
        leftSection={<IconPlus size={16} />}
        size="sm"
        style={{ height: '32px', alignSelf: 'flex-start' }}
        onClick={() => setShowAddForm(true)}
      >
        Create LLM Configuration
      </Button>
      <LLMConfigurationPanel showAddForm={showAddForm} setShowAddForm={setShowAddForm} />
    </Stack>
  );
};

export default LLMConfigTab;

