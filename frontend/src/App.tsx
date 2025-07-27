/**
 * Main Application Component - Professional Command Center
 * Implements routing and Mantine providers for the new UI architecture
 */

import React from 'react';
import { MantineProvider } from '@mantine/core';
import { Notifications } from '@mantine/notifications';
import { ModalsProvider } from '@mantine/modals';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { DashboardView } from './views/DashboardView';
import { ProjectsView } from './views/ProjectsView';
import { ProjectDetailView } from './views/ProjectDetailView';

function App() {
  return (
    <MantineProvider
      theme={{
        primaryColor: 'blue',
        fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif',
        headings: {
          fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif',
        },
        colors: {
          brand: [
            '#e3f2fd',
            '#bbdefb',
            '#90caf9',
            '#64b5f6',
            '#42a5f5',
            '#2196f3',
            '#1e88e5',
            '#1976d2',
            '#1565c0',
            '#0d47a1'
          ],
        },
        components: {
          Card: {
            styles: {
              root: {
                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
                border: '1px solid #e5e7eb',
                borderRadius: '12px',
                transition: 'all 0.2s ease-in-out',
                '&:hover': {
                  boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
                  transform: 'translateY(-1px)',
                },
              },
            },
          },
          Button: {
            styles: {
              root: {
                fontWeight: 600,
                borderRadius: '8px',
                transition: 'all 0.2s ease-in-out',
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
            },
          },
          Table: {
            styles: {
              root: {
                '& thead tr th': {
                  backgroundColor: '#f8fafc',
                  fontWeight: 600,
                  color: '#374151',
                  borderBottom: '2px solid #e5e7eb',
                },
                '& tbody tr': {
                  transition: 'background-color 0.2s ease-in-out',
                  '&:hover': {
                    backgroundColor: '#f9fafb',
                  },
                },
              },
            },
          },
        },
      }}
    >
      <ModalsProvider>
        <Notifications position="top-right" />
        <Router>
          <AppLayout>
            <Routes>
              <Route path="/" element={<DashboardView />} />
              <Route path="/projects" element={<ProjectsView />} />
              <Route path="/projects/:projectId" element={<ProjectDetailView />} />
              <Route path="/settings" element={<div>Settings coming soon...</div>} />
            </Routes>
          </AppLayout>
        </Router>
      </ModalsProvider>
    </MantineProvider>
  );
}

export default App;
