/**
 * FinOps View - Phase 1: Financial Operations & Cost Optimization
 * Professional interface for cost analysis and optimization recommendations
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
  Alert,
  ActionIcon,
  SimpleGrid,
  Paper,
  ThemeIcon,
  Loader,
  Center,
  Progress,
  RingProgress,
  Tooltip,
  rem,
} from '@mantine/core';
import {
  IconCash,
  IconTrendingUp,
  IconTrendingDown,
  IconAlertCircle,
  IconRefresh,
  IconChartBar,
  IconCoin,
  IconPercentage,
  IconPigMoney,
} from '@tabler/icons-react';
import { useSearchParams } from 'react-router-dom';

interface CostData {
  total_cost: number;
  monthly_cost: number;
  projected_annual: number;
  cost_trend: 'increasing' | 'decreasing' | 'stable';
  top_services: Array<{
    service: string;
    cost: number;
    percentage: number;
  }>;
}

export const FinOpsView: React.FC = () => {
  const [searchParams] = useSearchParams();
  const projectId = searchParams.get('project');

  const [costData, setCostData] = useState<CostData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadCostData();
  }, [projectId]);

  const loadCostData = async () => {
    try {
      setLoading(true);
      // Simulated data - replace with actual API call
      // const response = await fetch(`/api/finops/costs?project_id=${projectId}`);
      
      // Mock data for demonstration
      setTimeout(() => {
        setCostData({
          total_cost: 15234.56,
          monthly_cost: 4567.89,
          projected_annual: 54814.68,
          cost_trend: 'increasing',
          top_services: [
            { service: 'EC2', cost: 2134.45, percentage: 46.7 },
            { service: 'RDS', cost: 1234.56, percentage: 27.0 },
            { service: 'S3', cost: 678.90, percentage: 14.9 },
            { service: 'Lambda', cost: 345.67, percentage: 7.6 },
            { service: 'Others', cost: 174.31, percentage: 3.8 },
          ],
        });
        setLoading(false);
      }, 1000);
    } catch (error) {
      console.error('Failed to load cost data:', error);
      setLoading(false);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  if (loading) {
    return (
      <Center h={400}>
        <Loader size="lg" />
      </Center>
    );
  }

  if (!projectId) {
    return (
      <Alert icon={<IconAlertCircle size={16} />} color="blue">
        Please select a project from the query parameters to view cost data
      </Alert>
    );
  }

  return (
    <Stack gap="lg">
      {/* Header */}
      <Group justify="space-between">
        <div>
          <Title order={2}>FinOps & Cost Optimization</Title>
          <Text size="sm" c="dimmed">
            Financial operations, cost analysis, and optimization recommendations
          </Text>
        </div>
        <Group>
          <ActionIcon variant="light" onClick={loadCostData}>
            <IconRefresh size={18} />
          </ActionIcon>
        </Group>
      </Group>

      {/* Cost Overview Cards */}
      <SimpleGrid cols={4}>
        <Paper p="md" withBorder>
          <Group justify="space-between">
            <div>
              <Text size="xs" c="dimmed" tt="uppercase">Total Cost</Text>
              <Text size="xl" fw={700}>
                {formatCurrency(costData?.total_cost || 0)}
              </Text>
              <Text size="xs" c="dimmed">All time</Text>
            </div>
            <ThemeIcon size="lg" variant="light" color="blue">
              <IconCash size={24} />
            </ThemeIcon>
          </Group>
        </Paper>

        <Paper p="md" withBorder>
          <Group justify="space-between">
            <div>
              <Text size="xs" c="dimmed" tt="uppercase">Monthly Cost</Text>
              <Text size="xl" fw={700}>
                {formatCurrency(costData?.monthly_cost || 0)}
              </Text>
              <Group gap="xs" mt={4}>
                {costData?.cost_trend === 'increasing' && (
                  <>
                    <IconTrendingUp size={14} color="red" />
                    <Text size="xs" c="red">+12.5%</Text>
                  </>
                )}
                {costData?.cost_trend === 'decreasing' && (
                  <>
                    <IconTrendingDown size={14} color="green" />
                    <Text size="xs" c="green">-8.3%</Text>
                  </>
                )}
              </Group>
            </div>
            <ThemeIcon size="lg" variant="light" color="cyan">
              <IconChartBar size={24} />
            </ThemeIcon>
          </Group>
        </Paper>

        <Paper p="md" withBorder>
          <Group justify="space-between">
            <div>
              <Text size="xs" c="dimmed" tt="uppercase">Projected Annual</Text>
              <Text size="xl" fw={700}>
                {formatCurrency(costData?.projected_annual || 0)}
              </Text>
              <Text size="xs" c="dimmed">Based on current usage</Text>
            </div>
            <ThemeIcon size="lg" variant="light" color="grape">
              <IconCoin size={24} />
            </ThemeIcon>
          </Group>
        </Paper>

        <Paper p="md" withBorder>
          <Group justify="space-between">
            <div>
              <Text size="xs" c="dimmed" tt="uppercase">Savings Potential</Text>
              <Text size="xl" fw={700}>
                {formatCurrency(892.45)}
              </Text>
              <Text size="xs" c="green">19.5% savings</Text>
            </div>
            <ThemeIcon size="lg" variant="light" color="green">
              <IconPigMoney size={24} />
            </ThemeIcon>
          </Group>
        </Paper>
      </SimpleGrid>

      {/* Cost Breakdown */}
      <SimpleGrid cols={2}>
        {/* Service Cost Distribution */}
        <Card>
          <Stack>
            <Group justify="space-between">
              <Title order={4}>Cost by Service</Title>
              <Text size="sm" c="dimmed">
                {formatCurrency(costData?.monthly_cost || 0)}
              </Text>
            </Group>

            <Center>
              <RingProgress
                size={200}
                thickness={20}
                sections={
                  costData?.top_services.map((service, index) => ({
                    value: service.percentage,
                    color: ['blue', 'cyan', 'grape', 'orange', 'gray'][index],
                    tooltip: `${service.service}: ${formatCurrency(service.cost)}`,
                  })) || []
                }
                label={
                  <div style={{ textAlign: 'center' }}>
                    <Text size="xs" c="dimmed">Monthly</Text>
                    <Text size="lg" fw={700}>
                      {formatCurrency(costData?.monthly_cost || 0)}
                    </Text>
                  </div>
                }
              />
            </Center>

            <Stack gap="xs">
              {costData?.top_services.map((service, index) => (
                <Group key={service.service} justify="space-between">
                  <Group gap="xs">
                    <div
                      style={{
                        width: 12,
                        height: 12,
                        borderRadius: 2,
                        backgroundColor: ['#228be6', '#15aabf', '#9775fa', '#fd7e14', '#adb5bd'][index],
                      }}
                    />
                    <Text size="sm">{service.service}</Text>
                  </Group>
                  <Group gap="xs">
                    <Text size="sm" fw={500}>
                      {formatCurrency(service.cost)}
                    </Text>
                    <Text size="xs" c="dimmed">
                      ({service.percentage.toFixed(1)}%)
                    </Text>
                  </Group>
                </Group>
              ))}
            </Stack>
          </Stack>
        </Card>

        {/* Optimization Recommendations */}
        <Card>
          <Stack>
            <Title order={4}>Optimization Recommendations</Title>

            <Stack gap="md">
              <Paper p="md" withBorder style={{ borderLeft: '3px solid #fd7e14' }}>
                <Group justify="space-between" mb="xs">
                  <Text fw={600} size="sm">Underutilized EC2 Instances</Text>
                  <Badge color="orange">High Impact</Badge>
                </Group>
                <Text size="xs" c="dimmed" mb="sm">
                  5 instances running at &lt;20% CPU utilization
                </Text>
                <Group justify="space-between">
                  <Text size="sm" c="green" fw={500}>
                    Potential savings: {formatCurrency(456.78)}/mo
                  </Text>
                  <Button size="xs" variant="light" color="orange">
                    Review
                  </Button>
                </Group>
              </Paper>

              <Paper p="md" withBorder style={{ borderLeft: '3px solid #fab005' }}>
                <Group justify="space-between" mb="xs">
                  <Text fw={600} size="sm">Reserved Instance Opportunities</Text>
                  <Badge color="yellow">Medium Impact</Badge>
                </Group>
                <Text size="xs" c="dimmed" mb="sm">
                  3 instances eligible for RI discounts
                </Text>
                <Group justify="space-between">
                  <Text size="sm" c="green" fw={500}>
                    Potential savings: {formatCurrency(287.45)}/mo
                  </Text>
                  <Button size="xs" variant="light" color="yellow">
                    Review
                  </Button>
                </Group>
              </Paper>

              <Paper p="md" withBorder style={{ borderLeft: '3px solid #20c997' }}>
                <Group justify="space-between" mb="xs">
                  <Text fw={600} size="sm">S3 Lifecycle Policies</Text>
                  <Badge color="teal">Low Impact</Badge>
                </Group>
                <Text size="xs" c="dimmed" mb="sm">
                  Implement lifecycle rules for old data
                </Text>
                <Group justify="space-between">
                  <Text size="sm" c="green" fw={500}>
                    Potential savings: {formatCurrency(148.22)}/mo
                  </Text>
                  <Button size="xs" variant="light" color="teal">
                    Review
                  </Button>
                </Group>
              </Paper>
            </Stack>
          </Stack>
        </Card>
      </SimpleGrid>

      {/* Cost Trends (Placeholder) */}
      <Card>
        <Stack>
          <Title order={4}>Cost Trends</Title>
          <Text size="sm" c="dimmed">
            Historical cost analysis and projections coming soon...
          </Text>
          <Center h={200}>
            <Stack align="center" gap="sm">
              <IconChartBar size={48} stroke={1.5} color="gray" />
              <Text c="dimmed">Chart visualization in development</Text>
            </Stack>
          </Center>
        </Stack>
      </Card>

      {/* Resource Inventory (Placeholder) */}
      <Card>
        <Stack>
          <Group justify="space-between">
            <Title order={4}>Resource Inventory</Title>
            <Text size="sm" c="dimmed">Active cloud resources</Text>
          </Group>

          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Resource Type</Table.Th>
                <Table.Th>Count</Table.Th>
                <Table.Th>Monthly Cost</Table.Th>
                <Table.Th>Trend</Table.Th>
                <Table.Th>Optimization</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              <Table.Tr>
                <Table.Td>
                  <Text size="sm" fw={500}>EC2 Instances</Text>
                </Table.Td>
                <Table.Td>
                  <Badge variant="filled">12</Badge>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{formatCurrency(2134.45)}</Text>
                </Table.Td>
                <Table.Td>
                  <Group gap={4}>
                    <IconTrendingUp size={14} color="red" />
                    <Text size="xs" c="red">+15%</Text>
                  </Group>
                </Table.Td>
                <Table.Td>
                  <Tooltip label="5 rightsizing opportunities">
                    <Badge color="orange" variant="light">
                      Optimize
                    </Badge>
                  </Tooltip>
                </Table.Td>
              </Table.Tr>
              <Table.Tr>
                <Table.Td>
                  <Text size="sm" fw={500}>RDS Databases</Text>
                </Table.Td>
                <Table.Td>
                  <Badge variant="filled">4</Badge>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{formatCurrency(1234.56)}</Text>
                </Table.Td>
                <Table.Td>
                  <Group gap={4}>
                    <IconTrendingDown size={14} color="green" />
                    <Text size="xs" c="green">-3%</Text>
                  </Group>
                </Table.Td>
                <Table.Td>
                  <Badge color="green" variant="light">
                    Optimal
                  </Badge>
                </Table.Td>
              </Table.Tr>
              <Table.Tr>
                <Table.Td>
                  <Text size="sm" fw={500}>S3 Buckets</Text>
                </Table.Td>
                <Table.Td>
                  <Badge variant="filled">28</Badge>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{formatCurrency(678.90)}</Text>
                </Table.Td>
                <Table.Td>
                  <Group gap={4}>
                    <IconTrendingUp size={14} color="red" />
                    <Text size="xs" c="red">+8%</Text>
                  </Group>
                </Table.Td>
                <Table.Td>
                  <Tooltip label="Implement lifecycle policies">
                    <Badge color="yellow" variant="light">
                      Review
                    </Badge>
                  </Tooltip>
                </Table.Td>
              </Table.Tr>
            </Table.Tbody>
          </Table>
        </Stack>
      </Card>
    </Stack>
  );
};

export default FinOpsView;
