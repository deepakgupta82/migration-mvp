import React, { useEffect, useMemo, useState } from 'react';
import { Card, Stack, Group, Text, Button, Divider, Table, Loader, TextInput, Textarea, Badge, Grid, Alert, ActionIcon, Modal } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconCheck, IconEdit, IconPlus, IconRefresh, IconX } from '@tabler/icons-react';

type PromptDoc = {
  id: string;
  service: string;
  purpose?: string;
  description?: string;
  variables?: string[];
  text: string;
  version?: number;
  updated_by?: string;
  updated_at?: string;
  metadata?: Record<string, any>;
};

const API_BASE = 'http://localhost:8000';

export default function PromptManagementPanel() {
  const [loadingServices, setLoadingServices] = useState(false);
  const [services, setServices] = useState<string[]>([]);
  const [selectedService, setSelectedService] = useState<string>('');

  const [loadingPrompts, setLoadingPrompts] = useState(false);
  const [prompts, setPrompts] = useState<PromptDoc[]>([]);
  const [selectedPromptId, setSelectedPromptId] = useState<string>('');

  const [editorDoc, setEditorDoc] = useState<PromptDoc | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [saving, setSaving] = useState(false);
  const [validateErrors, setValidateErrors] = useState<string[]>([]);
  const [editorOpen, setEditorOpen] = useState(false);

  // Load services on mount
  useEffect(() => {
    const load = async () => {
      setLoadingServices(true);
      try {
        const res = await fetch(`${API_BASE}/api/prompts/services`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setServices(data.services || []);
        if ((data.services || []).length > 0) {
          setSelectedService((data.services || [])[0]);
        }
      } catch (e: any) {
        notifications.show({ title: 'Failed to load services', message: e.message || String(e), color: 'red' });
      } finally {
        setLoadingServices(false);
      }
    };
    load();
  }, []);

  // Load prompts when service changes
  useEffect(() => {
    if (!selectedService) return;
    const loadPrompts = async () => {
      setLoadingPrompts(true);
      try {
        const res = await fetch(`${API_BASE}/api/prompts/${encodeURIComponent(selectedService)}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setPrompts(data.prompts || []);
        setSelectedPromptId('');
        setEditorDoc(null);
        setIsNew(false);
      } catch (e: any) {
        notifications.show({ title: 'Failed to load prompts', message: e.message || String(e), color: 'red' });
      } finally {
        setLoadingPrompts(false);
      }
    };
    loadPrompts();
  }, [selectedService]);

  // Load a specific prompt doc
  const loadPromptDoc = async (service: string, id: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/prompts/${encodeURIComponent(service)}/${encodeURIComponent(id)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setEditorDoc(data);
      setSelectedPromptId(id);
      setIsNew(false);
      setValidateErrors([]);
      setEditorOpen(true);
    } catch (e: any) {
      notifications.show({ title: 'Failed to load prompt', message: e.message || String(e), color: 'red' });
    }
  };

  // Create new prompt skeleton
  const createNewPrompt = () => {
    if (!selectedService) return;
    const skeleton: PromptDoc = {
      id: '',
      service: selectedService,
      purpose: '',
      description: '',
      variables: [],
      text: ''
    };
    setEditorDoc(skeleton);
    setSelectedPromptId('');
    setIsNew(true);
    setValidateErrors([]);
    setEditorOpen(true);
  };

  // Validate a doc with backend
  const validateDoc = async (doc: PromptDoc): Promise<string[]> => {
    try {
      const res = await fetch(`${API_BASE}/api/prompts/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(doc)
      });
      const data = await res.json();
      if (res.ok) {
        return data.valid ? [] : (data.errors || []);
      }
      return (data.errors || [data.detail || 'Validation failed']);
    } catch (e: any) {
      return [e.message || String(e)];
    }
  };

  // Save and reload service
  const handleSave = async () => {
    if (!editorDoc) return;
    const doc: PromptDoc = {
      ...editorDoc,
      id: (editorDoc.id || '').trim(),
      service: selectedService,
      variables: (editorDoc.variables || []).filter(v => !!v).map(v => String(v).trim()),
      updated_by: 'ui'
    };

    // Basic client validation
    const basicErrors: string[] = [];
    if (!doc.id) basicErrors.push('Id is required');
    if (!doc.text || !doc.text.trim()) basicErrors.push('Text is required');
    if (basicErrors.length > 0) {
      setValidateErrors(basicErrors);
      return;
    }

    setSaving(true);
    setValidateErrors([]);
    try {
      const vErrors = await validateDoc(doc);
      if (vErrors.length > 0) {
        setValidateErrors(vErrors);
        setSaving(false);
        return;
      }

      const url = `${API_BASE}/api/prompts/${encodeURIComponent(doc.service)}/${encodeURIComponent(doc.id)}`;
      const res = await fetch(url, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(doc)
      });

      if (!res.ok) {
        let msg = `HTTP ${res.status}`;
        try { const j = await res.json(); msg = j.detail?.errors?.join(', ') || j.detail || msg; } catch {}
        throw new Error(msg);
      }

      // Reload the service cache
      const reloadRes = await fetch(`${API_BASE}/api/prompts/${encodeURIComponent(doc.service)}/reload`, { method: 'POST' });
      const reloadOk = reloadRes.ok;

      notifications.show({
        title: 'Prompt saved',
        message: reloadOk ? 'Service cache reloaded successfully.' : 'Saved. Reload request failed; service will pick up on restart.',
        color: reloadOk ? 'green' : 'yellow',
        icon: reloadOk ? <IconCheck size={16} /> : undefined
      });

      // Refresh list and selection
      // Re-fetch prompt list
      const listRes = await fetch(`${API_BASE}/api/prompts/${encodeURIComponent(doc.service)}`);
      if (listRes.ok) {
        const data = await listRes.json();
        setPrompts(data.prompts || []);
      }
      setIsNew(false);
      setSelectedPromptId(doc.id);
      setEditorDoc(doc);
      setEditorOpen(false);
    } catch (e: any) {
      notifications.show({ title: 'Save failed', message: e.message || String(e), color: 'red', icon: <IconX size={16} /> });
    } finally {
      setSaving(false);
    }
  };

  const selectedPromptSummary = useMemo(() => {
    if (!selectedPromptId) return null;
    const p = prompts.find(x => x.id === selectedPromptId);
    return p || null;
  }, [selectedPromptId, prompts]);

  return (
    <Card shadow="sm" p="lg" radius="md" withBorder>
      <Stack gap="lg">
        <Group justify="space-between">
          <div>
            <Text size="lg" fw={600}>LLM Prompts</Text>
            <Text size="sm" c="dimmed">View and edit the prompt templates used by backend services. Changes are saved to code (JSON) and auto-committed.</Text>
          </div>
          <Group>
            <Button variant="light" leftSection={<IconRefresh size={16} />} onClick={() => {
              // reload current service list
              setSelectedService('');
              setEditorDoc(null);
              setSelectedPromptId('');
              setIsNew(false);
              setLoadingServices(true);
              fetch(`${API_BASE}/api/prompts/services`).then(r => r.json()).then(d => {
                setServices(d.services || []);
                if ((d.services || []).length > 0) setSelectedService((d.services || [])[0]);
              }).finally(() => setLoadingServices(false));
            }}>Refresh</Button>
            {selectedService && (
              <Button leftSection={<IconPlus size={16} />} onClick={createNewPrompt} color="blue" variant="outline">New Prompt</Button>
            )}
          </Group>
        </Group>

        <Divider />

        <Grid gutter="md">
          {/* Services List */}
          <Grid.Col span={{ base: 12, md: 2 }}>
            <Card withBorder p="sm">
              <Stack gap="sm">
                <Group justify="space-between">
                  <Text fw={600}>Services</Text>
                  {loadingServices && <Loader size="xs" />}
                </Group>
                <Stack gap={6}>
                  {services.map((svc) => (
                    <Button key={svc} size="xs" variant={svc === selectedService ? 'filled' : 'light'} color={svc === selectedService ? 'blue' : 'gray'} onClick={() => setSelectedService(svc)}>
                      {svc}
                    </Button>
                  ))}
                  {services.length === 0 && !loadingServices && (
                    <Alert color="yellow" variant="light">
                      No services with prompts found. Ensure prompt JSON files exist under services/&lt;service&gt;/prompts.
                    </Alert>
                  )}
                </Stack>
              </Stack>
            </Card>
          </Grid.Col>

          {/* Prompts List */}
          <Grid.Col span={{ base: 12, md: 10 }}>
            <Card withBorder p="sm">
              <Stack gap="sm">
                <Group justify="space-between">
                  <Text fw={600}>Prompts {selectedService ? <Badge ml={6} variant="light">{selectedService}</Badge> : null}</Text>
                  {loadingPrompts && <Loader size="xs" />}
                </Group>
                {prompts.length === 0 && !loadingPrompts ? (
                  <Alert color="blue" variant="light">
                    {selectedService ? 'No prompts yet. Click "New Prompt" to add one.' : 'Select a service to view prompts.'}
                  </Alert>
                ) : (
                  <Table striped highlightOnHover>
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th>ID</Table.Th>
                        <Table.Th>Purpose</Table.Th>
                        <Table.Th>Description</Table.Th>
                        <Table.Th></Table.Th>
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {prompts.map((p) => (
                        <Table.Tr key={p.id}>
                          <Table.Td><Text fw={500}>{p.id}</Text></Table.Td>
                          <Table.Td>{p.purpose || '-'}</Table.Td>
                          <Table.Td>
                            <Text size="sm" c="dimmed" lineClamp={2}>{p.description || '-'}</Text>
                          </Table.Td>
                          <Table.Td>
                            <ActionIcon variant="subtle" color="blue" onClick={() => loadPromptDoc(p.service, p.id)}>
                              <IconEdit size={16} />
                            </ActionIcon>
                          </Table.Td>
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                )}
              </Stack>
            </Card>
          </Grid.Col>
        </Grid>

        {/* Modal Editor */}
        <Modal opened={editorOpen} onClose={() => setEditorOpen(false)} title={isNew ? 'Create Prompt' : `Edit Prompt${selectedPromptSummary ? ` • v${selectedPromptSummary.version ?? 1}` : ''}`} size="70%">
          {!editorDoc ? (
            <Alert color="gray" variant="light">Select a prompt to edit, or create a new one.</Alert>
          ) : (
            <Stack gap="sm">
              <Group grow>
                <TextInput
                  label="ID"
                  placeholder="unique_id"
                  value={editorDoc.id}
                  onChange={(e) => setEditorDoc({ ...editorDoc, id: e.currentTarget.value })}
                  disabled={!isNew}
                  required
                />
                <TextInput label="Service" value={selectedService} disabled />
              </Group>
              <TextInput
                label="Purpose"
                placeholder="Short purpose of this prompt"
                value={editorDoc.purpose || ''}
                onChange={(e) => setEditorDoc({ ...editorDoc, purpose: e.currentTarget.value })}
              />
              <TextInput
                label="Description"
                placeholder="Longer description of when/how this prompt is used"
                value={editorDoc.description || ''}
                onChange={(e) => setEditorDoc({ ...editorDoc, description: e.currentTarget.value })}
              />
              <TextInput
                label="Variables (comma-separated)"
                placeholder="e.g. project_id, template_guidance, context_snippets"
                value={(editorDoc.variables || []).join(', ')}
                onChange={(e) => setEditorDoc({ ...editorDoc, variables: e.currentTarget.value.split(',').map(s => s.trim()).filter(Boolean) })}
              />
              <Textarea
                label="Prompt Text"
                description="Use {{variable}} placeholders."
                autosize
                minRows={12}
                value={editorDoc.text}
                onChange={(e) => setEditorDoc({ ...editorDoc, text: e.currentTarget.value })}
                required
              />
              {validateErrors.length > 0 && (
                <Alert color="red" variant="light">
                  <Stack gap={4}>
                    {validateErrors.map((er, idx) => (
                      <Text key={idx} size="sm">• {er}</Text>
                    ))}
                  </Stack>
                </Alert>
              )}
              <Group justify="flex-end">
                <Button variant="default" onClick={() => setEditorOpen(false)}>Cancel</Button>
                <Button onClick={handleSave} loading={saving} leftSection={<IconCheck size={16} />} color="green">
                  {saving ? 'Saving...' : 'Save & Reload'}
                </Button>
              </Group>
            </Stack>
          )}
        </Modal>
      </Stack>
    </Card>
  );
}
