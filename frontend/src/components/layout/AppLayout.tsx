/**
 * Main Application Layout with Mantine AppShell
 * Provides persistent navigation and header
 */

import React from 'react';
import {
  AppShell,
  Navbar,
  Header,
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
      navbar={
        <Navbar width={{ base: 280 }} p="xs">
          {/* Logo Section */}
          <Navbar.Section mb="md">
            <Group spacing="xs" p="md">
              <div
                style={{
                  width: 40,
                  height: 40,
                  backgroundColor: '#1c7ed6',
                  borderRadius: '8px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'white',
                  fontWeight: 'bold',
                  fontSize: '18px',
                }}
              >
                N
              </div>
              <div>
                <Text size="lg" weight={600} color="dark">
                  AgentiMigrate
                </Text>
                <Text size="xs" color="dimmed">
                  Cloud Migration Platform
                </Text>
              </div>
            </Group>
          </Navbar.Section>

          <Divider mb="md" />

          {/* Navigation Links */}
          <Navbar.Section grow>
            {navigationItems.map((item) => (
              <NavLink
                key={item.path}
                icon={<item.icon size={20} />}
                label={item.label}
                active={item.active}
                onClick={() => navigate(item.path)}
                style={{
                  borderRadius: '8px',
                  margin: '4px 8px',
                }}
              />
            ))}
          </Navbar.Section>

          {/* Footer Section */}
          <Navbar.Section>
            <Divider mb="md" />
            <Group p="md" spacing="xs">
              <Avatar size="sm" color="blue">
                <IconUser size={16} />
              </Avatar>
              <div style={{ flex: 1 }}>
                <Text size="sm" weight={500}>
                  Admin User
                </Text>
                <Text size="xs" color="dimmed">
                  admin@nagarro.com
                </Text>
              </div>
            </Group>
          </Navbar.Section>
        </Navbar>
      }
      header={
        <Header height={70} p="md">
          <Group position="apart" style={{ height: '100%' }}>
            {/* Page Title */}
            <Group spacing="md">
              <Text size="xl" weight={600} color="dark">
                {location.pathname === '/' && 'Dashboard'}
                {location.pathname.startsWith('/projects') && !location.pathname.includes('/projects/') && 'Projects'}
                {location.pathname.includes('/projects/') && 'Project Details'}
                {location.pathname === '/settings' && 'Settings'}
              </Text>
            </Group>

            {/* Header Actions */}
            <Group spacing="md">
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
                  <Menu.Item icon={<IconUser size={14} />}>Profile</Menu.Item>
                  <Menu.Item icon={<IconSettings size={14} />}>Settings</Menu.Item>
                  <Menu.Divider />
                  <Menu.Item icon={<IconLogout size={14} />} color="red">
                    Logout
                  </Menu.Item>
                </Menu.Dropdown>
              </Menu>
            </Group>
          </Group>
        </Header>
      }
      styles={(theme) => ({
        main: {
          backgroundColor: theme.colors.gray[0],
          minHeight: 'calc(100vh - 70px)',
        },
      })}
    >
      {children}
    </AppShell>
  );
};
