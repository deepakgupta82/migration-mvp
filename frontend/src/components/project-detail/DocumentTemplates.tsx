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
  IconEye,
  IconSettings,
  IconLock,
  IconUserCheck,
} from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { CrewAITerminal } from '../crewai-terminal';

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
  status: 'pending' | 'generating' | 'completed' | 'failed' | 'downloading';
  progress: number;
  download_url?: string;
  download_urls?: Record<string, string>;
  error_message?: string;
  job_id?: string;
  status_endpoint?: string;
  ws_endpoint?: string;
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
  const [globalTemplatesLoading, setGlobalTemplatesLoading] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [viewModalOpen, setViewModalOpen] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<DocumentTemplate | null>(null);
  const [newTemplate, setNewTemplate] = useState({
    name: '',
    description: '',
    format: '',
    output_type: 'pdf',
  });
  const [templateUsage, setTemplateUsage] = useState<Record<string, number>>({});
  const [userRole, setUserRole] = useState<'user' | 'project_admin' | 'platform_admin'>('user');
  const [currentUser, setCurrentUser] = useState<string>('deepakgupta13'); // This should come from auth context

  // Load data
  useEffect(() => {
    // Load global templates from API and replace static fallbacks
    loadGlobalTemplates();
    
    // Load other data in parallel
    Promise.all([
      loadTemplates(),
      loadGenerationRequests(),
      loadTemplateUsage(),
      loadGenerationHistory(),
      loadUserRole()
    ]).catch(error => {
      console.error('Error loading additional data:', error);
    });
  }, [projectId]);

  // Permission checking functions
  const loadUserRole = async () => {
    // This should come from your auth context/API
    // For now, setting as platform_admin for demo purposes
    setUserRole('platform_admin'); // In real app: fetch from auth API
    setCurrentUser('deepakgupta13'); // In real app: fetch from auth context
  };

  const canViewTemplate = (template: DocumentTemplate): boolean => {
    return true; // All users can view templates
  };

  const canEditProjectTemplate = (template: DocumentTemplate): boolean => {
    // Project admins can edit project templates, platform admins can edit all
    return userRole === 'platform_admin' || 
           (userRole === 'project_admin' && !template.is_global);
  };

  const canEditGlobalTemplate = (template: DocumentTemplate): boolean => {
    // Only platform admins can edit global templates
    return userRole === 'platform_admin';
  };

  const canCreateProjectTemplate = (): boolean => {
    // Project admins and platform admins can create project templates
    return userRole === 'project_admin' || userRole === 'platform_admin';
  };

  const canEditTemplate = (template: DocumentTemplate): boolean => {
    if (template.is_global) {
      return canEditGlobalTemplate(template);
    } else {
      return canEditProjectTemplate(template);
    }
  };

  const loadTemplateUsage = async () => {
    try {
      const response = await fetch(`http://localhost:8000/api/projects/${projectId}/template-usage`);
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
      const response = await fetch(`http://localhost:8000/api/projects/${projectId}/generation-history`);
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
      const response = await fetch(`http://localhost:8000/api/projects/${projectId}/deliverables`);
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
      setGlobalTemplatesLoading(true);
      // Load global templates from database via project-service with timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 6000);
      const response = await fetch('http://localhost:8000/api/templates/global', { signal: controller.signal });
      clearTimeout(timeoutId);
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

        // Set global templates data
        setGlobalTemplates(globalTemplateData);
      } else {
        throw new Error(`Failed to load global templates: ${response.status}`);
      }
    } catch (error) {
      console.error('Error loading global templates:', error);
      // Set empty array on error
      setGlobalTemplates([]);
      notifications.show({
        title: 'Global templates unavailable',
        message: 'Using cached or empty list due to slow network or backend issue.',
        color: 'orange',
      });
    } finally {
      setGlobalTemplatesLoading(false);
    }
  };

  const loadGenerationRequests = async () => {
    try {
      // Load actual generation requests from backend
      const response = await fetch(`http://localhost:8000/api/projects/${projectId}/generation-requests`);
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
      const response = await fetch(`http://localhost:8000/api/projects/${projectId}/deliverables`, {
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
      const createResponse = await fetch(`http://localhost:8000/api/projects/${projectId}/generation-requests`, {
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
      // Show notification with CrewAI message
      notifications.show({
        id: `generation-${request.id}`,
        title: 'CrewAI Document Generation Started',
        message: `Generating "${template.name}" using CrewAI multi-agent system. Live agent interactions are visible in the terminal below - watch as agents collaborate and use tools in real-time!`,
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

    // Call CrewAI backend API to generate document with live agent interactions
    const response = await fetch(`http://localhost:8000/api/projects/${projectId}/crews/document/run`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
      document_type: template.name,
      document_description: template.description || template.format || 'Generate a professional document based on the template',
      output_format: 'markdown', // CrewAI will generate markdown, then we can convert to other formats
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const crewResult = await response.json();

      if (crewResult.success) {
        // CrewAI returns job info, not direct content
        const jobId = crewResult.job_id;
        const statusEndpoint = crewResult.status_endpoint;
        const wsEndpoint = crewResult.ws_endpoint;

        // Update request with CrewAI job info
        setGenerationRequests(prev =>
          prev.map(req =>
            req.id === request.id
              ? {
                  ...req,
                  status: 'generating',
                  progress: 10,
                  job_id: jobId,
                  status_endpoint: statusEndpoint,
                  ws_endpoint: wsEndpoint
                }
              : req
          )
        );

        // Start polling for status updates
        pollCrewAIStatus(jobId, request.id, statusEndpoint);

        notifications.show({
          id: `generation-${request.id}`,
          title: 'CrewAI Document Generation Started',
          message: 'Live agent interactions are now visible in the terminal below. CrewAI agents are collaborating to generate your document.',
          color: 'blue',
          autoClose: false,
          withCloseButton: true,
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
                  error_message: crewResult.detail || 'CrewAI generation failed'
                }
              : req
          )
        );

        notifications.show({
          title: 'Generation Failed',
          message: crewResult.detail || 'CrewAI generation failed',
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

  const handleDownloadFormat = async (request: GenerationRequest, format: 'pdf' | 'docx' | 'md') => {
    // Update request status to downloading
    setGenerationRequests(prev =>
      prev.map(req =>
        req.id === request.id
          ? { ...req, status: 'downloading', progress: 50 }
          : req
      )
    );

    try {
      const baseUrl = `http://localhost:8000/api/projects/${projectId}/download/`;
      // Prefer using previously known filenames when available
      let downloadUrl = '';
      let fileName = '';
      const knownUrl = request.download_urls?.[format === 'md' ? 'markdown' : format];

      if (knownUrl) {
        downloadUrl = `http://localhost:8000${knownUrl}`;
        // derive filename from URL path
        const parts = knownUrl.split('/');
        fileName = parts[parts.length - 1];
      } else if (request.download_urls?.markdown) {
        // derive base from markdown filename and replace extension
        const mdParts = request.download_urls.markdown.split('/');
        const mdName = mdParts[mdParts.length - 1]; // like some_base.md
        const baseName = mdName.replace(/\.md$/i, '');
        fileName = `${baseName}.${format === 'md' ? 'md' : format}`;
        downloadUrl = `${baseUrl}${fileName}`;
      } else {
        // Fallback to name+date scheme
        const timestamp = new Date(request.requested_at).toISOString().split('T')[0];
        const safeName = request.template_name.toLowerCase().replace(/\s+/g, '-');
        fileName = `${safeName}-${timestamp}.${format === 'md' ? 'md' : format}`;
        downloadUrl = `${baseUrl}${fileName}`;
      }

      // Create download link
      const link = document.createElement('a');
  link.href = downloadUrl;
      link.download = fileName;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      // Update to completed with download link
      setGenerationRequests(prev =>
        prev.map(req =>
          req.id === request.id
            ? { 
                ...req, 
                status: 'completed', 
                progress: 100,
                download_url: downloadUrl,
                download_urls: {
                  ...req.download_urls,
                  [format]: downloadUrl
                }
              }
            : req
        )
      );

      notifications.show({
        title: 'Download Successful',
        message: `${request.template_name} downloaded successfully as ${format.toUpperCase()}`,
        color: 'green',
      });

    } catch (error) {
      console.error('Download failed:', error);
      
      // Update to failed status with error
      setGenerationRequests(prev =>
        prev.map(req =>
          req.id === request.id
            ? { 
                ...req, 
                status: 'failed', 
                progress: 0,
                error_message: `Download failed: ${(error as Error).message || 'Unknown error'}`
              }
            : req
        )
      );

      notifications.show({
        title: 'Download Failed',
        message: `Failed to download ${request.template_name}: ${(error as Error).message || 'Unknown error'}`,
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

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'green';
      case 'draft': return 'yellow';
      case 'archived': return 'gray';
      case 'completed': return 'green';
      case 'generating': return 'blue';
      case 'downloading': return 'cyan';
      case 'pending': return 'orange';
      case 'failed': return 'red';
      default: return 'gray';
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString() + ' ' + new Date(dateString).toLocaleTimeString();
  };

  // Poll CrewAI status for live updates
  const pollCrewAIStatus = async (jobId: string, requestId: string, statusEndpoint: string) => {
    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch(`http://localhost:8000${statusEndpoint}`);
        if (response.ok) {
          const status = await response.json();

          // Update progress and status
          setGenerationRequests(prev =>
            prev.map(req =>
              req.id === requestId
                ? {
                    ...req,
                    status: status.status === 'completed' ? 'completed' :
                           status.status === 'failed' ? 'failed' : 'generating',
                    progress: status.progress || req.progress,
                    current_step: status.current_step,
                    result: status.result
                  }
                : req
            )
          );

          // Handle completion
          if (status.status === 'completed' && status.result) {
            clearInterval(pollInterval);

            // Extract download URLs from result if available
            const result = status.result;
            let downloadUrls: Record<string, string> = {};

            // Try to construct download URLs from the result
            if (result.download_urls) {
              downloadUrls = result.download_urls;
            } else if (result.file_path) {
              // Fallback: construct URL from file path
              const baseName = result.file_path.split('/').pop()?.replace('.md', '') || 'document';
              downloadUrls = {
                markdown: `/api/projects/${projectId}/download/${baseName}.md`
              };
            }

            setGenerationRequests(prev =>
              prev.map(req =>
                req.id === requestId
                  ? {
                      ...req,
                      status: 'completed',
                      progress: 100,
                      download_urls: downloadUrls,
                      download_url: downloadUrls.markdown || downloadUrls.pdf || downloadUrls.docx,
                      content: result.content || result
                    }
                  : req
              )
            );

            // Update template usage
            setTemplates(prev =>
              prev.map(tmpl =>
                tmpl.id === status.workflow_config?.template_id
                  ? {
                      ...tmpl,
                      usage_count: tmpl.usage_count + 1,
                      last_generated: new Date().toISOString()
                    }
                  : tmpl
              )
            );

            notifications.show({
              title: 'CrewAI Generation Complete',
              message: 'Document generated successfully with live agent interactions!',
              color: 'green',
            });
          }

          // Handle failure
          if (status.status === 'failed') {
            clearInterval(pollInterval);
            setGenerationRequests(prev =>
              prev.map(req =>
                req.id === requestId
                  ? {
                      ...req,
                      status: 'failed',
                      progress: 0,
                      error_message: status.current_step || 'CrewAI generation failed'
                    }
                  : req
              )
            );

            notifications.show({
              title: 'CrewAI Generation Failed',
              message: status.current_step || 'CrewAI generation failed',
              color: 'red',
            });
          }
        }
      } catch (error) {
        console.error('Error polling CrewAI status:', error);
      }
    }, 2000); // Poll every 2 seconds

    // Stop polling after 10 minutes to prevent infinite polling
    setTimeout(() => {
      clearInterval(pollInterval);
    }, 600000);
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
          {canCreateProjectTemplate() && (
            <Button
              leftSection={<IconPlus size={16} />}
              onClick={() => setCreateModalOpen(true)}
            >
              Create Template
            </Button>
          )}
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
                      {canViewTemplate(template) && (
                        <ActionIcon
                          size="sm"
                          variant="subtle"
                          color="gray"
                          onClick={() => {
                            setSelectedTemplate(template);
                            setViewModalOpen(true);
                          }}
                          title="View Template Details"
                        >
                          <IconEye size={14} />
                        </ActionIcon>
                      )}
                      <ActionIcon
                        size="sm"
                        variant="subtle"
                        color="blue"
                        onClick={() => handleGenerateDocument(template)}
                        title="Generate Document"
                      >
                        <IconRobot size={14} />
                      </ActionIcon>
                      {canEditTemplate(template) && (
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
                      )}
                      {canEditTemplate(template) && (
                        <ActionIcon
                          size="sm"
                          variant="subtle"
                          color="red"
                          title="Delete Template"
                        >
                          <IconTrash size={14} />
                        </ActionIcon>
                      )}
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Card>

        {/* CrewAI Terminal - Only visible during CrewAI document generation with valid job_id */}
        {(() => {
          const activeRequest = generationRequests.find(req => req.status === 'generating' && req.job_id);
          return activeRequest ? (
            <Card shadow="sm" p="lg" radius="md" withBorder>
              <CrewAITerminal
                projectId={projectId}
                websocketUrl={`ws://localhost:8008/api/agents/workflows/${activeRequest.job_id}/ws`}
                correlationId={activeRequest.job_id}
                height="400px"
                showHeader={true}
                showControls={true}
                autoScroll={true}
                maxEntries={100}
              />
            </Card>
          ) : null;
        })()}

      {/* Global Templates */}
      <Card shadow="sm" p="lg" radius="md" withBorder>
        <Group justify="space-between" align="center" mb="md">
          <div>
            <Text size="md" fw={600}>
              Global Templates
            </Text>
            <Text size="sm" c="dimmed">
              Standard templates available across all projects
            </Text>
          </div>
          {globalTemplatesLoading && (
            <Loader size="sm" />
          )}
        </Group>

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
                  <Group gap="xs">
                    {canViewTemplate(template) && (
                      <ActionIcon
                        size="sm"
                        variant="subtle"
                        color="gray"
                        onClick={() => {
                          setSelectedTemplate(template);
                          setViewModalOpen(true);
                        }}
                        title="View Template Details"
                      >
                        <IconEye size={14} />
                      </ActionIcon>
                    )}
                    <ActionIcon
                      size="sm"
                      variant="subtle"
                      color="blue"
                      onClick={() => handleGenerateDocument(template)}
                      title="Generate Document"
                    >
                      <IconRobot size={14} />
                    </ActionIcon>
                  </Group>
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

                  {(request.status === 'completed' || request.status === 'downloading') && (
                    <Group gap="xs">
                      {/* Download Links for Available Formats */}
                      <Group gap="xs">
                        <Button
                          size="xs"
                          variant="light"
                          color="red"
                          leftSection={<IconFileTypePdf size={12} />}
                          onClick={() => handleDownloadFormat(request, 'pdf')}
                          loading={request.status === 'downloading'}
                        >
                          PDF
                        </Button>
                        <Button
                          size="xs"
                          variant="light"
                          color="blue"
                          leftSection={<IconFileTypeDocx size={12} />}
                          onClick={() => handleDownloadFormat(request, 'docx')}
                          loading={request.status === 'downloading'}
                        >
                          Word
                        </Button>
                        <Button
                          size="xs"
                          variant="light"
                          color="gray"
                          leftSection={<IconFile size={12} />}
                          onClick={() => handleDownloadFormat(request, 'md')}
                          loading={request.status === 'downloading'}
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
                            disabled={request.status === 'downloading'}
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

                  {/* Show retry buttons for failed downloads */}
                  {request.status === 'failed' && request.error_message?.includes('Download failed') && (
                    <Group gap="xs">
                      <Button
                        size="xs"
                        variant="light"
                        color="orange"
                        leftSection={<IconRefresh size={12} />}
                        onClick={() => {
                          // Reset status to completed to show download buttons again
                          setGenerationRequests(prev =>
                            prev.map(req =>
                              req.id === request.id
                                ? { ...req, status: 'completed', error_message: undefined }
                                : req
                            )
                          );
                        }}
                      >
                        Retry Download
                      </Button>
                    </Group>
                  )}
                </Group>
              </Paper>
            ))}
          </Stack>
        )}
      </Card>

      {/* View Template Modal */}
      <Modal
        opened={viewModalOpen}
        onClose={() => {
          setViewModalOpen(false);
          setSelectedTemplate(null);
        }}
        title="Template Details"
        size="lg"
      >
        {selectedTemplate && (
          <Stack gap="md">
            <Group justify="apart">
              <Text fw={600} size="lg">{selectedTemplate.name}</Text>
              <Badge 
                size="sm" 
                color={selectedTemplate.is_global ? 'blue' : 'green'}
                variant="light"
              >
                {selectedTemplate.is_global ? 'Global Template' : 'Project Template'}
              </Badge>
            </Group>

            <Divider />

            <div>
              <Text fw={500} size="sm" mb="xs">Description</Text>
              <Text size="sm" c="dimmed">
                {selectedTemplate.description || 'No description provided'}
              </Text>
            </div>

            <div>
              <Text fw={500} size="sm" mb="xs">Output Type</Text>
              <Badge size="sm" variant="light">
                {selectedTemplate.output_type.toUpperCase()}
              </Badge>
            </div>

            {selectedTemplate.format && (
              <div>
                <Text fw={500} size="sm" mb="xs">Format & Structure Details</Text>
                <Paper p="sm" bg="gray.0" radius="md">
                  <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
                    {selectedTemplate.format}
                  </Text>
                </Paper>
              </div>
            )}

            <div>
              <Text fw={500} size="sm" mb="xs">Usage Statistics</Text>
              <Group gap="md">
                <div>
                  <Text size="xs" c="dimmed">Times Used</Text>
                  <Text fw={500}>{templateUsage[selectedTemplate.name] || 0}</Text>
                </div>
                <div>
                  <Text size="xs" c="dimmed">Last Generated</Text>
                  <Text fw={500}>
                    {selectedTemplate.last_generated 
                      ? formatDate(selectedTemplate.last_generated)
                      : 'Never'
                    }
                  </Text>
                </div>
              </Group>
            </div>

            <div>
              <Text fw={500} size="sm" mb="xs">Template Information</Text>
              <Group gap="md">
                <div>
                  <Text size="xs" c="dimmed">Created By</Text>
                  <Text fw={500}>{selectedTemplate.created_by}</Text>
                </div>
                <div>
                  <Text size="xs" c="dimmed">Created</Text>
                  <Text fw={500}>{formatDate(selectedTemplate.created_at)}</Text>
                </div>
                <div>
                  <Text size="xs" c="dimmed">Last Updated</Text>
                  <Text fw={500}>{formatDate(selectedTemplate.updated_at)}</Text>
                </div>
              </Group>
            </div>

            <Group justify="flex-end" gap="sm">
              <Button
                variant="light"
                onClick={() => {
                  setViewModalOpen(false);
                  setSelectedTemplate(null);
                }}
              >
                Close
              </Button>
              {canEditTemplate(selectedTemplate) && (
                <Button
                  onClick={() => {
                    setViewModalOpen(false);
                    setEditModalOpen(true);
                    // selectedTemplate is already set
                  }}
                >
                  Edit Template
                </Button>
              )}
            </Group>
          </Stack>
        )}
      </Modal>

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
