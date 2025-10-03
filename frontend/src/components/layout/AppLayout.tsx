
/**
 * Modern Application Layout with proper sidebar and content area
 *     {
      label: 'LLM',
      path: '/settings/llm-configuration',
      icon: IconRobot,
    },ws modern UI principles with left sidebar navigation and right content area
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
  Collapse,
} from '@mantine/core';
import { ServiceHealthBanner } from '../ServiceHealthBanner';
import { CriticalSystemBanner } from '../CriticalSystemBanner';
import { NotificationDropdown } from '../notifications/NotificationDropdown';
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
  IconTerminal,
  IconChevronRight,
  IconBrain,
  IconShield,
  IconKey,
  IconUsers,
  IconDatabase,
  IconRobot,
  IconBrandOauth,
  IconMessage,
  IconServer,
  IconBulb,
  IconCash,
} from '@tabler/icons-react';
import { useLocation, useNavigate } from 'react-router-dom';
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
  const [settingsOpened, setSettingsOpened] = useState(
    location.pathname.startsWith('/settings')
  );
  const [systemOpened, setSystemOpened] = useState(
    location.pathname.startsWith('/system') || location.pathname === '/system-logs'
  );

  // Settings sub-items configuration
  const settingsSubItems = [
    { 
      label: 'LLM Configuration', 
      path: '/settings/llm-configuration',
      icon: IconRobot
    },
    {
      label: 'LLM Prompts',
      path: '/settings/llm-prompts',
      icon: IconMessage
    },
    { 
      label: 'OAuth & Authentication', 
      path: '/settings/oauth-authentication',
      icon: IconBrandOauth
    },
    { 
      label: 'User Management', 
      path: '/settings/user-management',
      icon: IconUsers
    },
  // Removed Knowledge Base from left menu per request
    { 
      label: 'Environment Variables', 
      path: '/settings/environment-variables',
      icon: IconSettings
    },
  // Removed Platform Services from left menu per request
    { 
      label: 'AI Agents', 
      path: '/settings/ai-agents',
      icon: IconBrain
    },
    { 
      label: 'Model Manager', 
      path: '/settings/model-manager',
      icon: IconServer
    },
    { 
      label: 'Global Document Templates', 
      path: '/settings/global-templates',
      icon: IconFileText
    },
    {
      label: 'Chunking & Embedding',
      path: '/settings/chunking-embedding',
      icon: IconDatabase
    },
    {
      label: 'Lessons Learned',
      path: '/settings/lessons-learned',
      icon: IconBulb
    },
    {
      label: 'Usage & Costs',
      path: '/settings/usage-costs',
      icon: IconCash
    },
    {
      label: 'MCP Servers',
      path: '/settings/mcp-servers',
      icon: IconServer
    }
  ];


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
  // System is handled as a tree below (like Settings)
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
        <Group h="100%" pl={navCollapsed ? "sm" : "md"} pr="xxl" justify="space-between" style={{ position: 'relative' }}>
          {/* Service Health Banner - Topmost inside header, only until navigation */}
    {/* Removed topmost ServiceHealthBanner as requested. */}
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
            <Stack gap={2}>
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

              {/* System with expandable sub-menu (trimmed to Overview, Logs, Containers) */}
              {!navCollapsed && (
                <NavLink
                  leftSection={
                    <Box style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <IconTerminal size={18} stroke={1.5} />
                    </Box>
                  }
                  label="System"
                  active={location.pathname === '/system-logs' && !systemOpened}
                  opened={systemOpened}
                  onChange={setSystemOpened}
                  childrenOffset={20}
                  style={{
                    marginBottom: '4px'
                  }}
                >
                  <Stack gap={1}>
                    {[
                      { label: 'Overview', tab: 'overview' },
                      { label: 'Logs', tab: 'logs' },
                    ].map((subItem) => (
                      <NavLink
                        key={subItem.tab}
                        leftSection={
                          <Box style={{ display: 'flex', alignItems: 'center', width: 14, flexShrink: 0 }}>
                            {/* Removed chevron icon as requested */}
                          </Box>
                        }
                        label={
                          <Text size="xs" style={{ lineHeight: '1.2', whiteSpace: 'nowrap' }}>
                            {subItem.label}
                          </Text>
                        }
                        active={location.pathname === '/system-logs' && window.location.hash === `#${subItem.tab}`}
                        onClick={() => {
                          navigate('/system-logs');
                          // Update hash to control tab selection
                          window.location.hash = `#${subItem.tab}`;
                        }}
                        style={{
                          fontSize: '11px',
                          minHeight: '28px',
                          padding: '4px 8px',
                          marginBottom: '2px'
                        }}
                      />
                    ))}
                  </Stack>
                </NavLink>
              )}

              {/* Collapsed system icon */}
              {navCollapsed && (
                <Tooltip label="System" position="right">
                  <ActionIcon
                    size="lg"
                    variant={location.pathname === '/system-logs' ? "filled" : "subtle"}
                    color={location.pathname === '/system-logs' ? "blue" : "gray"}
                    onClick={() => navigate('/system-logs')}
                    style={{ width: '100%', height: '40px' }}
                  >
                    <IconTerminal size={18} stroke={1.5} />
                  </ActionIcon>
                </Tooltip>
              )}

              {/* Settings with expandable sub-menu */}
              {!navCollapsed && (
                <NavLink
                  leftSection={
                    <Box style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <IconSettings size={18} stroke={1.5} />
                    </Box>
                  }
                  label="Settings"
                  active={location.pathname.startsWith('/settings') && !settingsOpened}
                  opened={settingsOpened}
                  onChange={setSettingsOpened}
                  childrenOffset={20}
                  style={{
                    marginBottom: '4px'
                  }}
                >
                  <Stack gap={1}>
                    {settingsSubItems.map((subItem) => (
                      <NavLink
                        key={subItem.path}
                        leftSection={
                          <Box style={{ display: 'flex', alignItems: 'center', width: 14, flexShrink: 0 }}>
                            <subItem.icon size={12} stroke={1.5} />
                          </Box>
                        }
                        label={
                          <Text size="xs" style={{ lineHeight: '1.2', whiteSpace: 'nowrap' }}>
                            {subItem.label}
                          </Text>
                        }
                        active={location.pathname === subItem.path}
                        onClick={() => navigate(subItem.path)}
                        style={{
                          fontSize: '11px',
                          minHeight: '28px',
                          padding: '4px 8px',
                          marginBottom: '2px'
                        }}
                      />
                    ))}
                  </Stack>
                </NavLink>
              )}

              {/* Collapsed settings icon */}
              {navCollapsed && (
                <Tooltip label="Settings" position="right">
                  <ActionIcon
                    size="lg"
                    variant={location.pathname.startsWith('/settings') ? "filled" : "subtle"}
                    color={location.pathname.startsWith('/settings') ? "blue" : "gray"}
                    onClick={() => navigate('/settings/llm-configuration')}
                    style={{ width: '100%', height: '40px' }}
                  >
                    <IconSettings size={18} stroke={1.5} />
                  </ActionIcon>
                </Tooltip>
              )}
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
        {/* Critical System Banner - Top Priority */}
  {/* Removed CriticalSystemBanner as requested. */}
  <ServiceHealthBanner />


    {/* Page Title Section - Extra compact per spacing request */}
        {!location.pathname.startsWith('/settings') && (
          <Box
            style={{
              backgroundColor: '#fafafa',
              borderBottom: '1px solid #e1e5e9',
      padding: '8px 18px',
            }}
          >
            <Title order={2} fw={600} c="dark.8" size="h4">
              {location.pathname === '/' && 'Dashboard'}
              {location.pathname === '/projects' && 'All Projects'}
              {location.pathname.includes('/projects/') && 'Project Details'}
              {location.pathname === '/logs' && 'System Logs'}
              {location.pathname === '/settings/agents' && 'AI Agent Management'}
            </Title>
          </Box>
        )}

        {/* Main Content with ScrollArea - Optimized for settings pages */}
    <ScrollArea
          h={location.pathname.startsWith('/settings')
            ? "calc(100vh - var(--app-shell-header-height, 70px) - 20px)"
            : "calc(100vh - var(--app-shell-header-height, 70px) - 50px)"
          }
          p={location.pathname.startsWith('/settings') ? "sm" : "md"}
          type="auto"
          style={{
      marginRight: '20px',
      paddingRight: '12px'
          }}
        >
          <div style={{
      maxWidth: 'calc(100% - 20px)',
      marginLeft: location.pathname.startsWith('/settings') ? '6px' : '12px',
      paddingLeft: location.pathname.startsWith('/settings') ? '6px' : '12px',
      paddingRight: '12px',
      paddingTop: location.pathname.startsWith('/settings') ? '4px' : '0px'
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
