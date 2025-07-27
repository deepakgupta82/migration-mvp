/**
 * Modern Application Layout with proper sidebar and content area
 * Follows modern UI principles with left sidebar navigation and right content area
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
  Title,
  Stack,
  UnstyledButton,
  Box,
  ScrollArea,
} from '@mantine/core';
import {
  IconDashboard,
  IconFolder,
  IconSettings,
  IconLogout,
  IconUser,
  IconBell,
  IconChevronDown,
  IconFileText,
} from '@tabler/icons-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { NotificationDropdown } from '../notifications/NotificationDropdown';

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
      icon: IconFileText,
      label: 'Logs',
      path: '/logs',
      active: location.pathname === '/logs',
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
      navbar={{
        width: 260,
        breakpoint: 'sm',
      }}
      header={{ height: 70 }}
      styles={{
        main: {
          backgroundColor: '#fafafa',
        },
        navbar: {
          backgroundColor: 'white',
          borderRight: '1px solid #e1e5e9',
          boxShadow: '1px 0 3px rgba(0, 0, 0, 0.05)',
        },
        header: {
          backgroundColor: 'white',
          borderBottom: '1px solid #e1e5e9',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
        },
      }}
    >
      {/* Professional SharePoint-like Header */}
      <AppShell.Header>
        <Group h="100%" px="xl" justify="space-between">
          {/* Logo and App Name - Left */}
          <Group gap="md">
            <Box
              style={{
                background: '#0072c6',
                borderRadius: '8px',
                padding: '8px 10px',
                color: 'white',
                fontWeight: 700,
                fontSize: '14px',
                boxShadow: '0 2px 8px rgba(0, 114, 198, 0.3)',
              }}
            >
              NA
            </Box>
            <Text size="lg" fw={700} c="dark.8">
              Nagarro Ascent
            </Text>
          </Group>

          {/* User Actions - Top Right Only */}
          <Group gap="sm">
            <NotificationDropdown />

            <Menu shadow="md" width={200} position="bottom-end">
              <Menu.Target>
                <UnstyledButton
                  p="sm"
                  style={{
                    borderRadius: '6px',
                    transition: 'all 0.15s ease',
                    '&:hover': {
                      backgroundColor: '#f5f5f5',
                    },
                  }}
                >
                  <Group gap="sm">
                    <Avatar
                      size={32}
                      radius="md"
                      style={{
                        background: '#0072c6',
                      }}
                    >
                      <IconUser size={16} />
                    </Avatar>
                    <Stack gap={0}>
                      <Text size="sm" fw={600} c="dark.8">
                        Admin User
                      </Text>
                      <Text size="xs" c="dimmed">
                        admin@nagarro.com
                      </Text>
                    </Stack>
                    <IconChevronDown size={14} stroke={1.5} />
                  </Group>
                </UnstyledButton>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Item leftSection={<IconUser size={16} />}>
                  Profile Settings
                </Menu.Item>
                <Menu.Item leftSection={<IconSettings size={16} />}>
                  Preferences
                </Menu.Item>
                <Menu.Divider />
                <Menu.Item
                  leftSection={<IconLogout size={16} />}
                  color="red"
                  onClick={() => navigate('/login')}
                >
                  Sign Out
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          </Group>
        </Group>
      </AppShell.Header>

      {/* Professional SharePoint-like Sidebar */}
      <AppShell.Navbar>
        <Stack gap="lg" h="100%" p="md">
          {/* Navigation Section */}
          <Box>
            <Text size="xs" fw={600} tt="uppercase" c="dimmed" mb="md">
              Navigation
            </Text>
            <Stack gap={4}>
              {navigationItems.map((item) => (
                <NavLink
                  key={item.path}
                  leftSection={
                    <Box style={{ display: 'flex', alignItems: 'center', width: 20 }}>
                      <item.icon size={18} stroke={1.5} />
                    </Box>
                  }
                  label={item.label}
                  active={item.active}
                  onClick={() => navigate(item.path)}
                />
              ))}
            </Stack>
          </Box>

          {/* Spacer */}
          <Box style={{ flex: 1 }} />

          {/* Footer */}
          <Box>
            <Divider mb="sm" />
            <Text size="xs" c="dimmed" ta="center">
              © 2024 Nagarro
            </Text>
          </Box>
        </Stack>
      </AppShell.Navbar>

      {/* Main Content Area - Right Side */}
      <AppShell.Main>
        {/* Page Title Section - Compact */}
        <Box
          style={{
            backgroundColor: '#fafafa',
            borderBottom: '1px solid #e1e5e9',
            padding: '12px 24px',
          }}
        >
          <Title order={2} fw={600} c="dark.8" size="h4">
            {location.pathname === '/' && 'Dashboard'}
            {location.pathname === '/projects' && 'All Projects'}
            {location.pathname.includes('/projects/') && 'Project Details'}
            {location.pathname === '/logs' && 'System Logs'}
            {location.pathname === '/settings' && 'Settings'}
          </Title>
        </Box>

        {/* Main Content with ScrollArea - Reduced padding */}
        <ScrollArea h="calc(100vh - var(--app-shell-header-height, 70px) - 50px)" p="md" type="auto">
          {children}
        </ScrollArea>
      </AppShell.Main>
    </AppShell>
  );
};
