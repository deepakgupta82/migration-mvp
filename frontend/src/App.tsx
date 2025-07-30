/**
 * Main Application Component - Professional Command Center
 * Implements routing and Mantine providers for the new UI architecture
 */

import React from 'react';
// Import core Mantine styles - THIS IS THE FIX FOR THE LAYOUT
import '@mantine/core/styles.css';

import { MantineProvider } from '@mantine/core';
import { Notifications } from '@mantine/notifications';
import { ModalsProvider } from '@mantine/modals';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { DashboardView } from './views/DashboardView';
import { ProjectsView } from './views/ProjectsView';
import { ProjectDetailView } from './views/ProjectDetailView';
import { SettingsView } from './views/SettingsView';
import { LogsView } from './views/LogsView';
import { NotificationProvider } from './contexts/NotificationContext';
import { AssessmentProvider } from './contexts/AssessmentContext';

function App() {
  return (
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
          <AssessmentProvider>
          <Notifications position="top-right" />
          <Router>
            <AppLayout>
              <Routes>
                <Route path="/" element={<DashboardView />} />
                <Route path="/projects" element={<ProjectsView />} />
                <Route path="/projects/:projectId" element={<ProjectDetailView />} />
                <Route path="/logs" element={<LogsView />} />
                <Route path="/settings" element={<SettingsView />} />
              </Routes>
            </AppLayout>
          </Router>
          </AssessmentProvider>
        </NotificationProvider>
      </ModalsProvider>
    </MantineProvider>
  );
}

export default App;
