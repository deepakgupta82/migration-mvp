/**
 * Main Application Component - Professional Command Center
 * Implements routing and Mantine providers for the new UI architecture
 */

import React, { Suspense, lazy } from 'react';
// Import core Mantine styles - THIS IS THE FIX FOR THE LAYOUT
import '@mantine/core/styles.css';

import { MantineProvider } from '@mantine/core';
import { Notifications } from '@mantine/notifications';
import { ModalsProvider } from '@mantine/modals';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';

// Import new settings page components
import { LLMConfigurationPage } from './pages/settings/LLMConfigurationPage';
import { OAuthAuthenticationPage } from './pages/settings/OAuthAuthenticationPage';
import { UserManagementPage } from './pages/settings/UserManagementPage';
import { KnowledgeBasePage } from './pages/settings/KnowledgeBasePage';
import { EnvironmentVariablesPage } from './pages/settings/EnvironmentVariablesPage';
import { PlatformServicesPage } from './pages/settings/PlatformServicesPage';
import { AIAgentsPage } from './pages/settings/AIAgentsPage';
import { GlobalDocumentTemplatesPage } from './pages/settings/GlobalDocumentTemplatesPage';
import { ChunkingEmbeddingPage } from './pages/settings/ChunkingEmbeddingPage';
import ModelManager from './components/ModelManager';
import { NotificationProvider } from './contexts/NotificationContext';
import { AssessmentProvider } from './contexts/AssessmentContext';
import { LLMConfigProvider } from './contexts/LLMConfigContext';
import ErrorBoundary from './components/ErrorBoundary';

// Lazy load main views for better performance
const DashboardView = lazy(() => import('./views/DashboardView').then(module => ({ default: module.DashboardView })));
const ProjectsView = lazy(() => import('./views/ProjectsView').then(module => ({ default: module.ProjectsView })));
const ProjectDetailView = lazy(() => import('./views/ProjectDetailView').then(module => ({ default: module.ProjectDetailView })));
const SettingsView = lazy(() => import('./views/SettingsView').then(module => ({ default: module.SettingsView })));
const LogsView = lazy(() => import('./views/LogsView').then(module => ({ default: module.LogsView })));
const SystemLogsView = lazy(() => import('./views/SystemLogsView').then(module => ({ default: module.SystemLogsView })));
const CrewManagementView = lazy(() => import('./views/CrewManagementView').then(module => ({ default: module.CrewManagementView })));
const LessonsLearnedView = lazy(() => import('./views/LessonsLearnedView').then(module => ({ default: module.LessonsLearnedView })));

