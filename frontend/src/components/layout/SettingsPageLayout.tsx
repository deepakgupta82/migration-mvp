/**
 * Settings Page Layout - Consistent layout for all settings pages
 * Provides breadcrumbs, page header, and content area
 */

import React, { ReactNode } from 'react';
import {
  Container,
  Title,
  Paper,
  Group,
  Text,
  Breadcrumbs,
  Anchor,
  Stack,
  Box,
  ActionIcon,
} from '@mantine/core';
import { Link } from 'react-router-dom';
import { IconArrowLeft } from '@tabler/icons-react';

interface SettingsPageLayoutProps {
  title: string;
  description: string;
  icon: ReactNode;
  children: ReactNode;
  breadcrumbText: string;
  actions?: ReactNode;
  showBackButton?: boolean;
}

export const SettingsPageLayout: React.FC<SettingsPageLayoutProps> = ({
  title,
  description,
  icon,
  children,
  breadcrumbText,
  actions,
  showBackButton = false,
}) => {
  return (
    <Container fluid>
      {/* Consistent breadcrumbs following platform convention */}
      <Breadcrumbs mb="md" separator="›">
        <Anchor component={Link} to="/" size="sm">
          Dashboard
        </Anchor>
        <Text size="sm" c="dimmed">
          Settings
        </Text>
        <Text size="sm">{breadcrumbText}</Text>
      </Breadcrumbs>

      <Stack gap="lg">
        {/* Consistent page header */}
        <Group justify="space-between" align="center">
          <Group gap="sm" align="center">
            {showBackButton && (
              <ActionIcon
                variant="subtle"
                component={Link}
                to="/settings/llm-configuration"
                aria-label="Back to settings"
              >
                <IconArrowLeft size="1rem" />
              </ActionIcon>
            )}
            {icon}
            <Title order={2}>{title}</Title>
          </Group>

          {actions && <Box>{actions}</Box>}
        </Group>

        <Text size="sm" c="dimmed">
          {description}
        </Text>

        {/* Page content */}
        <Paper shadow="sm" p="xl" radius="md">
          {children}
        </Paper>
      </Stack>
    </Container>
  );
};
