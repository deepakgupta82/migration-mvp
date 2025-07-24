import React, { useState, useEffect } from 'react';
import { AppShell, Header, Container, Title, Tabs, Text, Paper, Group, Button, TextInput, Table, Badge, Stack } from '@mantine/core';
import FileUpload from './components/FileUpload';
import LiveConsole from './components/LiveConsole';
import ReportDisplay from './components/ReportDisplay';

interface Project {
  id: string;
  name: string;
  description: string;
  client_name: string;
  client_contact: string;
  status: string;
  created_at: string;
  updated_at: string;
}

function App() {
  const [activeTab, setActiveTab] = useState<string | null>('dashboard');
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [projectName, setProjectName] = useState<string>('');
  const [clientName, setClientName] = useState<string>('');
  const [projectDescription, setProjectDescription] = useState<string>('');
  const [clientContact, setClientContact] = useState<string>('');
  const [consoleOutput, setConsoleOutput] = useState<string[]>([]);
  const [finalReport, setFinalReport] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);

  // Fetch projects on component mount
  useEffect(() => {
    fetchProjects();
  }, []);

  const fetchProjects = async () => {
    try {
      // Use project-service directly via NodePort
      const response = await fetch('http://localhost:30802/projects');
      if (response.ok) {
        const data = await response.json();
        setProjects(data);
      }
    } catch (error) {
      console.error('Error fetching projects:', error);
    }
  };

  const handleCreateProject = async () => {
    if (!projectName || !clientName) {
      alert('Please fill in all required fields');
      return;
    }

    setLoading(true);
    try {
      // Use project-service directly via NodePort
      const response = await fetch('http://localhost:30802/projects', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: projectName,
          description: projectDescription,
          client_name: clientName,
          client_contact: clientContact,
        }),
      });

      if (response.ok) {
        const newProject = await response.json();
        setProjects([...projects, newProject]);
        setProjectName('');
        setClientName('');
        setProjectDescription('');
        setClientContact('');
        alert('Project created successfully!');
        setActiveTab('dashboard');
      } else {
        alert('Failed to create project');
      }
    } catch (error) {
      console.error('Error creating project:', error);
      alert('Error creating project');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AppShell
      header={
        <Header height={60} p="xs">
          <Title order={2}>Nagarro AgentiMigrate Platform</Title>
        </Header>
      }
    >
      <Container size="xl" mt="xl">
        <Tabs value={activeTab} onTabChange={setActiveTab}>
          <Tabs.List>
            <Tabs.Tab value="dashboard">Dashboard</Tabs.Tab>
            <Tabs.Tab value="create">Create Project</Tabs.Tab>
            <Tabs.Tab value="upload">File Upload</Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="dashboard" pt="xs">
            <Title order={3} mb="md">Project Dashboard</Title>
            <Paper shadow="xs" p="md">
              <Table>
                <thead>
                  <tr>
                    <th>Project Name</th>
                    <th>Client</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {projects.length === 0 ? (
                    <tr>
                      <td colSpan={5} style={{ textAlign: 'center' }}>
                        <Text>No projects found. Create your first project!</Text>
                      </td>
                    </tr>
                  ) : (
                    projects.map((project) => (
                      <tr key={project.id}>
                        <td>{project.name}</td>
                        <td>{project.client_name}</td>
                        <td>
                          <Badge color={project.status === 'completed' ? 'green' : project.status === 'running' ? 'yellow' : 'blue'}>
                            {project.status}
                          </Badge>
                        </td>
                        <td>{new Date(project.created_at).toLocaleDateString()}</td>
                        <td>
                          <Button
                            size="xs"
                            onClick={() => {
                              setSelectedProject(project);
                              setActiveTab('upload');
                            }}
                          >
                            Select
                          </Button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </Table>
            </Paper>
          </Tabs.Panel>

          <Tabs.Panel value="create" pt="xs">
            <Title order={3} mb="md">Create New Project</Title>
            <Paper shadow="xs" p="md">
              <Stack spacing="md">
                <TextInput
                  label="Project Name"
                  placeholder="Enter project name"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  required
                />
                <TextInput
                  label="Client Name"
                  placeholder="Enter client name"
                  value={clientName}
                  onChange={(e) => setClientName(e.target.value)}
                  required
                />
                <TextInput
                  label="Client Contact"
                  placeholder="Enter client contact email/phone"
                  value={clientContact}
                  onChange={(e) => setClientContact(e.target.value)}
                />
                <TextInput
                  label="Description"
                  placeholder="Enter project description"
                  value={projectDescription}
                  onChange={(e) => setProjectDescription(e.target.value)}
                />
                <Group>
                  <Button onClick={handleCreateProject} loading={loading}>
                    Create Project
                  </Button>
                  <Button variant="outline" onClick={() => setActiveTab('dashboard')}>
                    Cancel
                  </Button>
                </Group>
              </Stack>
            </Paper>
          </Tabs.Panel>

          <Tabs.Panel value="upload" pt="xs">
            <Title order={3} mb="md">File Upload & Assessment</Title>
            {selectedProject ? (
              <>
                <Paper shadow="xs" p="md" mb="md">
                  <Text size="sm" color="dimmed">Selected Project:</Text>
                  <Text weight={500}>{selectedProject.name} - {selectedProject.client_name}</Text>
                </Paper>
                <FileUpload projectId={selectedProject.id} />
              </>
            ) : (
              <Paper shadow="xs" p="md">
                <Text>Please select a project from the Dashboard first.</Text>
                <Button mt="md" onClick={() => setActiveTab('dashboard')}>Go to Dashboard</Button>
              </Paper>
            )}
          </Tabs.Panel>
        </Tabs>
      </Container>
    </AppShell>
  );
}

export default App;
