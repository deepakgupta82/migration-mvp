import React, { useState, useEffect } from 'react';
import {
  Card,
  Text,
  Button,
  Stack,
  Group,
  Table,
  Modal,
  TextInput,
  Textarea,
  Badge,
  ActionIcon,
  Alert,
  Divider,
  Paper,
  Loader,
  Select,
  Accordion,
  Code,
  Progress,
  Menu,
} from '@mantine/core';
import {
  IconPlus,
  IconDownload,
  IconRefresh,
  IconEdit,
  IconTrash,
  IconFileText,
  IconRobot,
  IconClock,
  IconUser,
  IconCheck,
  IconX,
  IconAlertCircle,
  IconTemplate,
  IconFile,
  IconFileTypePdf,
  IconFileTypeDocx,
  IconChevronDown,
} from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';

interface DocumentTemplate {
  id: string;
  name: string;
  description: string;
  format: string;
  output_type: string;
  is_global: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
  usage_count: number;
  last_generated: string | null;
  status: 'draft' | 'active' | 'archived';
}

interface GenerationRequest {
  id: string;
  template_id: string;
  template_name: string;
  requested_by: string;
  requested_at: string;
  status: 'pending' | 'generating' | 'completed' | 'failed';
  progress: number;
  download_url?: string;
  error_message?: string;
}

interface DocumentTemplatesProps {
  projectId: string;
  onNavigateToCrewInteraction?: () => void;
}

