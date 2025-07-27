/**
 * Notification Dropdown Component
 * Shows all notifications with filtering and actions
 */

import React, { useState } from 'react';
import {
  Menu,
  ActionIcon,
  Badge,
  Text,
  Group,
  Stack,
  ScrollArea,
  Button,
  Divider,
  Paper,
  Box,
  Select,
  UnstyledButton,
} from '@mantine/core';
import {
  IconBell,
  IconBellRinging,
  IconCheck,
  IconTrash,
  IconX,
  IconFileUpload,
  IconAlertTriangle,
  IconCircleCheck,
  IconInfoCircle,
} from '@tabler/icons-react';
import { useNotifications, AppNotification } from '../../contexts/NotificationContext';

export const NotificationDropdown: React.FC = () => {
  const {
    notifications,
    unreadCount,
    markAsRead,
    markAllAsRead,
    clearNotification,
    clearAllNotifications,
  } = useNotifications();

  const [filterType, setFilterType] = useState<string>('all');

  const getNotificationIcon = (type: AppNotification['type']) => {
    switch (type) {
      case 'success':
        return <IconCircleCheck size={16} color="#51cf66" />;
      case 'error':
        return <IconAlertTriangle size={16} color="#ff6b6b" />;
      case 'warning':
        return <IconAlertTriangle size={16} color="#ffd43b" />;
      case 'info':
      default:
        return <IconInfoCircle size={16} color="#339af0" />;
    }
  };

  const getNotificationColor = (type: AppNotification['type']) => {
    switch (type) {
      case 'success':
        return '#e7f5ff';
      case 'error':
        return '#ffe0e0';
      case 'warning':
        return '#fff3cd';
      case 'info':
      default:
        return '#e7f5ff';
    }
  };

  const filteredNotifications = notifications.filter(notification => {
    if (filterType === 'all') return true;
    if (filterType === 'unread') return !notification.read;
    return notification.type === filterType;
  });

  const formatTimeAgo = (timestamp: Date) => {
    const now = new Date();
    const diffInMinutes = Math.floor((now.getTime() - timestamp.getTime()) / (1000 * 60));

    if (diffInMinutes < 1) return 'Just now';
    if (diffInMinutes < 60) return `${diffInMinutes}m ago`;

    const diffInHours = Math.floor(diffInMinutes / 60);
    if (diffInHours < 24) return `${diffInHours}h ago`;

    const diffInDays = Math.floor(diffInHours / 24);
    return `${diffInDays}d ago`;
  };

  return (
    <Menu shadow="md" width={400} position="bottom-end">
      <Menu.Target>
        <ActionIcon variant="subtle" size="lg" style={{ position: 'relative' }}>
          {unreadCount > 0 ? (
            <IconBellRinging size={20} color="#0072c6" />
          ) : (
            <IconBell size={20} />
          )}
          {unreadCount > 0 && (
            <Badge
              size="xs"
              variant="filled"
              color="red"
              style={{
                position: 'absolute',
                top: -2,
                right: -2,
                minWidth: 16,
                height: 16,
                padding: 0,
                fontSize: 10,
              }}
            >
              {unreadCount > 99 ? '99+' : unreadCount}
            </Badge>
          )}
        </ActionIcon>
      </Menu.Target>

      <Menu.Dropdown p={0}>
        <Box p="md" style={{ borderBottom: '1px solid #e9ecef' }}>
          <Group justify="space-between" mb="sm">
            <Text fw={600} size="sm">
              Notifications
            </Text>
            {unreadCount > 0 && (
              <Badge size="sm" variant="light" color="blue">
                {unreadCount} new
              </Badge>
            )}
          </Group>

          <Group gap="xs">
            <Select
              size="xs"
              value={filterType}
              onChange={(value) => setFilterType(value || 'all')}
              data={[
                { value: 'all', label: 'All' },
                { value: 'unread', label: 'Unread' },
                { value: 'success', label: 'Success' },
                { value: 'error', label: 'Errors' },
                { value: 'warning', label: 'Warnings' },
                { value: 'info', label: 'Info' },
              ]}
              style={{ flex: 1 }}
            />
            {unreadCount > 0 && (
              <Button size="xs" variant="subtle" onClick={markAllAsRead}>
                Mark all read
              </Button>
            )}
          </Group>
        </Box>

        <ScrollArea h={400}>
          {filteredNotifications.length === 0 ? (
            <Box p="xl" style={{ textAlign: 'center' }}>
              <IconBell size={32} color="#868e96" style={{ marginBottom: 8 }} />
              <Text size="sm" c="dimmed">
                {filterType === 'unread' ? 'No unread notifications' : 'No notifications yet'}
              </Text>
            </Box>
          ) : (
            <Stack gap={0}>
              {filteredNotifications.map((notification) => (
                <UnstyledButton
                  key={notification.id}
                  onClick={() => !notification.read && markAsRead(notification.id)}
                  style={{
                    width: '100%',
                    padding: 0,
                  }}
                >
                  <Paper
                    p="md"
                    style={{
                      backgroundColor: notification.read ? '#ffffff' : getNotificationColor(notification.type),
                      borderBottom: '1px solid #f1f3f4',
                      borderRadius: 0,
                      transition: 'background-color 0.2s ease',
                      cursor: 'pointer',
                    }}
                  >
                    <Group align="flex-start" gap="sm">
                      <Box mt={2}>
                        {getNotificationIcon(notification.type)}
                      </Box>

                      <Box style={{ flex: 1, minWidth: 0 }}>
                        <Group justify="space-between" align="flex-start" mb={4}>
                          <Text fw={notification.read ? 400 : 600} size="sm" style={{ flex: 1 }}>
                            {notification.title}
                          </Text>
                          <ActionIcon
                            size="xs"
                            variant="subtle"
                            color="gray"
                            onClick={(e) => {
                              e.stopPropagation();
                              clearNotification(notification.id);
                            }}
                          >
                            <IconX size={12} />
                          </ActionIcon>
                        </Group>

                        <Text size="xs" c="dimmed" mb={6} style={{ lineHeight: 1.4 }}>
                          {notification.message}
                        </Text>

                        <Group justify="space-between" align="center">
                          <Text size="xs" c="dimmed">
                            {formatTimeAgo(notification.timestamp)}
                          </Text>
                          {notification.projectName && (
                            <Badge size="xs" variant="light" color="gray">
                              {notification.projectName}
                            </Badge>
                          )}
                        </Group>
                      </Box>
                    </Group>
                  </Paper>
                </UnstyledButton>
              ))}
            </Stack>
          )}
        </ScrollArea>

        {notifications.length > 0 && (
          <>
            <Divider />
            <Box p="sm">
              <Button
                variant="subtle"
                size="xs"
                fullWidth
                leftSection={<IconTrash size={14} />}
                onClick={clearAllNotifications}
                color="red"
              >
                Clear all notifications
              </Button>
            </Box>
          </>
        )}
      </Menu.Dropdown>
    </Menu>
  );
};

export default NotificationDropdown;
