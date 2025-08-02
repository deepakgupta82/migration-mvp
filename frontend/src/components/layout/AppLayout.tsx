/**
 * Modern Application Layout with proper sidebar and content area
 * Follows modern UI principles with left sidebar navigation and right content area
 */

import React, { useState } from 'react';
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
  Tooltip,
} from '@mantine/core';
import { ServiceHealthBanner } from '../ServiceHealthBanner';
import {
  IconDashboard,
  IconFolder,
  IconSettings,
  IconLogout,
  IconUser,
  IconBell,
  IconChevronDown,
  IconFileText,
  IconMenu2,
  IconChevronLeft,
} from '@tabler/icons-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { NotificationDropdown } from '../notifications/NotificationDropdown';
import GlobalLogPane from '../logs/GlobalLogPane';
import FloatingChatWidget from '../FloatingChatWidget';

interface AppLayoutProps {
  children: React.ReactNode;
}

export const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const [logPaneOpen, setLogPaneOpen] = useState(false);
  const [navCollapsed, setNavCollapsed] = useState(false);

  // Extract project ID from URL if we're in a project context
  const projectId = location.pathname.match(/\/projects\/([^/]+)/)?.[1];

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
        width: navCollapsed ? 72 : 210,
        breakpoint: 'sm',
      }}
      header={{ height: 63 }}
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
        <Group h="100%" pl={navCollapsed ? "sm" : "md"} pr="xxl" justify="space-between">
          {/* Logo and App Name - Left */}
          <Group gap={0}>
            <img
              src="/dark-nagarrologo.svg"
              alt="Nagarro Logo"
              style={{
                height: '24px',
                width: 'auto',
              }}
            />
            <Text size="md" fw={700} c="dark.8">
              Nagarro's Ascent
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
        <Stack gap="lg" h="100%" p={navCollapsed ? "xs" : "md"}>
          {/* Navigation Section */}
          <Box>
            {!navCollapsed && (
              <Group justify="space-between" mb="md">
                <Text size="xs" fw={600} tt="uppercase" c="dimmed">
                  Navigation
                </Text>
                <ActionIcon
                  variant="subtle"
                  size="sm"
                  onClick={() => setNavCollapsed(!navCollapsed)}
                  title="Collapse Navigation"
                >
                  <IconChevronLeft size={16} />
                </ActionIcon>
              </Group>
            )}
            {navCollapsed && (
              <Group justify="center" mb="md">
                <ActionIcon
                  variant="subtle"
                  size="sm"
                  onClick={() => setNavCollapsed(!navCollapsed)}
                  title="Expand Navigation"
                >
                  <IconMenu2 size={16} />
                </ActionIcon>
              </Group>
            )}
            <Stack gap={4}>
              {navigationItems.map((item) => (
                navCollapsed ? (
                  <Tooltip key={item.path} label={item.label} position="right">
                    <ActionIcon
                      size="lg"
                      variant={item.active ? "filled" : "subtle"}
                      color={item.active ? "blue" : "gray"}
                      onClick={() => navigate(item.path)}
                      style={{ width: '100%', height: '40px' }}
                    >
                      <item.icon size={18} stroke={1.5} />
                    </ActionIcon>
                  </Tooltip>
                ) : (
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
                )
              ))}
            </Stack>
          </Box>

          {/* Spacer */}
          <Box style={{ flex: 1 }} />

          {/* Footer */}
          {!navCollapsed && (
            <Box>
              <Divider mb="sm" />
              <Text size="xs" c="dimmed" ta="center">
                © 2024 Nagarro
              </Text>
            </Box>
          )}
        </Stack>
      </AppShell.Navbar>

      {/* Main Content Area - Right Side */}
      <AppShell.Main>
        {/* Service Health Banner */}
        <ServiceHealthBanner />

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
            {location.pathname === '/settings/agents' && 'AI Agent Management'}
          </Title>
        </Box>

        {/* Main Content with ScrollArea - Reduced padding and right margin for panels */}
        <ScrollArea
          h="calc(100vh - var(--app-shell-header-height, 70px) - 50px)"
          p="md"
          type="auto"
          style={{
            marginRight: '60px', // Prevent text from going behind right panels
            paddingRight: '24px' // Ensure proper text alignment
          }}
        >
          <div style={{
            maxWidth: 'calc(100% - 60px)', // Ensure content doesn't overflow
            marginLeft: '0px', // Align content properly
            paddingLeft: '0px' // Remove any left padding that might cause cutoff
          }}>
            {children}
          </div>
        </ScrollArea>
      </AppShell.Main>

      {/* Global Log Pane */}
      <GlobalLogPane
        isOpen={logPaneOpen}
        onToggle={() => setLogPaneOpen(!logPaneOpen)}
      />

      {/* Floating Chat Widget - only show when in project context */}
      {projectId && (
        <FloatingChatWidget projectId={projectId} />
      )}
    </AppShell>
  );
};