function App() {
  return (
    <ErrorBoundary>
    <MantineProvider
      theme={{
        primaryColor: 'corporate',
        fontFamily: '"Segoe UI", "Inter", -apple-system, BlinkMacSystemFont, Roboto, "Helvetica Neue", Arial, sans-serif',
        fontSizes: {
          xs: '11px',
          sm: '12px',
          md: '13px',
          lg: '15px',
          xl: '17px',
        },
        headings: {
          fontFamily: '"Segoe UI", "Inter", -apple-system, BlinkMacSystemFont, Roboto, "Helvetica Neue", Arial, sans-serif',
          fontWeight: '600',
          sizes: {
            h1: { fontSize: '28px', lineHeight: '1.2' },
            h2: { fontSize: '22px', lineHeight: '1.3' },
            h3: { fontSize: '18px', lineHeight: '1.4' },
            h4: { fontSize: '16px', lineHeight: '1.4' },
            h5: { fontSize: '14px', lineHeight: '1.5' },
            h6: { fontSize: '12px', lineHeight: '1.5' },
          },
        },
        colors: {
          // SharePoint-like Corporate Blue
          corporate: [
            '#f3f9ff', // Lightest
            '#e1f0ff',
            '#c7e4ff',
            '#a5d4ff',
            '#82c1ff',
            '#0072c6', // Primary SharePoint Blue
            '#005a9e',
            '#004578',
            '#003355',
            '#002233'  // Darkest
          ],
          // Professional Gray Scale
          gray: [
            '#fafafa', // Main app background
            '#f5f5f5',
            '#eeeeee',
            '#e0e0e0',
            '#bdbdbd',
            '#9e9e9e',
            '#757575',
            '#616161',
            '#424242',
            '#212121'
          ],
        },
        other: {
          // Custom design tokens
          borderRadius: {
            sm: '6px',
            md: '8px',
            lg: '12px',
            xl: '16px',
          },
          shadows: {
            subtle: '0 1px 3px rgba(0, 0, 0, 0.05)',
            soft: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
            medium: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
            strong: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
          },
        },
        components: {
          Card: {
            defaultProps: {
              shadow: 'sm',
              radius: 'md',
              withBorder: true,
            },
            styles: {
              root: {
                backgroundColor: '#ffffff',
                border: '1px solid #e1e5e9',
                boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)',
                transition: 'all 0.2s ease',
                '&:hover': {
                  boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
                  borderColor: '#0072c6',
                },
              },
            },
          },
          Button: {
            defaultProps: {
              radius: 'md',
            },
            styles: {
              root: {
                fontWeight: 500,
                fontSize: '14px',
                transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                '&:hover': {
                  transform: 'translateY(-1px)',
                },
              },
            },
          },
          Modal: {
            styles: {
              content: {
                borderRadius: '16px',
                boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
              },
              header: {
                backgroundColor: '#fafafa',
                borderBottom: '1px solid #f0f0f0',
                borderRadius: '16px 16px 0 0',
                padding: '20px 24px',
              },
              body: {
                padding: '24px',
              },
            },
          },
          Table: {
            styles: {
              root: {
                backgroundColor: '#ffffff',
                borderRadius: '8px',
                overflow: 'hidden',
                border: '1px solid #f0f0f0',
                '& thead tr th': {
                  backgroundColor: '#fafafa',
                  fontWeight: 600,
                  fontSize: '13px',
                  color: '#374151',
                  borderBottom: '1px solid #f0f0f0',
                  padding: '16px',
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px',
                },
                '& tbody tr': {
                  transition: 'background-color 0.15s ease',
                  '&:hover': {
                    backgroundColor: '#fafafa',
                  },
                  '& td': {
                    padding: '16px',
                    borderBottom: '1px solid #f5f5f5',
                  },
                },
              },
            },
          },
          NavLink: {
            styles: {
              root: {
                borderRadius: '4px',
                fontWeight: 500,
                fontSize: '14px',
                padding: '8px 12px',
                position: 'relative',
                transition: 'all 0.15s ease',
                '&[data-active]': {
                  backgroundColor: '#f3f9ff',
                  color: '#0072c6',
                  fontWeight: 600,
                  borderLeft: '3px solid #0072c6',
                  paddingLeft: '9px', // Adjust for border
                },
                '&:hover:not([data-active])': {
                  backgroundColor: '#f5f5f5',
                },
              },
            },
          },
          Badge: {
            styles: {
              root: {
                fontWeight: 500,
                fontSize: '12px',
                textTransform: 'none',
              },
            },
          },
        },
      }}
    >
      <ModalsProvider>
        <NotificationProvider>
          <LLMConfigProvider>
            <AssessmentProvider>
            <Notifications position="top-right" />
            <Router>
            <AppLayout>
              <Suspense fallback={
                <div style={{
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  height: '400px',
                  flexDirection: 'column',
                  gap: '16px'
                }}>
                  <div style={{
                    width: '40px',
                    height: '40px',
                    border: '4px solid #e1e5e9',
                    borderTop: '4px solid #0072c6',
                    borderRadius: '50%',
                    animation: 'spin 1s linear infinite'
                  }} />
                  <div style={{ color: '#666', fontSize: '14px' }}>Loading...</div>
                </div>
              }>
                <Routes>
                  <Route path="/" element={<DashboardView />} />
                  <Route path="/projects" element={<ProjectsView />} />
                  <Route path="/projects/:projectId" element={<ProjectDetailView />} />
                  <Route path="/logs" element={<LogsView />} />
                  <Route path="/system-logs" element={<SystemLogsView />} />
                  <Route path="/lessons-learned" element={<LessonsLearnedView />} />

                  {/* Legacy Settings Route - Redirect to first settings page */}
                  <Route path="/settings" element={<LLMConfigurationPage />} />
                  <Route path="/settings/agents" element={<CrewManagementView />} />

                  {/* New Settings Pages - Each former tab becomes a full page */}
                  <Route path="/settings/llm-configuration" element={<LLMConfigurationPage />} />
                  <Route path="/settings/oauth-authentication" element={<OAuthAuthenticationPage />} />
                  <Route path="/settings/user-management" element={<UserManagementPage />} />
                  <Route path="/settings/knowledge-base" element={<KnowledgeBasePage />} />
                  <Route path="/settings/environment-variables" element={<EnvironmentVariablesPage />} />
                  <Route path="/settings/platform-services" element={<PlatformServicesPage />} />
                  <Route path="/settings/ai-agents" element={<AIAgentsPage />} />
                  <Route path="/settings/global-templates" element={<GlobalDocumentTemplatesPage />} />
                  <Route path="/settings/chunking-embedding" element={<ChunkingEmbeddingPage />} />
                  <Route path="/settings/model-manager" element={<ModelManager />} />
                </Routes>
              </Suspense>
            </AppLayout>
          </Router>
            </AssessmentProvider>
          </LLMConfigProvider>
        </NotificationProvider>
      </ModalsProvider>
    </MantineProvider>
    </ErrorBoundary>
  );
}

export default App;
