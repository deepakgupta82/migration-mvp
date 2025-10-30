/**
 * IAC Governance View - Phase 1: Infrastructure as Code Governance
 * Professional interface for policy management, scans, and violations
 */

import React, { useEffect, useState } from 'react';
import {
  Card,
  Text,
  Group,
  Button,
  Stack,
  Title,
  Badge,
  Table,
  Modal,
  TextInput,
  Select,
  Textarea,
  Alert,
  ActionIcon,
  Menu,
  Tabs,
  ThemeIcon,
  Progress,
  SimpleGrid,
  Paper,
  Loader,
  Center,
  Code,
  JsonInput,
  rem,
} from '@mantine/core';
import {
  IconShieldCheck,
  IconPlus,
  IconEdit,
  IconTrash,
  IconScan,
  IconAlertTriangle,
  IconCheck,
  IconClock,
  IconAlertCircle,
  IconDots,
  IconEye,
  IconRefresh,
  IconFileCode,
  IconBug,
  IconShield,
  IconClipboard,
  IconDownload,
} from '@tabler/icons-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { notifications } from '@mantine/notifications';

interface PolicyTemplate {
  policy_id: string;
  name: string;
  description?: string;
  policy_type: 'security' | 'compliance' | 'cost' | 'best_practices';
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  rego_policy: string;
  tags?: string[];
  enabled: boolean;
  created_at: string;
}

interface PolicyScan {
  scan_id: string;
  project_id: string;
  scan_type: 'terraform' | 'cloudformation' | 'arm' | 'pulumi';
  target_path: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  violations_count: number;
  created_at: string;
  completed_at?: string;
}

interface Violation {
  violation_id: string;
  scan_id: string;
  policy_id: string;
  resource_path: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  message: string;
  line_number?: number;
  status: 'open' | 'resolved' | 'ignored';
}

