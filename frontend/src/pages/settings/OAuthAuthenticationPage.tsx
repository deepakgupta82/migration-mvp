/**
 * OAuth & Authentication Page - Full page for OAuth settings
 */

import React, { useState } from 'react';
import {
  Stack,
  Button,
  Group,
  Card,
  Text,
  Badge,
  Switch,
  Divider,
  Alert,
  TextInput,
  PasswordInput,
  Table,
} from '@mantine/core';
import {
  IconShield,
  IconBrandGoogle,
  IconBrandAzure,
  IconBrandGithub,
  IconAlertCircle,
  IconCheck,
  IconPlus,
} from '@tabler/icons-react';

import { SettingsPageLayout } from '../../components/layout/SettingsPageLayout';

export const OAuthAuthenticationPage: React.FC = () => {
  const [providers, setProviders] = useState([
    { id: 'google', name: 'Google', enabled: true, icon: IconBrandGoogle, configured: true },
    { id: 'azure', name: 'Microsoft Azure', enabled: false, icon: IconBrandAzure, configured: false },
    { id: 'github', name: 'GitHub', enabled: true, icon: IconBrandGithub, configured: true }
  ]);

  const toggleProvider = (id: string) => {
    setProviders(providers.map(p => 
      p.id === id ? { ...p, enabled: !p.enabled } : p
    ));
  };

  return (
    <SettingsPageLayout
      title="OAuth & Authentication"
      description="Configure OAuth providers, authentication methods, and security settings for user access control and single sign-on capabilities."
      icon={<IconShield size="1.5rem" />}
      breadcrumbText="OAuth & Authentication"
    >
      <Stack gap="xl">
        {/* Security Notice */}
        <Alert icon={<IconAlertCircle size="1rem" />} title="Security Notice" color="blue">
          Changes to authentication settings will affect all users. Ensure proper testing before applying changes to production.
        </Alert>

        {/* OAuth Providers */}
        <Stack gap="lg">
          <Text size="lg" fw={600}>OAuth Providers</Text>
          
          {providers.map((provider) => {
            const IconComponent = provider.icon;
            return (
              <Card key={provider.id} p="lg" radius="md" withBorder>
                <Group justify="space-between" align="center">
                  <Group gap="md">
                    <IconComponent size="2rem" />
                    <div>
                      <Text fw={500}>{provider.name}</Text>
                      <Group gap="xs">
                        <Badge color={provider.configured ? 'green' : 'gray'}>
                          {provider.configured ? 'Configured' : 'Not Configured'}
                        </Badge>
                        <Badge color={provider.enabled ? 'blue' : 'gray'}>
                          {provider.enabled ? 'Enabled' : 'Disabled'}
                        </Badge>
                      </Group>
                    </div>
                  </Group>
                  <Switch
                    checked={provider.enabled}
                    onChange={() => toggleProvider(provider.id)}
                    disabled={!provider.configured}
                  />
                </Group>
              </Card>
            );
          })}
        </Stack>

        {/* Authentication Settings */}
        <Stack gap="lg">
          <Text size="lg" fw={600}>Authentication Settings</Text>
          
          <Card p="lg" withBorder>
            <Stack gap="md">
              <Group justify="space-between">
                <div>
                  <Text fw={500}>Multi-Factor Authentication</Text>
                  <Text size="sm" c="dimmed">Require 2FA for all users</Text>
                </div>
                <Switch defaultChecked />
              </Group>
              
              <Divider />
              
              <Group justify="space-between">
                <div>
                  <Text fw={500}>Session Timeout</Text>
                  <Text size="sm" c="dimmed">Auto-logout after inactivity</Text>
                </div>
                <Switch defaultChecked />
              </Group>
              
              <Divider />
              
              <Group justify="space-between">
                <div>
                  <Text fw={500}>Password Complexity</Text>
                  <Text size="sm" c="dimmed">Enforce strong passwords</Text>
                </div>
                <Switch defaultChecked />
              </Group>
            </Stack>
          </Card>
        </Stack>
      </Stack>
    </SettingsPageLayout>
  );
};
