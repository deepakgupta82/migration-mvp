import { useState, useEffect } from 'react';
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
  Select,
  Switch,
  Paper,
  Loader,
} from '@mantine/core';
import {
  IconPlus,
  IconEdit,
  IconTrash,
  IconTemplate,
  IconRefresh,
  IconAlertCircle,
  IconCheck,
  IconX,
  IconRobot,
  IconDownload,
} from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';

interface GlobalDocumentTemplate {
  id: string;
  name: string;
  description: string;
  format: string;
  output_type: string;
  category: string;
  is_active: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
  usage_count: number;
  last_used: string | null;
}

export const GlobalDocumentTemplates: React.FC = () => {
  const [templates, setTemplates] = useState<GlobalDocumentTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<GlobalDocumentTemplate | null>(null);
  const [newTemplate, setNewTemplate] = useState({
    name: '',
    description: '',
    format: '',
    output_type: 'pdf',
    category: 'migration',
    is_active: true,
  });

  useEffect(() => {
    loadTemplates();
    loadGlobalUsageStats();
  }, []);

  const loadGlobalUsageStats = async () => {
    try {
      const response = await fetch('http://localhost:8002/template-usage/global');
      if (response.ok) {
        const data = await response.json();
        // Update templates with real usage data
        setTemplates(prev => prev.map(template => {
          const usage = data.global_template_usage.find(
            (u: any) => u.template_name === template.name
          );
          return {
            ...template,
            usage_count: usage ? usage.total_usage : 0,
            last_used: usage ? usage.last_used : null
          };
        }));
      }
    } catch (error) {
      console.log('Could not load global template usage:', error);
    }
  };

  const loadTemplates = async () => {
    setLoading(true);
    try {
      // Load global templates from database via project-service
      const response = await fetch('http://localhost:8002/templates/global');
      if (response.ok) {
        const dbTemplates = await response.json();

        // Convert database format to frontend format
        const convertedTemplates: GlobalDocumentTemplate[] = dbTemplates.map((template: any) => ({
          id: template.id,
          name: template.name,
          description: template.description || 'No description provided',
          format: template.template_content || template.prompt || 'Standard document format',
          output_type: template.output_format || 'pdf',
          category: template.category || 'migration',
          is_active: template.is_active !== false,
          created_by: template.created_by || 'admin',
          created_at: template.created_at,
          updated_at: template.updated_at,
          usage_count: template.usage_count || 0,
          last_used: template.last_used,
        }));

        setTemplates(convertedTemplates);
      } else {
        throw new Error(`Failed to load templates: ${response.status}`);
      }
    } catch (error) {
      console.error('Error loading global templates:', error);
      // Fallback to empty array instead of mock data
      setTemplates([]);
      notifications.show({
        title: 'Error',
        message: 'Failed to load global templates from database',
        color: 'red',
      });
    } finally {
      setLoading(false);
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
      const response = await fetch('http://localhost:8002/templates/global', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: newTemplate.name,
          description: newTemplate.description,
          prompt: newTemplate.format, // Use format as prompt for now
          category: newTemplate.category,
          output_format: newTemplate.output_type,
          template_content: newTemplate.format,
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to create template: ${response.status}`);
      }

      const createdTemplate = await response.json();

      // Convert to frontend format and add to list
      const frontendTemplate: GlobalDocumentTemplate = {
        id: createdTemplate.id,
        name: createdTemplate.name,
        description: createdTemplate.description,
        format: createdTemplate.template_content || createdTemplate.prompt,
        output_type: createdTemplate.output_format,
        category: createdTemplate.category,
        is_active: createdTemplate.is_active,
        created_by: createdTemplate.created_by || 'admin',
        created_at: createdTemplate.created_at,
        updated_at: createdTemplate.updated_at,
        usage_count: 0,
        last_used: null,
      };

      setTemplates(prev => [...prev, frontendTemplate]);
      setCreateModalOpen(false);
      setNewTemplate({
        name: '',
        description: '',
        format: '',
        output_type: 'pdf',
        category: 'migration',
        is_active: true,
      });

      notifications.show({
        title: 'Template Created',
        message: 'Global document template created successfully',
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

  const handleEditTemplate = async () => {
    if (!selectedTemplate) return;

    try {
      setTemplates(prev =>
        prev.map(template =>
          template.id === selectedTemplate.id
            ? { ...selectedTemplate, updated_at: new Date().toISOString() }
            : template
        )
      );

      setEditModalOpen(false);
      setSelectedTemplate(null);

      notifications.show({
        title: 'Template Updated',
        message: 'Global template updated successfully',
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

  const handleDeleteTemplate = async (templateId: string) => {
    try {
      setTemplates(prev => prev.filter(template => template.id !== templateId));

      notifications.show({
        title: 'Template Deleted',
        message: 'Global template deleted successfully',
        color: 'green',
      });
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: 'Failed to delete template',
        color: 'red',
      });
    }
  };

  const toggleTemplateStatus = async (templateId: string) => {
    try {
      setTemplates(prev =>
        prev.map(template =>
          template.id === templateId
            ? { ...template, is_active: !template.is_active, updated_at: new Date().toISOString() }
            : template
        )
      );

      notifications.show({
        title: 'Status Updated',
        message: 'Template status updated successfully',
        color: 'blue',
      });
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: 'Failed to update template status',
        color: 'red',
      });
    }
  };

  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'migration': return 'blue';
      case 'assessment': return 'green';
      case 'financial': return 'yellow';
      case 'security': return 'red';
      case 'technical': return 'purple';
      case 'reporting': return 'gray';
      default: return 'gray';
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString() + ' ' + new Date(dateString).toLocaleTimeString();
  };

  const categories = [
    { value: 'migration', label: 'Migration' },
    { value: 'assessment', label: 'Assessment' },
    { value: 'financial', label: 'Financial' },
    { value: 'security', label: 'Security' },
    { value: 'technical', label: 'Technical' },
    { value: 'reporting', label: 'Reporting' },
  ];

  const outputTypes = [
    { value: 'pdf', label: 'PDF Document' },
    { value: 'docx', label: 'Word Document' },
    { value: 'xlsx', label: 'Excel Spreadsheet' },
    { value: 'pptx', label: 'PowerPoint Presentation' },
    { value: 'txt', label: 'Text File' },
  ];

  return (
    <Card shadow="sm" p="lg" radius="md" withBorder>
      <Group justify="space-between" mb="md">
        <div>
          <Text size="lg" fw={600}>
            Global Document Templates
          </Text>
          <Text size="sm" c="dimmed">
            Manage global document templates available across all projects
          </Text>
        </div>
        <Group gap="sm">
          <Button
            leftSection={<IconPlus size={16} />}
            onClick={() => setCreateModalOpen(true)}
          >
            Create Global Template
          </Button>
          <ActionIcon variant="subtle" onClick={loadTemplates}>
            <IconRefresh size={16} />
          </ActionIcon>
        </Group>
      </Group>

      {loading ? (
        <Group justify="center" p="xl">
          <Loader size="md" />
        </Group>
      ) : templates.length === 0 ? (
        <Alert icon={<IconAlertCircle size={16} />} color="blue">
          No global templates created yet. Create your first global template to get started.
        </Alert>
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Template</Table.Th>
              <Table.Th>Category</Table.Th>
              <Table.Th>Output</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Usage</Table.Th>
              <Table.Th>Last Used</Table.Th>
              <Table.Th>Actions</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {templates.map((template) => (
              <Table.Tr key={template.id}>
                <Table.Td>
                  <div>
                    <Group gap="xs" mb="xs">
                      <IconTemplate size={16} />
                      <Text fw={500} size="sm">{template.name}</Text>
                    </Group>
                    <Text size="xs" c="dimmed" style={{ maxWidth: '300px' }}>
                      {template.description}
                    </Text>
                  </div>
                </Table.Td>
                <Table.Td>
                  <Badge size="sm" color={getCategoryColor(template.category)}>
                    {template.category}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Badge size="sm" variant="light">
                    {template.output_type.toUpperCase()}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Switch
                    checked={template.is_active}
                    onChange={() => toggleTemplateStatus(template.id)}
                    size="sm"
                    color="green"
                  />
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{template.usage_count} times</Text>
                </Table.Td>
                <Table.Td>
                  <Text size="xs" c="dimmed">
                    {template.last_used
                      ? formatDate(template.last_used)
                      : 'Never'
                    }
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Group gap="xs">
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
                      onClick={() => handleDeleteTemplate(template.id)}
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

      {/* Create Template Modal */}
      <Modal
        opened={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        title="Create Global Document Template"
        size="lg"
      >
        <Stack gap="md">
          <TextInput
            label="Template Name"
            placeholder="e.g., Standard Migration Playbook"
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

          <Group grow>
            <Select
              label="Category"
              value={newTemplate.category}
              onChange={(value) => setNewTemplate({ ...newTemplate, category: value || 'migration' })}
              data={categories}
            />

            <Select
              label="Output Type"
              value={newTemplate.output_type}
              onChange={(value) => setNewTemplate({ ...newTemplate, output_type: value || 'pdf' })}
              data={outputTypes}
            />
          </Group>

          <Switch
            label="Active Template"
            description="Active templates are available for use in projects"
            checked={newTemplate.is_active}
            onChange={(event) => setNewTemplate({ ...newTemplate, is_active: event.currentTarget.checked })}
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

      {/* Edit Template Modal */}
      <Modal
        opened={editModalOpen}
        onClose={() => setEditModalOpen(false)}
        title="Edit Global Document Template"
        size="lg"
      >
        {selectedTemplate && (
          <Stack gap="md">
            <TextInput
              label="Template Name"
              value={selectedTemplate.name}
              onChange={(event) => setSelectedTemplate({ ...selectedTemplate, name: event.currentTarget.value })}
              required
            />

            <Textarea
              label="Description"
              value={selectedTemplate.description}
              onChange={(event) => setSelectedTemplate({ ...selectedTemplate, description: event.currentTarget.value })}
              rows={3}
              required
            />

            <Textarea
              label="Format & Output Details"
              value={selectedTemplate.format}
              onChange={(event) => setSelectedTemplate({ ...selectedTemplate, format: event.currentTarget.value })}
              rows={4}
            />

            <Group grow>
              <Select
                label="Category"
                value={selectedTemplate.category}
                onChange={(value) => setSelectedTemplate({ ...selectedTemplate, category: value || 'migration' })}
                data={categories}
              />

              <Select
                label="Output Type"
                value={selectedTemplate.output_type}
                onChange={(value) => setSelectedTemplate({ ...selectedTemplate, output_type: value || 'pdf' })}
                data={outputTypes}
              />
            </Group>

            <Switch
              label="Active Template"
              description="Active templates are available for use in projects"
              checked={selectedTemplate.is_active}
              onChange={(event) => setSelectedTemplate({ ...selectedTemplate, is_active: event.currentTarget.checked })}
            />

            <Group justify="flex-end" gap="sm">
              <Button variant="light" onClick={() => setEditModalOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleEditTemplate}>
                Save Changes
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>
    </Card>
  );
};

export default GlobalDocumentTemplates;
