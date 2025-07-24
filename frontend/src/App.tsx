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
        components: {
          Card: {
            styles: {
              root: {
                boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05), 0 1px 2px rgba(0, 0, 0, 0.1)',
              },
            },
          },
          Button: {
            styles: {
              root: {
                fontWeight: 500,
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
