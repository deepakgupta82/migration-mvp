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
    <Container fluid p={0}>
      {/* Breadcrumbs integrated with page header - no separate section */}
      <Stack gap="xs" mb="md">
        {/* Breadcrumbs next to page name */}
        <Group gap="xs" align="center">
          <Breadcrumbs separator="›">
            <Anchor component={Link} to="/" size="sm" c="dimmed">
              Dashboard
            </Anchor>
            <Text size="sm" c="dimmed">
              Settings
            </Text>
          </Breadcrumbs>
          <Text size="sm" c="dimmed">›</Text>
          <Group gap="xs" align="center">
            {showBackButton && (
              <ActionIcon
                variant="subtle"
                size="sm"
                component={Link}
                to="/settings/llm-configuration"
                aria-label="Back to settings"
              >
                <IconArrowLeft size="0.9rem" />
              </ActionIcon>
            )}
            {icon}
            <Title order={2} size="h3">{title}</Title>
          </Group>
          {actions && (
            <Box ml="auto">
              {actions}
            </Box>
          )}
        </Group>

        {/* Purpose description directly below */}
        <Text size="sm" c="dimmed" ml="md">
          {description}
        </Text>
      </Stack>

      {/* Page content with minimal spacing */}
      <Paper shadow="sm" p="lg" radius="md">
        {children}
      </Paper>
    </Container>
  );
};
