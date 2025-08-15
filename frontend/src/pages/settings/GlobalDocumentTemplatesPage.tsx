/**
 * Global Document Templates Page - Full page for template settings
 */

import React from 'react';
import { IconFileText } from '@tabler/icons-react';
import { SettingsPageLayout } from '../../components/layout/SettingsPageLayout';
import GlobalDocumentTemplates from '../../components/settings/GlobalDocumentTemplates';

export const GlobalDocumentTemplatesPage: React.FC = () => {
  return (
    <SettingsPageLayout
      title="Global Document Templates"
      description="Manage document templates used across the platform for reports, assessments, and documentation."
      icon={<IconFileText size="1.5rem" />}
      breadcrumbText="Global Document Templates"
    >
      <GlobalDocumentTemplates />
    </SettingsPageLayout>
  );
};
