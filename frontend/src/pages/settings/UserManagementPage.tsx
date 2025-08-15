/**
 * User Management Page - Full page for user management settings
 */

import React, { useState, useEffect } from 'react';
import {
  Stack,
  Button,
  Group,
  Card,
  Text,
  Badge,
  Table,
  ActionIcon,
  Modal,
  TextInput,
  Select,
  Switch,
  Avatar,
  Pagination,
  Alert,
} from '@mantine/core';
import {
  IconUsers,
  IconPlus,
  IconEdit,
  IconTrash,
  IconUserCheck,
  IconUserX,
  IconRefresh,
  IconAlertCircle,
} from '@tabler/icons-react';

import { SettingsPageLayout } from '../../components/layout/SettingsPageLayout';
import { notifications } from '@mantine/notifications';

interface User {
  id: string;
  username: string;
  email: string;
  role: string;
  status: string;
  created_at: string;
  lastLogin?: string;
}

export const UserManagementPage: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpened, setModalOpened] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [activePage, setActivePage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  // Mock data for demonstration
  useEffect(() => {
    const mockUsers: User[] = [
      {
        id: '1',
        username: 'admin',
        email: 'admin@nagarro.com',
        role: 'platform_admin',
        status: 'active',
        created_at: '2024-01-15T10:00:00Z',
        lastLogin: '2024-08-15T08:30:00Z'
      },
      {
        id: '2',
        username: 'project_manager',
        email: 'pm@nagarro.com',
        role: 'project_admin',
        status: 'active',
        created_at: '2024-02-01T10:00:00Z',
        lastLogin: '2024-08-14T16:45:00Z'
      },
      {
        id: '3',
        username: 'user1',
        email: 'user1@nagarro.com',
        role: 'user',
        status: 'inactive',
        created_at: '2024-03-01T10:00:00Z',
      }
    ];
    setUsers(mockUsers);
    setTotalPages(1);
  }, []);

  const handleAddNew = () => {
    setEditingUser(null);
    setModalOpened(true);
  };

  const handleEdit = (user: User) => {
    setEditingUser(user);
    setModalOpened(true);
  };

  const handleDelete = (userId: string) => {
    setUsers(users.filter(u => u.id !== userId));
    notifications.show({
      title: 'User Deleted',
      message: 'User has been successfully deleted',
      color: 'green',
    });
  };

  const toggleUserStatus = (userId: string) => {
    setUsers(users.map(u => 
      u.id === userId 
        ? { ...u, status: u.status === 'active' ? 'inactive' : 'active' }
        : u
    ));
  };

  const roleOptions = [
    { value: 'user', label: 'User' },
    { value: 'project_user', label: 'Project User' },
    { value: 'project_admin', label: 'Project Admin' },
    { value: 'platform_admin', label: 'Platform Admin' },
  ];

  const getRoleBadgeColor = (role: string) => {
    switch (role) {
      case 'platform_admin': return 'red';
      case 'project_admin': return 'blue';
      case 'project_user': return 'green';
      default: return 'gray';
    }
  };

  const getStatusBadgeColor = (status: string) => {
    return status === 'active' ? 'green' : 'gray';
  };

  const pageActions = (
    <Group gap="sm">
      <Button
        leftSection={<IconRefresh size="1rem" />}
        variant="light"
        onClick={() => setLoading(!loading)}
        loading={loading}
      >
        Refresh
      </Button>
      <Button
        leftSection={<IconPlus size="1rem" />}
        onClick={handleAddNew}
      >
        Add User
      </Button>
    </Group>
  );

  return (
    <>
      <SettingsPageLayout
        title="User Management"
        description="Manage platform users, roles, permissions, and access controls. Add new users and configure their access levels."
        icon={<IconUsers size="1.5rem" />}
        breadcrumbText="User Management"
        actions={pageActions}
      >
        <Stack gap="xl">
          {/* User Statistics */}
          <Group gap="lg">
            <Card p="md" radius="md" withBorder>
              <Text size="sm" c="dimmed">Total Users</Text>
              <Text size="xl" fw={700}>{users.length}</Text>
            </Card>
            <Card p="md" radius="md" withBorder>
              <Text size="sm" c="dimmed">Active Users</Text>
              <Text size="xl" fw={700} c="green">
                {users.filter(u => u.status === 'active').length}
              </Text>
            </Card>
            <Card p="md" radius="md" withBorder>
              <Text size="sm" c="dimmed">Admins</Text>
              <Text size="xl" fw={700} c="blue">
                {users.filter(u => u.role.includes('admin')).length}
              </Text>
            </Card>
          </Group>

          {/* Users Table */}
          <Card p="lg" radius="md" withBorder>
            <Stack gap="md">
              <Text size="lg" fw={600}>Platform Users</Text>
              
              {users.length === 0 ? (
                <Text c="dimmed" ta="center" py="xl">
                  No users found
                </Text>
              ) : (
                <Table>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>User</Table.Th>
                      <Table.Th>Role</Table.Th>
                      <Table.Th>Status</Table.Th>
                      <Table.Th>Last Login</Table.Th>
                      <Table.Th>Actions</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {users.map((user) => (
                      <Table.Tr key={user.id}>
                        <Table.Td>
                          <Group gap="sm">
                            <Avatar size="sm" color="blue">
                              {user.username.charAt(0).toUpperCase()}
                            </Avatar>
                            <div>
                              <Text fw={500}>{user.username}</Text>
                              <Text size="sm" c="dimmed">{user.email}</Text>
                            </div>
                          </Group>
                        </Table.Td>
                        <Table.Td>
                          <Badge color={getRoleBadgeColor(user.role)}>
                            {user.role.replace('_', ' ').toUpperCase()}
                          </Badge>
                        </Table.Td>
                        <Table.Td>
                          <Badge color={getStatusBadgeColor(user.status)}>
                            {user.status.toUpperCase()}
                          </Badge>
                        </Table.Td>
                        <Table.Td>
                          <Text size="sm">
                            {user.lastLogin 
                              ? new Date(user.lastLogin).toLocaleDateString()
                              : 'Never'
                            }
                          </Text>
                        </Table.Td>
                        <Table.Td>
                          <Group gap="xs">
                            <ActionIcon
                              variant="light"
                              color={user.status === 'active' ? 'red' : 'green'}
                              onClick={() => toggleUserStatus(user.id)}
                            >
                              {user.status === 'active' ? (
                                <IconUserX size="1rem" />
                              ) : (
                                <IconUserCheck size="1rem" />
                              )}
                            </ActionIcon>
                            <ActionIcon
                              variant="light"
                              onClick={() => handleEdit(user)}
                            >
                              <IconEdit size="1rem" />
                            </ActionIcon>
                            <ActionIcon
                              variant="light"
                              color="red"
                              onClick={() => handleDelete(user.id)}
                            >
                              <IconTrash size="1rem" />
                            </ActionIcon>
                          </Group>
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              )}
              
              {totalPages > 1 && (
                <Group justify="center" mt="md">
                  <Pagination
                    value={activePage}
                    onChange={setActivePage}
                    total={totalPages}
                  />
                </Group>
              )}
            </Stack>
          </Card>
        </Stack>
      </SettingsPageLayout>

      {/* User Modal */}
      <Modal
        opened={modalOpened}
        onClose={() => setModalOpened(false)}
        title={`${editingUser ? 'Edit' : 'Add'} User`}
        size="md"
      >
        <Stack gap="md">
          <TextInput
            label="Username"
            placeholder="Enter username"
            defaultValue={editingUser?.username || ''}
            required
          />
          <TextInput
            label="Email"
            placeholder="Enter email address"
            defaultValue={editingUser?.email || ''}
            required
          />
          <Select
            label="Role"
            placeholder="Select user role"
            data={roleOptions}
            defaultValue={editingUser?.role || 'user'}
            required
          />
          <Switch
            label="Active User"
            defaultChecked={editingUser?.status === 'active'}
          />
          
          <Group justify="flex-end" mt="md">
            <Button variant="light" onClick={() => setModalOpened(false)}>
              Cancel
            </Button>
            <Button onClick={() => setModalOpened(false)}>
              {editingUser ? 'Update' : 'Create'} User
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
};