export const DocumentTemplates: React.FC<DocumentTemplatesProps> = ({ projectId, onNavigateToCrewInteraction }) => {
  const [templates, setTemplates] = useState<DocumentTemplate[]>([]);
  const [globalTemplates, setGlobalTemplates] = useState<DocumentTemplate[]>([]);
  const [generationRequests, setGenerationRequests] = useState<GenerationRequest[]>([]);
  const [loading, setLoading] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<DocumentTemplate | null>(null);
  const [newTemplate, setNewTemplate] = useState({
    name: '',
    description: '',
    format: '',
    output_type: 'pdf',
  });
  const [templateUsage, setTemplateUsage] = useState<Record<string, number>>({});

  // Load data
  useEffect(() => {
    loadTemplates();
    loadGlobalTemplates();
    loadGenerationRequests();
    loadTemplateUsage();
    loadGenerationHistory();
  }, [projectId]);

  const loadTemplateUsage = async () => {
    try {
      const response = await fetch(`http://localhost:8000/projects/${projectId}/template-usage`);
      if (response.ok) {
        const data = await response.json();
        const usageMap: Record<string, number> = {};
        data.template_usage.forEach((usage: any) => {
          usageMap[usage.template_name] = usage.usage_count;
        });
        setTemplateUsage(usageMap);
      }
    } catch (error) {
      console.log('Could not load template usage:', error);
      // Set default usage to 0 for new projects
      setTemplateUsage({});
    }
  };

  const loadGenerationHistory = async () => {
    try {
      const response = await fetch(`http://localhost:8000/projects/${projectId}/generation-history`);
      if (response.ok) {
        const history = await response.json();
        console.log('Generation history loaded:', history);

        // If no history, templates will show 0 usage and no last generated date
        if (history.length === 0) {
          console.log('No generation history found for this project');
          return;
        }

        // Update templates with real generation history
        setTemplates(prev => prev.map(template => {
          const templateHistory = history.filter((h: any) => h.template_name === template.name);
          const lastGenerated = templateHistory.length > 0 ? templateHistory[0].generated_at : null;
          const usageCount = templateHistory.length;

          return {
            ...template,
            usage_count: usageCount,
            last_generated: lastGenerated
          };
        }));
      }
    } catch (error) {
      console.log('Could not load generation history:', error);
    }
  };

  const loadTemplates = async () => {
    setLoading(true);
    try {
      // Load real project-specific templates from backend
      const response = await fetch(`http://localhost:8002/projects/${projectId}/deliverables`);
      if (response.ok) {
        const backendTemplates = await response.json();

        // Convert backend format to frontend format
        const convertedTemplates: DocumentTemplate[] = backendTemplates.map((template: any) => ({
          id: template.id,
          name: template.name,
          description: template.description,
          format: template.template_content || 'Standard document format',
          output_type: template.output_format || 'pdf',
          is_global: false,
          created_by: template.created_by || 'user',
          created_at: template.created_at,
          updated_at: template.updated_at,
          usage_count: 0, // Will be updated by loadGenerationHistory
          last_generated: null, // Will be updated by loadGenerationHistory
          status: template.status || 'active',
        }));

        setTemplates(convertedTemplates);
      } else {
        // For new projects with no templates, start with empty array
        console.log('No project-specific templates found, starting with empty list');
        setTemplates([]);
      }
    } catch (error) {
      console.error('Error loading templates:', error);
      // For new projects or on error, start with empty array
      setTemplates([]);
    } finally {
      setLoading(false);
    }
  };

  const loadGlobalTemplates = async () => {
    try {
      // Load global templates from database via project-service
      const response = await fetch('http://localhost:8002/templates/global');
      if (response.ok) {
        const dbTemplates = await response.json();

        // Convert database format to frontend format
        const globalTemplateData: DocumentTemplate[] = dbTemplates.map((template: any) => ({
          id: template.id,
          name: template.name,
          description: template.description || 'No description provided',
          format: template.template_content || template.prompt || 'Standard document format',
          output_type: template.output_format || 'pdf',
          is_global: true,
          created_by: template.created_by || 'admin',
          created_at: template.created_at,
          updated_at: template.updated_at,
          usage_count: template.usage_count || 0,
          last_generated: template.last_used,
          status: template.is_active ? 'active' : 'inactive',
        }));

        setGlobalTemplates(globalTemplateData);
      } else {
        throw new Error(`Failed to load global templates: ${response.status}`);
      }
    } catch (error) {
      console.error('Error loading global templates:', error);
      setGlobalTemplates([]);
    }
  };

  const loadGenerationRequests = async () => {
    try {
      // Load actual generation requests from backend
      const response = await fetch(`http://localhost:8002/projects/${projectId}/generation-requests`);
      if (response.ok) {
        const requests = await response.json();
        setGenerationRequests(requests);
      } else {
        // For new projects, start with empty list
        setGenerationRequests([]);
      }
    } catch (error) {
      console.error('Error loading generation requests:', error);
      // For new projects or on error, start with empty list
      setGenerationRequests([]);
    }
  };

  const handleCreateTemplate = async () => {
    if (!newTemplate.name || !newTemplate.description) {
      notifications.show({
        title: 'Validation Error',
        message: 'Please fill in all required fields',
        color: 'red',
      });
      return;
    }

    try {
      // Create template via API
      const response = await fetch(`http://localhost:8002/projects/${projectId}/deliverables`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: newTemplate.name,
          description: newTemplate.description,
          prompt: newTemplate.format, // Use format as prompt
          template_content: newTemplate.format,
          output_format: newTemplate.output_type,
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to create template: ${response.status}`);
      }

      const createdTemplate = await response.json();

      // Convert to frontend format and add to list
      const frontendTemplate: DocumentTemplate = {
        id: createdTemplate.id,
        name: createdTemplate.name,
        description: createdTemplate.description,
        format: createdTemplate.template_content || createdTemplate.prompt,
        output_type: createdTemplate.output_format || 'pdf',
        is_global: false,
        created_by: createdTemplate.created_by || 'user',
        created_at: createdTemplate.created_at,
        updated_at: createdTemplate.updated_at,
        usage_count: 0,
        last_generated: null,
        status: 'active',
      };

      setTemplates(prev => [...prev, frontendTemplate]);
      setCreateModalOpen(false);
      setNewTemplate({ name: '', description: '', format: '', output_type: 'pdf' });

      notifications.show({
        title: 'Template Created',
        message: 'Document template created successfully',
        color: 'green',
      });
    } catch (error) {
      console.error('Error creating template:', error);
      notifications.show({
        title: 'Error',
        message: 'Failed to create template in database',
        color: 'red',
      });
    }
  };

  const handleUpdateTemplate = async () => {
    if (!selectedTemplate || !selectedTemplate.name || !selectedTemplate.description) {
      notifications.show({
        title: 'Validation Error',
        message: 'Please fill in all required fields',
        color: 'red',
      });
      return;
    }

    try {
      const updatedTemplate = {
        ...selectedTemplate,
        updated_at: new Date().toISOString(),
      };

      setTemplates(prev => prev.map(t =>
        t.id === selectedTemplate.id ? updatedTemplate : t
      ));

      setEditModalOpen(false);
      setSelectedTemplate(null);

      notifications.show({
        title: 'Template Updated',
        message: 'Document template updated successfully',
        color: 'green',
      });
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: 'Failed to update template',
        color: 'red',
      });
    }
  };

  const handleGenerateDocument = async (template: DocumentTemplate) => {
    const request: GenerationRequest = {
      id: `req-${Date.now()}`,
      template_id: template.id,
      template_name: template.name,
      requested_by: 'deepakgupta13',
      requested_at: new Date().toISOString(),
      status: 'pending',
      progress: 0,
    };

    // Store request in database first
    try {
      const createResponse = await fetch(`http://localhost:8002/projects/${projectId}/generation-requests`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request)
      });

      if (!createResponse.ok) {
        throw new Error('Failed to create generation request in database');
      }
    } catch (error) {
      console.error('Error creating generation request:', error);
      notifications.show({
        title: 'Database Error',
        message: 'Failed to store generation request. Continuing anyway...',
        color: 'orange',
      });
    }

    setGenerationRequests(prev => [request, ...prev]);

    try {
      // Show notification with navigation message
      notifications.show({
        id: `generation-${request.id}`,
        title: 'Document Generation Started',
        message: `Generating "${template.name}" using AI agents. ${onNavigateToCrewInteraction ? 'Use the "Monitor Live Progress" button below to view crew interactions in real-time.' : ''}`,
        color: 'blue',
        autoClose: false,
        withCloseButton: true,
      });

      // Update status to generating
      setGenerationRequests(prev =>
        prev.map(req =>
          req.id === request.id
            ? { ...req, status: 'generating', progress: 25 }
            : req
        )
      );

      // Call backend API to generate document
      const response = await fetch(`http://localhost:8000/api/projects/${projectId}/generate-document`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: template.name,
          description: template.description,
          format: template.format,
          output_type: template.output_type,
          request_id: request.id, // Include request ID for database updates
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();

      if (result.success) {
        // Update to completed status
        setGenerationRequests(prev =>
          prev.map(req =>
            req.id === request.id
              ? {
                  ...req,
                  status: 'completed',
                  progress: 100,
                  download_url: result.download_urls?.markdown || result.download_urls?.pdf || result.download_urls?.docx || '#',
                  download_urls: result.download_urls || {},
                  content: result.content,
                  file_path: result.file_path
                }
              : req
          )
        );

        // Update template usage count
        setTemplates(prev =>
          prev.map(tmpl =>
            tmpl.id === template.id
              ? {
                  ...tmpl,
                  usage_count: tmpl.usage_count + 1,
                  last_generated: new Date().toISOString()
                }
              : tmpl
          )
        );

        notifications.show({
          title: 'Generation Complete',
          message: result.message,
          color: 'green',
        });
      } else {
        // Update to failed status
        setGenerationRequests(prev =>
          prev.map(req =>
            req.id === request.id
              ? {
                  ...req,
                  status: 'failed',
                  progress: 0,
                  error_message: result.message
                }
              : req
          )
        );

        notifications.show({
          title: 'Generation Failed',
          message: result.message,
          color: 'red',
        });
      }

    } catch (error) {
      // Update to failed status
      setGenerationRequests(prev =>
        prev.map(req =>
          req.id === request.id
            ? {
                ...req,
                status: 'failed',
                progress: 0,
                error_message: 'Network error occurred'
              }
            : req
        )
      );

      notifications.show({
        title: 'Generation Failed',
        message: 'Failed to generate document due to network error',
        color: 'red',
      });
    }
  };

  const handleDownload = (request: GenerationRequest, format?: string) => {
    if (request.download_url) {
      // Create a temporary link element and trigger download
      const link = document.createElement('a');
      link.href = `http://localhost:8000${request.download_url}`;
      link.download = `${request.template_name.toLowerCase().replace(/\s+/g, '-')}-${new Date().toISOString().split('T')[0]}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      notifications.show({
        title: 'Download Started',
        message: `Downloading ${request.template_name}${format ? ` as ${format.toUpperCase()}` : ''}`,
        color: 'blue',
      });
    }
  };

  const handleDownloadFormat = (request: GenerationRequest, format: 'pdf' | 'docx' | 'md') => {
    // Check if the specific format is available
    const baseUrl = `http://localhost:8000/api/projects/${projectId}/download/`;
    const timestamp = new Date(request.requested_at).toISOString().split('T')[0];
    const safeName = request.template_name.toLowerCase().replace(/\s+/g, '-');

    let downloadUrl = '';
    let fileName = '';

    switch (format) {
      case 'pdf':
        downloadUrl = `${baseUrl}${safeName}-${timestamp}.pdf`;
        fileName = `${safeName}-${timestamp}.pdf`;
        break;
      case 'docx':
        downloadUrl = `${baseUrl}${safeName}-${timestamp}.docx`;
        fileName = `${safeName}-${timestamp}.docx`;
        break;
      case 'md':
        downloadUrl = `${baseUrl}${safeName}-${timestamp}.md`;
        fileName = `${safeName}-${timestamp}.md`;
        break;
    }

    // Create download link
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    notifications.show({
      title: 'Download Started',
      message: `Downloading ${request.template_name} as ${format.toUpperCase()}`,
      color: 'blue',
    });
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'green';
      case 'draft': return 'yellow';
      case 'archived': return 'gray';
      case 'completed': return 'green';
      case 'generating': return 'blue';
      case 'pending': return 'orange';
      case 'failed': return 'red';
      default: return 'gray';
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString() + ' ' + new Date(dateString).toLocaleTimeString();
  };

  return (
    <Stack gap="lg">
      {/* Header */}
      <Group justify="space-between">
        <div>
          <Text size="lg" fw={600}>
            Document Templates
          </Text>
          <Text size="sm" c="dimmed">
            Create and manage document templates for automated generation
          </Text>
        </div>
        <Group gap="sm">
          <Button
            leftSection={<IconPlus size={16} />}
            onClick={() => setCreateModalOpen(true)}
          >
            Create Template
          </Button>
          <ActionIcon variant="subtle" onClick={loadTemplates}>
            <IconRefresh size={16} />
          </ActionIcon>
        </Group>
      </Group>

      {/* Project Templates */}
      <Card shadow="sm" p="lg" radius="md" withBorder>
        <Text size="md" fw={600} mb="md">
          Project Templates
        </Text>

        {loading ? (
          <Group justify="center" p="xl">
            <Loader size="md" />
          </Group>
        ) : templates.length === 0 ? (
          <Alert icon={<IconAlertCircle size={16} />} color="blue">
            No project templates created yet. Create your first template to get started.
          </Alert>
        ) : (
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Template</Table.Th>
                <Table.Th>Output</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Usage</Table.Th>
                <Table.Th>Last Generated</Table.Th>
                <Table.Th>Actions</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {templates.map((template) => (
                <Table.Tr key={template.id}>
                  <Table.Td>
                    <div>
                      <Text fw={500} size="sm">{template.name}</Text>
                      <Text size="xs" c="dimmed" style={{ maxWidth: '300px' }}>
                        {template.description}
                      </Text>
                    </div>
                  </Table.Td>
                  <Table.Td>
                    <Badge size="sm" variant="light">
                      {template.output_type.toUpperCase()}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Badge size="sm" color={getStatusColor(template.status)}>
                      {template.status}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">{templateUsage[template.name] || 0} times</Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="xs" c="dimmed">
                      {template.last_generated
                        ? formatDate(template.last_generated)
                        : 'Never'
                      }
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Group gap="xs">
                      <ActionIcon
                        size="sm"
                        variant="subtle"
                        color="blue"
                        onClick={() => handleGenerateDocument(template)}
                        title="Generate Document"
                      >
                        <IconRobot size={14} />
                      </ActionIcon>
                      <ActionIcon
                        size="sm"
                        variant="subtle"
                        onClick={() => {
                          setSelectedTemplate(template);
                          setEditModalOpen(true);
                        }}
                        title="Edit Template"
                      >
                        <IconEdit size={14} />
                      </ActionIcon>
                      <ActionIcon
                        size="sm"
                        variant="subtle"
                        color="red"
                        title="Delete Template"
                      >
                        <IconTrash size={14} />
                      </ActionIcon>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Card>

      {/* Global Templates */}
      <Card shadow="sm" p="lg" radius="md" withBorder>
        <Text size="md" fw={600} mb="md">
          Global Templates
        </Text>
        <Text size="sm" c="dimmed" mb="md">
          Standard templates available across all projects
        </Text>

        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Template</Table.Th>
              <Table.Th>Output</Table.Th>
              <Table.Th>Usage</Table.Th>
              <Table.Th>Actions</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {globalTemplates.map((template) => (
              <Table.Tr key={template.id}>
                <Table.Td>
                  <div>
                    <Group gap="xs">
                      <IconTemplate size={16} color="#868e96" />
                      <Text fw={500} size="sm">{template.name}</Text>
                    </Group>
                    <Text size="xs" c="dimmed" style={{ maxWidth: '300px' }}>
                      {template.description}
                    </Text>
                  </div>
                </Table.Td>
                <Table.Td>
                  <Badge size="sm" variant="light">
                    {template.output_type.toUpperCase()}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{templateUsage[template.name] || 0} times</Text>
                </Table.Td>
                <Table.Td>
                  <ActionIcon
                    size="sm"
                    variant="subtle"
                    color="blue"
                    onClick={() => handleGenerateDocument(template)}
                    title="Generate Document"
                  >
                    <IconRobot size={14} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Card>

      {/* Generation History */}
      <Card shadow="sm" p="lg" radius="md" withBorder>
        <Group justify="space-between" align="center" mb="md">
          <Text size="md" fw={600}>
            Generation History
          </Text>
          {/* Show navigation button if there are active generations */}
          {generationRequests.some(req => req.status === 'generating' || req.status === 'pending') && onNavigateToCrewInteraction && (
            <Button
              size="sm"
              variant="light"
              color="blue"
              leftSection={<IconRobot size={16} />}
              onClick={onNavigateToCrewInteraction}
            >
              Monitor Live Progress
            </Button>
          )}
        </Group>

        {generationRequests.length === 0 ? (
          <Alert icon={<IconAlertCircle size={16} />} color="blue">
            No documents generated yet.
          </Alert>
        ) : (
          <Stack gap="md">
            {generationRequests.map((request) => (
              <Paper key={request.id} p="md" withBorder>
                <Group justify="space-between" align="flex-start">
                  <div style={{ flex: 1 }}>
                    <Group gap="xs" mb="xs">
                      <IconFileText size={16} />
                      <Text fw={500} size="sm">{request.template_name}</Text>
                      <Badge size="xs" color={getStatusColor(request.status)}>
                        {request.status}
                      </Badge>
                    </Group>

                    <Group gap="md" mb="xs">
                      <Group gap="xs">
                        <IconUser size={12} />
                        <Text size="xs" c="dimmed">{request.requested_by}</Text>
                      </Group>
                      <Group gap="xs">
                        <IconClock size={12} />
                        <Text size="xs" c="dimmed">{formatDate(request.requested_at)}</Text>
                      </Group>
                    </Group>

                    {request.status === 'generating' && (
                      <div>
                        <Progress value={request.progress} size="sm" mb="xs" />
                        {onNavigateToCrewInteraction && (
                          <Button
                            size="xs"
                            variant="light"
                            color="blue"
                            leftSection={<IconRobot size={12} />}
                            onClick={onNavigateToCrewInteraction}
                            mt="xs"
                          >
                            View Live Progress
                          </Button>
                        )}
                      </div>
                    )}

                    {request.error_message && (
                      <Alert icon={<IconX size={14} />} color="red">
                        {request.error_message}
                      </Alert>
                    )}
                  </div>

                  {request.status === 'completed' && request.download_url && (
                    <Group gap="xs">
                      {/* Download Links for Available Formats */}
                      <Group gap="xs">
                        <Button
                          size="xs"
                          variant="light"
                          color="red"
                          leftSection={<IconFileTypePdf size={12} />}
                          onClick={() => handleDownloadFormat(request, 'pdf')}
                        >
                          PDF
                        </Button>
                        <Button
                          size="xs"
                          variant="light"
                          color="blue"
                          leftSection={<IconFileTypeDocx size={12} />}
                          onClick={() => handleDownloadFormat(request, 'docx')}
                        >
                          Word
                        </Button>
                        <Button
                          size="xs"
                          variant="light"
                          color="gray"
                          leftSection={<IconFile size={12} />}
                          onClick={() => handleDownloadFormat(request, 'md')}
                        >
                          Markdown
                        </Button>
                      </Group>

                      {/* Dropdown Menu for All Formats */}
                      <Menu shadow="md" width={200}>
                        <Menu.Target>
                          <Button
                            size="xs"
                            variant="light"
                            rightSection={<IconChevronDown size={12} />}
                          >
                            Download
                          </Button>
                        </Menu.Target>

                        <Menu.Dropdown>
                          <Menu.Label>Available Formats</Menu.Label>
                          <Menu.Item
                            leftSection={<IconFileTypePdf size={14} />}
                            onClick={() => handleDownloadFormat(request, 'pdf')}
                          >
                            Download as PDF
                          </Menu.Item>
                          <Menu.Item
                            leftSection={<IconFileTypeDocx size={14} />}
                            onClick={() => handleDownloadFormat(request, 'docx')}
                          >
                            Download as Word
                          </Menu.Item>
                          <Menu.Item
                            leftSection={<IconFile size={14} />}
                            onClick={() => handleDownloadFormat(request, 'md')}
                          >
                            Download as Markdown
                          </Menu.Item>
                        </Menu.Dropdown>
                      </Menu>
                    </Group>
                  )}
                </Group>
              </Paper>
            ))}
          </Stack>
        )}
      </Card>

      {/* Edit Template Modal */}
      <Modal
        opened={editModalOpen}
        onClose={() => {
          setEditModalOpen(false);
          setSelectedTemplate(null);
        }}
        title="Edit Document Template"
        size="lg"
      >
        {selectedTemplate && (
          <Stack gap="md">
            <TextInput
              label="Template Name"
              placeholder="e.g., Infrastructure Assessment Report"
              value={selectedTemplate.name}
              onChange={(event) => setSelectedTemplate({
                ...selectedTemplate,
                name: event.currentTarget.value
              })}
              required
            />

            <Textarea
              label="Description"
              placeholder="Describe what this template generates and its purpose..."
              value={selectedTemplate.description}
              onChange={(event) => setSelectedTemplate({
                ...selectedTemplate,
                description: event.currentTarget.value
              })}
              rows={3}
              required
            />

            <Textarea
              label="Format & Output Details"
              placeholder="Describe the format, structure, and content that should be included in the generated document..."
              value={selectedTemplate.format || ''}
              onChange={(event) => setSelectedTemplate({
                ...selectedTemplate,
                format: event.currentTarget.value
              })}
              rows={4}
            />

            <Select
              label="Output Type"
              value={selectedTemplate.output_type}
              onChange={(value) => setSelectedTemplate({
                ...selectedTemplate,
                output_type: value || 'pdf'
              })}
              data={[
                { value: 'pdf', label: 'PDF Document' },
                { value: 'docx', label: 'Word Document' },
                { value: 'xlsx', label: 'Excel Spreadsheet' },
                { value: 'pptx', label: 'PowerPoint Presentation' },
                { value: 'txt', label: 'Text File' },
              ]}
            />

            <Group justify="flex-end" gap="sm">
              <Button
                variant="light"
                onClick={() => {
                  setEditModalOpen(false);
                  setSelectedTemplate(null);
                }}
              >
                Cancel
              </Button>
              <Button onClick={handleUpdateTemplate}>
                Update Template
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>

      {/* Create Template Modal */}
      <Modal
        opened={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        title="Create Document Template"
        size="lg"
      >
        <Stack gap="md">
          <TextInput
            label="Template Name"
            placeholder="e.g., Infrastructure Assessment Report"
            value={newTemplate.name}
            onChange={(event) => setNewTemplate({ ...newTemplate, name: event.currentTarget.value })}
            required
          />

          <Textarea
            label="Description"
            placeholder="Describe what this template generates and its purpose..."
            value={newTemplate.description}
            onChange={(event) => setNewTemplate({ ...newTemplate, description: event.currentTarget.value })}
            rows={3}
            required
          />

          <Textarea
            label="Format & Output Details"
            placeholder="Describe the format, structure, and content that should be included in the generated document..."
            value={newTemplate.format}
            onChange={(event) => setNewTemplate({ ...newTemplate, format: event.currentTarget.value })}
            rows={4}
          />

          <Select
            label="Output Type"
            value={newTemplate.output_type}
            onChange={(value) => setNewTemplate({ ...newTemplate, output_type: value || 'pdf' })}
            data={[
              { value: 'pdf', label: 'PDF Document' },
              { value: 'docx', label: 'Word Document' },
              { value: 'xlsx', label: 'Excel Spreadsheet' },
              { value: 'pptx', label: 'PowerPoint Presentation' },
              { value: 'txt', label: 'Text File' },
            ]}
          />

          <Group justify="flex-end" gap="sm">
            <Button variant="light" onClick={() => setCreateModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateTemplate}>
              Create Template
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
};

export default DocumentTemplates;
