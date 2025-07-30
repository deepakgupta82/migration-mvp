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
}

export const DocumentTemplates: React.FC<DocumentTemplatesProps> = ({ projectId }) => {
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

  // Mock data - replace with real API calls
  useEffect(() => {
    loadTemplates();
    loadGlobalTemplates();
    loadGenerationRequests();
  }, [projectId]);

  const loadTemplates = async () => {
    setLoading(true);
    try {
      // Mock project-specific templates
      const mockTemplates: DocumentTemplate[] = [
        {
          id: 'tmpl-1',
          name: 'Infrastructure Assessment Report',
          description: 'Comprehensive infrastructure analysis with recommendations for cloud migration',
          format: 'Detailed technical report with executive summary, current state analysis, migration roadmap, and risk assessment',
          output_type: 'pdf',
          is_global: false,
          created_by: 'deepakgupta13',
          created_at: '2025-07-25T10:00:00Z',
          updated_at: '2025-07-25T10:00:00Z',
          usage_count: 3,
          last_generated: '2025-07-29T09:45:00Z',
          status: 'active',
        },
        {
          id: 'tmpl-2',
          name: 'Cost Optimization Analysis',
          description: 'Detailed cost analysis and optimization recommendations for cloud migration',
          format: 'Financial analysis with current costs, projected cloud costs, ROI calculations, and optimization strategies',
          output_type: 'xlsx',
          is_global: false,
          created_by: 'deepakgupta13',
          created_at: '2025-07-26T14:30:00Z',
          updated_at: '2025-07-26T14:30:00Z',
          usage_count: 1,
          last_generated: '2025-07-28T16:20:00Z',
          status: 'active',
        },
        {
          id: 'tmpl-3',
          name: 'Security Compliance Checklist',
          description: 'Security assessment and compliance checklist for cloud migration',
          format: 'Checklist format with security controls, compliance requirements, and remediation steps',
          output_type: 'docx',
          is_global: false,
          created_by: 'deepakgupta13',
          created_at: '2025-07-27T11:15:00Z',
          updated_at: '2025-07-27T11:15:00Z',
          usage_count: 0,
          last_generated: null,
          status: 'draft',
        },
      ];
      setTemplates(mockTemplates);
    } catch (error) {
      console.error('Error loading templates:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadGlobalTemplates = async () => {
    try {
      // Mock global templates
      const mockGlobalTemplates: DocumentTemplate[] = [
        {
          id: 'global-1',
          name: 'Standard Migration Playbook',
          description: 'Standard enterprise migration playbook with best practices and methodologies',
          format: 'Comprehensive playbook with phases, tasks, deliverables, and success criteria',
          output_type: 'pdf',
          is_global: true,
          created_by: 'admin',
          created_at: '2025-07-20T09:00:00Z',
          updated_at: '2025-07-20T09:00:00Z',
          usage_count: 15,
          last_generated: '2025-07-29T08:30:00Z',
          status: 'active',
        },
        {
          id: 'global-2',
          name: 'Risk Assessment Matrix',
          description: 'Standard risk assessment matrix for cloud migration projects',
          format: 'Risk matrix with categories, impact levels, mitigation strategies, and monitoring plans',
          output_type: 'xlsx',
          is_global: true,
          created_by: 'admin',
          created_at: '2025-07-21T13:45:00Z',
          updated_at: '2025-07-21T13:45:00Z',
          usage_count: 8,
          last_generated: '2025-07-28T15:10:00Z',
          status: 'active',
        },
      ];
      setGlobalTemplates(mockGlobalTemplates);
    } catch (error) {
      console.error('Error loading global templates:', error);
    }
  };

  const loadGenerationRequests = async () => {
    try {
      // Mock generation requests
      const mockRequests: GenerationRequest[] = [
        {
          id: 'req-1',
          template_id: 'tmpl-1',
          template_name: 'Infrastructure Assessment Report',
          requested_by: 'deepakgupta13',
          requested_at: '2025-07-29T09:45:00Z',
          status: 'completed',
          progress: 100,
          download_url: '/api/downloads/infrastructure-report-20250729.pdf',
        },
        {
          id: 'req-2',
          template_id: 'tmpl-2',
          template_name: 'Cost Optimization Analysis',
          requested_by: 'deepakgupta13',
          requested_at: '2025-07-28T16:20:00Z',
          status: 'completed',
          progress: 100,
          download_url: '/api/downloads/cost-analysis-20250728.xlsx',
        },
        {
          id: 'req-3',
          template_id: 'global-1',
          template_name: 'Standard Migration Playbook',
          requested_by: 'deepakgupta13',
          requested_at: '2025-07-29T10:30:00Z',
          status: 'generating',
          progress: 65,
        },
      ];
      setGenerationRequests(mockRequests);
    } catch (error) {
      console.error('Error loading generation requests:', error);
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
      const template: DocumentTemplate = {
        id: `tmpl-${Date.now()}`,
        name: newTemplate.name,
        description: newTemplate.description,
        format: newTemplate.format,
        output_type: newTemplate.output_type,
        is_global: false,
        created_by: 'deepakgupta13',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        usage_count: 0,
        last_generated: null,
        status: 'draft',
      };

      setTemplates(prev => [...prev, template]);
      setCreateModalOpen(false);
      setNewTemplate({ name: '', description: '', format: '', output_type: 'pdf' });

      notifications.show({
        title: 'Template Created',
        message: 'Document template created successfully',
        color: 'green',
      });
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: 'Failed to create template',
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

    setGenerationRequests(prev => [request, ...prev]);

    try {

      notifications.show({
        title: 'Generation Started',
        message: `Document generation started for "${template.name}"`,
        color: 'blue',
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
      const response = await fetch(`/api/projects/${projectId}/generate-document`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: template.name,
          description: template.description,
          format: template.format,
          output_type: template.output_type,
        }),
      });

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
                  download_url: result.download_url
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

  const handleDownload = (request: GenerationRequest) => {
    if (request.download_url) {
      // Create a temporary link element and trigger download
      const link = document.createElement('a');
      link.href = request.download_url;
      link.download = `${request.template_name.toLowerCase().replace(/\s+/g, '-')}-${new Date().toISOString().split('T')[0]}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      notifications.show({
        title: 'Download Started',
        message: `Downloading ${request.template_name}`,
        color: 'blue',
      });
    }
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
                    <Text size="sm">{template.usage_count} times</Text>
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
                  <Text size="sm">{template.usage_count} times</Text>
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
        <Text size="md" fw={600} mb="md">
          Generation History
        </Text>

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
                      <Progress value={request.progress} size="sm" mb="xs" />
                    )}

                    {request.error_message && (
                      <Alert icon={<IconX size={14} />} color="red">
                        {request.error_message}
                      </Alert>
                    )}
                  </div>

                  {request.status === 'completed' && request.download_url && (
                    <Button
                      size="xs"
                      variant="light"
                      leftSection={<IconDownload size={12} />}
                      onClick={() => handleDownload(request)}
                    >
                      Download
                    </Button>
                  )}
                </Group>
              </Paper>
            ))}
          </Stack>
        )}
      </Card>

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
