/**
 * Main Application Layout with Mantine AppShell
 * Provides persistent navigation and header
 */

import React from 'react';
import {
  AppShell,
  Text,
  NavLink,
  Group,
  ActionIcon,
  Avatar,
  Menu,
  Divider,
  Badge,
} from '@mantine/core';
import {
  IconDashboard,
  IconFolder,
  IconSettings,
  IconLogout,
  IconUser,
  IconBell,
} from '@tabler/icons-react';
import { useLocation, useNavigate } from 'react-router-dom';

interface AppLayoutProps {
  children: React.ReactNode;
}

export const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();

  const navigationItems = [
    {
      icon: IconDashboard,
      label: 'Dashboard',
      path: '/',
      active: location.pathname === '/',
    },
    {
      icon: IconFolder,
      label: 'Projects',
      path: '/projects',
      active: location.pathname.startsWith('/projects'),
    },
    {
      icon: IconSettings,
      label: 'Settings',
      path: '/settings',
      active: location.pathname === '/settings',
    },
  ];

  return (
    <AppShell
      padding="md"
      navbar={{ width: { base: 280 }, breakpoint: 'sm' }}
    >
      <AppShell.Navbar p="xs">
          {/* Logo Section */}
          <AppShell.Section mb="md">
            <Group gap="xs" p="md">
              <div
                style={{
                  width: 40,
                  height: 40,
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  borderRadius: '12px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'white',
                  fontWeight: 'bold',
                  fontSize: '18px',
                  boxShadow: '0 4px 12px rgba(102, 126, 234, 0.4)',
                }}
              >
                A
              </div>
              <div>
                <Text size="lg" fw={600} c="dark">
                  AgentiMigrate
                </Text>
                <Text size="xs" c="dimmed">
                  Cloud Migration Platform
                </Text>
              </div>
            </Group>
          </AppShell.Section>

          <Divider mb="md" />

          {/* Navigation Links */}
          <AppShell.Section grow>
            {navigationItems.map((item) => (
              <NavLink
                key={item.path}
                leftSection={<item.icon size={20} />}
                label={item.label}
                active={item.active}
                onClick={() => navigate(item.path)}
                style={{
                  borderRadius: '8px',
                  margin: '4px 8px',
                }}
              />
            ))}
          </AppShell.Section>

          {/* Footer Section */}
          <AppShell.Section>
            <Divider mb="md" />
            <Group p="md" gap="xs">
              <Avatar size="sm" color="blue">
                <IconUser size={16} />
              </Avatar>
              <div style={{ flex: 1 }}>
                <Text size="sm" fw={500}>
                  Admin User
                </Text>
                <Text size="xs" c="dimmed">
                  admin@nagarro.com
                </Text>
              </div>
            </Group>
          </AppShell.Section>
      </AppShell.Navbar>

      <AppShell.Header h={70} p="md">
          <Group justify="space-between" style={{ height: '100%' }}>
            {/* Page Title */}
            <Group gap="md">
              <Text size="xl" fw={600} c="dark">
                {location.pathname === '/' && 'Dashboard'}
                {location.pathname.startsWith('/projects') && !location.pathname.includes('/projects/') && 'Projects'}
                {location.pathname.includes('/projects/') && 'Project Details'}
                {location.pathname === '/settings' && 'Settings'}
              </Text>
            </Group>

            {/* Header Actions */}
            <Group gap="md">
              {/* Notifications */}
              <ActionIcon size="lg" variant="subtle" color="gray">
                <IconBell size={20} />
              </ActionIcon>

              {/* User Menu */}
              <Menu shadow="md" width={200}>
                <Menu.Target>
                  <ActionIcon size="lg" variant="subtle" color="gray">
                    <Avatar size="sm" color="blue">
                      <IconUser size={16} />
                    </Avatar>
                  </ActionIcon>
                </Menu.Target>

                <Menu.Dropdown>
                  <Menu.Label>Account</Menu.Label>
                  <Menu.Item leftSection={<IconUser size={14} />}>Profile</Menu.Item>
                  <Menu.Item leftSection={<IconSettings size={14} />}>Settings</Menu.Item>
                  <Menu.Divider />
                  <Menu.Item leftSection={<IconLogout size={14} />} c="red">
                    Logout
                  </Menu.Item>
                </Menu.Dropdown>
              </Menu>
            </Group>
          </Group>
      </AppShell.Header>

      <AppShell.Main
        style={{
          background: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)',
          minHeight: 'calc(100vh - 70px)',
          padding: '24px',
        }}
      >
        {children}
      </AppShell.Main>
    </AppShell>
  );
};
