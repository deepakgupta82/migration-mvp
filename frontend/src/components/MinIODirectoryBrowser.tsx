import React, { useState, useEffect } from 'react';
import {
  Card,
  Text,
  Stack,
  Group,
  Button,
  Loader,
  Table,
  Badge,
  ActionIcon,
  Tooltip,
  Breadcrumbs,
  Anchor,
  Alert,
  Modal,
  TextInput
} from '@mantine/core';
import {
  IconFolder,
  IconFile,
  IconDownload,
  IconRefresh,
  IconHome,
  IconChevronRight,
  IconAlertCircle,
  IconSearch,
  IconFolderOpen
} from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { apiService } from '../services/api';

interface MinIOFile {
  name: string;
  type: 'file' | 'directory';
  size?: number;
  last_modified?: string;
  path: string;
}

interface MinIODirectoryBrowserProps {
  projectId: string;
}

const MinIODirectoryBrowser: React.FC<MinIODirectoryBrowserProps> = ({ projectId }) => {
  const [files, setFiles] = useState<MinIOFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [currentPath, setCurrentPath] = useState('');
  const [downloadingFiles, setDownloadingFiles] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState('');
  const [showCreateFolder, setShowCreateFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');

  // Fetch directory contents
  const fetchDirectoryContents = async (path: string = '') => {
    setLoading(true);
    try {
      // Call backend API to list MinIO files
      const response = await apiService.listProjectFiles(projectId, path);
      setFiles(response.files || []);
      setCurrentPath(path);
    } catch (error) {
      console.error('Error fetching directory contents:', error);
      notifications.show({
        title: 'Error',
        message: 'Failed to load directory contents',
        color: 'red'
      });
      setFiles([]);
    } finally {
      setLoading(false);
    }
  };

  // Initialize component
  useEffect(() => {
    fetchDirectoryContents();
  }, [projectId]);

  // Navigate to directory
  const navigateToDirectory = (path: string) => {
    fetchDirectoryContents(path);
  };

  // Navigate up one level
  const navigateUp = () => {
    const pathParts = currentPath.split('/').filter(p => p);
    pathParts.pop();
    const parentPath = pathParts.join('/');
    navigateToDirectory(parentPath);
  };

  // Download file
  const handleDownloadFile = async (file: MinIOFile) => {
    if (file.type === 'directory') return;

    setDownloadingFiles(prev => new Set(prev).add(file.path));
    try {
      // Call backend API to download file
      const response = await fetch(
        `/api/storage/projects/${projectId}/download/${encodeURIComponent(file.path)}`,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token') || 'service-backend-token'}`
          }
        }
      );

      if (!response.ok) {
        throw new Error(`Download failed: ${response.statusText}`);
      }

      // Create download link
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = file.name;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      notifications.show({
        title: 'Success',
        message: `Downloaded ${file.name}`,
        color: 'green'
      });
    } catch (error) {
      console.error('Error downloading file:', error);
      notifications.show({
        title: 'Download Failed',
        message: `Failed to download ${file.name}`,
        color: 'red'
      });
    } finally {
      setDownloadingFiles(prev => {
        const newSet = new Set(prev);
        newSet.delete(file.path);
        return newSet;
      });
    }
  };

  // Create breadcrumb navigation
  const getBreadcrumbs = () => {
    if (!currentPath) return [];
    
    const pathParts = currentPath.split('/').filter(p => p);
    const breadcrumbs = [];
    
    // Add root
    breadcrumbs.push({
      title: 'Root',
      path: ''
    });
    
    // Add each path segment
    for (let i = 0; i < pathParts.length; i++) {
      const path = pathParts.slice(0, i + 1).join('/');
      breadcrumbs.push({
        title: pathParts[i],
        path
      });
    }
    
    return breadcrumbs;
  };

  // Filter files based on search query
  const filteredFiles = files.filter(file =>
    file.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Get file type icon
  const getFileIcon = (file: MinIOFile) => {
    if (file.type === 'directory') {
      return <IconFolder size={18} color="#228be6" />;
    }
    return <IconFile size={18} color="#495057" />;
  };

  // Format file size
  const formatFileSize = (size?: number) => {
    if (!size) return 'Unknown';
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    if (size < 1024 * 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`;
    return `${(size / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  };

  return (
    <Card shadow="sm" p="lg" radius="md" withBorder>
      <Stack gap="md">
        {/* Header */}
        <Group justify="space-between">
          <Text size="lg" fw={600}>
            Project Files Browser
          </Text>
          <Group gap="sm">
            <Button
              size="sm"
              variant="light"
              leftSection={<IconRefresh size={14} />}
              onClick={() => fetchDirectoryContents(currentPath)}
              loading={loading}
            >
              Refresh
            </Button>
          </Group>
        </Group>

        {/* Navigation */}
        <Group gap="sm">
          {/* Breadcrumbs */}
          <Breadcrumbs separator={<IconChevronRight size={14} />} style={{ flex: 1 }}>
            {getBreadcrumbs().map((crumb, index) => (
              <Anchor
                key={crumb.path}
                onClick={() => navigateToDirectory(crumb.path)}
                size="sm"
                style={{ cursor: 'pointer' }}
              >
                {index === 0 ? <IconHome size={14} /> : crumb.title}
              </Anchor>
            ))}
          </Breadcrumbs>

          {/* Search */}
          <TextInput
            placeholder="Search files..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.currentTarget.value)}
            leftSection={<IconSearch size={14} />}
            style={{ width: 200 }}
          />
        </Group>

        {/* Directory Contents */}
        {loading ? (
          <Group justify="center" p="xl">
            <Loader size="md" />
            <Text>Loading directory contents...</Text>
          </Group>
        ) : filteredFiles.length === 0 ? (
          <Alert icon={<IconAlertCircle size={16} />} color="gray">
            {searchQuery ? 'No files match your search criteria.' : 'This directory is empty.'}
          </Alert>
        ) : (
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>Type</Table.Th>
                <Table.Th>Size</Table.Th>
                <Table.Th>Last Modified</Table.Th>
                <Table.Th>Actions</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {/* Show "up" directory if not at root */}
              {currentPath && (
                <Table.Tr style={{ cursor: 'pointer' }} onClick={navigateUp}>
                  <Table.Td>
                    <Group gap="xs">
                      <IconFolderOpen size={18} color="#228be6" />
                      <Text size="sm" fw={500}>..</Text>
                    </Group>
                  </Table.Td>
                  <Table.Td>
                    <Badge size="sm" variant="light" color="blue">Directory</Badge>
                  </Table.Td>
                  <Table.Td>-</Table.Td>
                  <Table.Td>-</Table.Td>
                  <Table.Td>-</Table.Td>
                </Table.Tr>
              )}

              {/* Directory and file listings */}
              {filteredFiles.map((file) => (
                <Table.Tr
                  key={file.path}
                  style={{ cursor: file.type === 'directory' ? 'pointer' : 'default' }}
                  onClick={() => file.type === 'directory' && navigateToDirectory(file.path)}
                >
                  <Table.Td>
                    <Group gap="xs">
                      {getFileIcon(file)}
                      <Text size="sm" fw={file.type === 'directory' ? 500 : 400}>
                        {file.name}
                      </Text>
                    </Group>
                  </Table.Td>
                  <Table.Td>
                    <Badge 
                      size="sm" 
                      variant="light" 
                      color={file.type === 'directory' ? 'blue' : 'gray'}
                    >
                      {file.type === 'directory' ? 'Directory' : 'File'}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" c="dimmed">
                      {file.type === 'directory' ? '-' : formatFileSize(file.size)}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" c="dimmed">
                      {file.last_modified ? new Date(file.last_modified).toLocaleString() : '-'}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    {file.type === 'file' && (
                      <Tooltip label="Download file">
                        <ActionIcon
                          size="sm"
                          variant="subtle"
                          color="blue"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDownloadFile(file);
                          }}
                          loading={downloadingFiles.has(file.path)}
                        >
                          <IconDownload size={14} />
                        </ActionIcon>
                      </Tooltip>
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}

        {/* Status */}
        <Group justify="space-between">
          <Text size="sm" c="dimmed">
            {filteredFiles.length} items {searchQuery && `(filtered from ${files.length})`}
          </Text>
          <Text size="sm" c="dimmed">
            Path: /{currentPath || 'root'}
          </Text>
        </Group>
      </Stack>
    </Card>
  );
};

export default MinIODirectoryBrowser;