export const IACGovernanceView: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const projectId = searchParams.get('project');

  const [activeTab, setActiveTab] = useState<string>('policies');
  const [policies, setPolicies] = useState<PolicyTemplate[]>([]);
  const [scans, setScans] = useState<PolicyScan[]>([]);
  const [violations, setViolations] = useState<Violation[]>([]);
  const [selectedScan, setSelectedScan] = useState<PolicyScan | null>(null);
  const [loading, setLoading] = useState(false);
  const [createPolicyModalOpen, setCreatePolicyModalOpen] = useState(false);
  const [createScanModalOpen, setCreateScanModalOpen] = useState(false);

  // Form state
  const [policyFormData, setPolicyFormData] = useState({
    name: '',
    description: '',
    policy_type: 'security' as 'security' | 'compliance' | 'cost' | 'best_practices',
    severity: 'medium' as 'critical' | 'high' | 'medium' | 'low' | 'info',
    rego_policy: '',
    tags: '',
  });

  const [scanFormData, setScanFormData] = useState({
    scan_type: 'terraform' as 'terraform' | 'cloudformation' | 'arm' | 'pulumi',
    target_path: '',
    policy_ids: [] as string[],
  });

  useEffect(() => {
    if (activeTab === 'policies') {
      loadPolicies();
    } else if (activeTab === 'scans') {
      loadScans();
    }
  }, [activeTab, projectId]);

  const loadPolicies = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/iac-governance/api/policies', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token') || 'service-backend-token'}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setPolicies(data.policies || []);
      }
    } catch (error) {
      console.error('Failed to load policies:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadScans = async () => {
    try {
      setLoading(true);
      const url = projectId
        ? `/api/iac-governance/api/scans?project_id=${projectId}`
        : '/api/iac-governance/api/scans';

      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token') || 'service-backend-token'}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setScans(data.scans || []);
      }
    } catch (error) {
      console.error('Failed to load scans:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadViolations = async (scanId: string) => {
    try {
      const response = await fetch(`/api/iac-governance/api/scans/${scanId}/violations`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token') || 'service-backend-token'}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setViolations(data.violations || []);
      }
    } catch (error) {
      console.error('Failed to load violations:', error);
    }
  };

  const handleCreatePolicy = async () => {
    try {
      const response = await fetch('/api/iac-governance/api/policies', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token') || 'service-backend-token'}`,
        },
        body: JSON.stringify({
          ...policyFormData,
          tags: policyFormData.tags ? policyFormData.tags.split(',').map(t => t.trim()) : [],
        }),
      });

      if (response.ok) {
        notifications.show({
          title: 'Success',
          message: 'Policy template created successfully',
          color: 'green',
        });
        setCreatePolicyModalOpen(false);
        setPolicyFormData({
          name: '',
          description: '',
          policy_type: 'security',
          severity: 'medium',
          rego_policy: '',
          tags: '',
        });
        loadPolicies();
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create policy');
      }
    } catch (error: any) {
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to create policy',
        color: 'red',
      });
    }
  };

  const handleCreateScan = async () => {
    try {
      if (!projectId) {
        notifications.show({
          title: 'Error',
          message: 'Please select a project first',
          color: 'red',
        });
        return;
      }

      const response = await fetch('/api/iac-governance/api/scans', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token') || 'service-backend-token'}`,
        },
        body: JSON.stringify({
          project_id: projectId,
          ...scanFormData,
        }),
      });

      if (response.ok) {
        notifications.show({
          title: 'Success',
          message: 'Policy scan started',
          color: 'green',
        });
        setCreateScanModalOpen(false);
        setScanFormData({
          scan_type: 'terraform',
          target_path: '',
          policy_ids: [],
        });
        loadScans();
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create scan');
      }
    } catch (error: any) {
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to create scan',
        color: 'red',
      });
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'red';
      case 'high': return 'orange';
      case 'medium': return 'yellow';
      case 'low': return 'blue';
      case 'info': return 'gray';
      default: return 'gray';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'green';
      case 'running': return 'blue';
      case 'failed': return 'red';
      default: return 'gray';
    }
  };

  const getPolicyTypeIcon = (type: string) => {
    switch (type) {
      case 'security': return <IconShield size={16} />;
      case 'compliance': return <IconShieldCheck size={16} />;
      case 'cost': return <IconAlertTriangle size={16} />;
      case 'best_practices': return <IconCheck size={16} />;
      default: return <IconFileCode size={16} />;
    }
  };

  return (
    <Stack gap="lg">
      {/* Header */}
      <Group justify="space-between">
        <div>
          <Title order={2}>IAC Governance</Title>
          <Text size="sm" c="dimmed">
            Infrastructure as Code policy management and compliance scanning
          </Text>
        </div>
        <Group>
          <ActionIcon variant="light" onClick={() => activeTab === 'policies' ? loadPolicies() : loadScans()}>
            <IconRefresh size={18} />
          </ActionIcon>
          {activeTab === 'policies' && (
            <Button
              leftSection={<IconPlus size={18} />}
              onClick={() => setCreatePolicyModalOpen(true)}
            >
              Create Policy
            </Button>
          )}
          {activeTab === 'scans' && (
            <Button
              leftSection={<IconScan size={18} />}
              onClick={() => setCreateScanModalOpen(true)}
              disabled={!projectId}
            >
              Start Scan
            </Button>
          )}
        </Group>
      </Group>

      {!projectId && activeTab === 'scans' && (
        <Alert icon={<IconAlertCircle size={16} />} color="blue">
          Please select a project from the query parameters to run policy scans
        </Alert>
      )}

      {/* Stats Cards */}
      <SimpleGrid cols={4}>
        <Paper p="md" withBorder>
          <Group justify="space-between">
            <div>
              <Text size="xs" c="dimmed" tt="uppercase">Total Policies</Text>
              <Text size="xl" fw={700}>{policies.length}</Text>
            </div>
            <ThemeIcon size="lg" variant="light" color="blue">
              <IconShieldCheck size={24} />
            </ThemeIcon>
          </Group>
        </Paper>
        <Paper p="md" withBorder>
          <Group justify="space-between">
            <div>
              <Text size="xs" c="dimmed" tt="uppercase">Active Scans</Text>
              <Text size="xl" fw={700}>
                {scans.filter(s => s.status === 'running').length}
              </Text>
            </div>
            <ThemeIcon size="lg" variant="light" color="blue">
              <IconScan size={24} />
            </ThemeIcon>
          </Group>
        </Paper>
        <Paper p="md" withBorder>
          <Group justify="space-between">
            <div>
              <Text size="xs" c="dimmed" tt="uppercase">Total Violations</Text>
              <Text size="xl" fw={700}>
                {scans.reduce((sum, s) => sum + (s.violations_count || 0), 0)}
              </Text>
            </div>
            <ThemeIcon size="lg" variant="light" color="orange">
              <IconAlertTriangle size={24} />
            </ThemeIcon>
          </Group>
        </Paper>
        <Paper p="md" withBorder>
          <Group justify="space-between">
            <div>
              <Text size="xs" c="dimmed" tt="uppercase">Critical Issues</Text>
              <Text size="xl" fw={700}>
                {violations.filter(v => v.severity === 'critical').length}
              </Text>
            </div>
            <ThemeIcon size="lg" variant="light" color="red">
              <IconBug size={24} />
            </ThemeIcon>
          </Group>
        </Paper>
      </SimpleGrid>

      {/* Tabs */}
      <Tabs value={activeTab} onChange={(value) => setActiveTab(value || 'policies')}>
        <Tabs.List>
          <Tabs.Tab value="policies" leftSection={<IconShieldCheck size={16} />}>
            Policy Templates
          </Tabs.Tab>
          <Tabs.Tab value="scans" leftSection={<IconScan size={16} />}>
            Policy Scans
          </Tabs.Tab>
        </Tabs.List>

        {/* Policies Tab */}
        <Tabs.Panel value="policies" pt="md">
          <Card>
            <Table highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Policy Name</Table.Th>
                  <Table.Th>Type</Table.Th>
                  <Table.Th>Severity</Table.Th>
                  <Table.Th>Status</Table.Th>
                  <Table.Th>Created</Table.Th>
                  <Table.Th>Actions</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {policies.map((policy) => (
                  <Table.Tr key={policy.policy_id}>
                    <Table.Td>
                      <div>
                        <Text fw={500}>{policy.name}</Text>
                        {policy.description && (
                          <Text size="xs" c="dimmed">{policy.description}</Text>
                        )}
                      </div>
                    </Table.Td>
                    <Table.Td>
                      <Badge variant="light" leftSection={getPolicyTypeIcon(policy.policy_type)}>
                        {policy.policy_type}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Badge color={getSeverityColor(policy.severity)}>
                        {policy.severity}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Badge color={policy.enabled ? 'green' : 'gray'}>
                        {policy.enabled ? 'Enabled' : 'Disabled'}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">
                        {new Date(policy.created_at).toLocaleDateString()}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Group gap="xs">
                        <ActionIcon variant="light" color="blue">
                          <IconEye size={16} />
                        </ActionIcon>
                        <Menu position="bottom-end">
                          <Menu.Target>
                            <ActionIcon variant="subtle">
                              <IconDots size={16} />
                            </ActionIcon>
                          </Menu.Target>
                          <Menu.Dropdown>
                            <Menu.Item leftSection={<IconEdit size={16} />}>
                              Edit Policy
                            </Menu.Item>
                            <Menu.Item leftSection={<IconClipboard size={16} />}>
                              Duplicate
                            </Menu.Item>
                            <Menu.Divider />
                            <Menu.Item leftSection={<IconTrash size={16} />} color="red">
                              Delete Policy
                            </Menu.Item>
                          </Menu.Dropdown>
                        </Menu>
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>

            {policies.length === 0 && (
              <Center p="xl">
                <Stack align="center" gap="sm">
                  <IconShieldCheck size={48} stroke={1.5} color="gray" />
                  <Text c="dimmed">No policy templates yet</Text>
                  <Button
                    size="sm"
                    variant="light"
                    leftSection={<IconPlus size={16} />}
                    onClick={() => setCreatePolicyModalOpen(true)}
                  >
                    Create First Policy
                  </Button>
                </Stack>
              </Center>
            )}
          </Card>
        </Tabs.Panel>

        {/* Scans Tab */}
        <Tabs.Panel value="scans" pt="md">
          <Card>
            <Table highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Scan Type</Table.Th>
                  <Table.Th>Target Path</Table.Th>
                  <Table.Th>Violations</Table.Th>
                  <Table.Th>Status</Table.Th>
                  <Table.Th>Created</Table.Th>
                  <Table.Th>Actions</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {scans.map((scan) => (
                  <Table.Tr key={scan.scan_id}>
                    <Table.Td>
                      <Badge variant="light" color="blue">
                        {scan.scan_type.toUpperCase()}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Code>{scan.target_path}</Code>
                    </Table.Td>
                    <Table.Td>
                      <Badge
                        variant="filled"
                        color={scan.violations_count > 0 ? 'red' : 'green'}
                      >
                        {scan.violations_count || 0}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Badge color={getStatusColor(scan.status)}>
                        {scan.status}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">
                        {new Date(scan.created_at).toLocaleDateString()}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Group gap="xs">
                        <ActionIcon
                          variant="light"
                          color="blue"
                          onClick={() => {
                            setSelectedScan(scan);
                            loadViolations(scan.scan_id);
                          }}
                        >
                          <IconEye size={16} />
                        </ActionIcon>
                        <ActionIcon variant="light" color="green">
                          <IconDownload size={16} />
                        </ActionIcon>
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>

            {scans.length === 0 && (
              <Center p="xl">
                <Stack align="center" gap="sm">
                  <IconScan size={48} stroke={1.5} color="gray" />
                  <Text c="dimmed">No policy scans yet</Text>
                  <Button
                    size="sm"
                    variant="light"
                    leftSection={<IconScan size={16} />}
                    onClick={() => setCreateScanModalOpen(true)}
                    disabled={!projectId}
                  >
                    Start First Scan
                  </Button>
                </Stack>
              </Center>
            )}
          </Card>
        </Tabs.Panel>
      </Tabs>

      {/* Violations Modal */}
      <Modal
        opened={selectedScan !== null}
        onClose={() => setSelectedScan(null)}
        size="xl"
        title={
          <Group>
            <IconBug size={20} />
            <Text fw={600}>Scan Violations</Text>
          </Group>
        }
      >
        <Stack>
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Severity</Table.Th>
                <Table.Th>Resource</Table.Th>
                <Table.Th>Message</Table.Th>
                <Table.Th>Line</Table.Th>
                <Table.Th>Status</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {violations.map((violation) => (
                <Table.Tr key={violation.violation_id}>
                  <Table.Td>
                    <Badge color={getSeverityColor(violation.severity)}>
                      {violation.severity}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Code>{violation.resource_path}</Code>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">{violation.message}</Text>
                  </Table.Td>
                  <Table.Td>
                    {violation.line_number && <Code>L{violation.line_number}</Code>}
                  </Table.Td>
                  <Table.Td>
                    <Badge variant="outline">{violation.status}</Badge>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Stack>
      </Modal>

      {/* Create Policy Modal */}
      <Modal
        opened={createPolicyModalOpen}
        onClose={() => setCreatePolicyModalOpen(false)}
        title="Create Policy Template"
        size="lg"
      >
        <Stack>
          <TextInput
            label="Policy Name"
            placeholder="e.g., Enforce S3 Encryption"
            required
            value={policyFormData.name}
            onChange={(e) => setPolicyFormData({ ...policyFormData, name: e.target.value })}
          />
          <Textarea
            label="Description"
            placeholder="Describe what this policy checks..."
            rows={2}
            value={policyFormData.description}
            onChange={(e) => setPolicyFormData({ ...policyFormData, description: e.target.value })}
          />
          <Select
            label="Policy Type"
            required
            data={[
              { value: 'security', label: '🛡️ Security' },
              { value: 'compliance', label: '✓ Compliance' },
              { value: 'cost', label: '💰 Cost' },
              { value: 'best_practices', label: '⭐ Best Practices' },
            ]}
            value={policyFormData.policy_type}
            onChange={(value) => setPolicyFormData({ ...policyFormData, policy_type: value as any })}
          />
          <Select
            label="Severity"
            required
            data={[
              { value: 'critical', label: '🔴 Critical' },
              { value: 'high', label: '🟠 High' },
              { value: 'medium', label: '🟡 Medium' },
              { value: 'low', label: '🔵 Low' },
              { value: 'info', label: 'ℹ️ Info' },
            ]}
            value={policyFormData.severity}
            onChange={(value) => setPolicyFormData({ ...policyFormData, severity: value as any })}
          />
          <Textarea
            label="Rego Policy"
            placeholder="package terraform.policy..."
            rows={8}
            ff="monospace"
            value={policyFormData.rego_policy}
            onChange={(e) => setPolicyFormData({ ...policyFormData, rego_policy: e.target.value })}
          />
          <TextInput
            label="Tags (comma-separated)"
            placeholder="aws, s3, encryption"
            value={policyFormData.tags}
            onChange={(e) => setPolicyFormData({ ...policyFormData, tags: e.target.value })}
          />
          <Group justify="flex-end" mt="md">
            <Button variant="subtle" onClick={() => setCreatePolicyModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreatePolicy}>Create Policy</Button>
          </Group>
        </Stack>
      </Modal>

      {/* Create Scan Modal */}
      <Modal
        opened={createScanModalOpen}
        onClose={() => setCreateScanModalOpen(false)}
        title="Start Policy Scan"
      >
        <Stack>
          <Select
            label="Scan Type"
            required
            data={[
              { value: 'terraform', label: 'Terraform' },
              { value: 'cloudformation', label: 'CloudFormation' },
              { value: 'arm', label: 'ARM Template' },
              { value: 'pulumi', label: 'Pulumi' },
            ]}
            value={scanFormData.scan_type}
            onChange={(value) => setScanFormData({ ...scanFormData, scan_type: value as any })}
          />
          <TextInput
            label="Target Path"
            placeholder="e.g., /terraform/modules/s3"
            required
            value={scanFormData.target_path}
            onChange={(e) => setScanFormData({ ...scanFormData, target_path: e.target.value })}
          />
          <Group justify="flex-end" mt="md">
            <Button variant="subtle" onClick={() => setCreateScanModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateScan}>Start Scan</Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
};

export default IACGovernanceView;
