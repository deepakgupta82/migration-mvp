import React, { useEffect, useState } from 'react';
import { Card, Stack, Group, Text, Button, Textarea, Badge, Loader, Alert } from '@mantine/core';
import { IconCheck, IconCloudUpload, IconRefresh, IconAlertCircle } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';

type LatestOntology = {
  version: string;
  created_at: number;
  ontology_json: any;
};

const pretty = (obj: any) => JSON.stringify(obj, null, 2);

const OntologyEditor: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [version, setVersion] = useState<string | null>(null);
  const [createdAt, setCreatedAt] = useState<number | null>(null);
  const [rawText, setRawText] = useState('');
  const [error, setError] = useState<string | null>(null);

  const loadLatest = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('http://localhost:8006/api/ontology');
      if (res.status === 404) {
        // Initialize with empty template
        const template = { entities: [], relationships: [] };
        setVersion(null);
        setCreatedAt(null);
        setRawText(pretty(template));
      } else if (res.ok) {
        const data: LatestOntology = await res.json();
        setVersion(data.version);
        setCreatedAt(data.created_at);
        setRawText(pretty(data.ontology_json));
      } else {
        const t = await res.text();
        throw new Error(`Failed to load ontology: ${res.status} ${t}`);
      }
    } catch (e: any) {
      setError(e.message || String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLatest();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      let payload: any;
      try {
        payload = JSON.parse(rawText);
      } catch (e: any) {
        throw new Error(`Invalid JSON: ${e.message}`);
      }
      if (!payload || typeof payload !== 'object') {
        throw new Error('Ontology must be a JSON object');
      }
      if (!Array.isArray(payload.entities) || !Array.isArray(payload.relationships)) {
        throw new Error('Ontology must have arrays: entities[], relationships[]');
      }

      const res = await fetch('http://localhost:8006/api/ontology', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const txt = await res.text();
        throw new Error(`Save failed: ${res.status} ${txt}`);
      }
      const saved = await res.json();
      setVersion(saved.version);
      setCreatedAt(saved.created_at);
      notifications.show({
        title: 'Ontology saved',
        message: `Version ${saved.version} created`,
        color: 'green',
        icon: <IconCheck size={16} />,
      });
    } catch (e: any) {
      setError(e.message || String(e));
      notifications.show({ title: 'Save error', message: e.message || String(e), color: 'red' });
    } finally {
      setSaving(false);
    }
  };

  const defaultPlaceholder = '{\n  "entities": [],\n  "relationships": []\n}';

  return (
    <Card shadow="sm" p="lg" radius="md" withBorder>
      <Stack gap="md">
        <Group justify="space-between">
          <div>
            <Text size="lg" fw={600}>Ontology Editor</Text>
            <Text size="sm" c="dimmed">Edit the platform ontology used for entity/relationship extraction</Text>
          </div>
          <Group gap="xs">
            {version && (
              <Badge color="blue" variant="light">v{version}</Badge>
            )}
            {createdAt && (
              <Badge color="gray" variant="outline">{new Date(createdAt * 1000).toLocaleString()}</Badge>
            )}
          </Group>
        </Group>

        {error && (
          <Alert icon={<IconAlertCircle size={16} />} color="red" variant="light">{error}</Alert>
        )}

        <Textarea
          autosize
          minRows={16}
          styles={{ input: { fontFamily: 'monospace' } }}
          value={rawText}
          onChange={(e) => setRawText(e.currentTarget.value)}
          placeholder={defaultPlaceholder}
        />

        <Group justify="flex-end">
          <Button variant="light" leftSection={<IconRefresh size={16} />} onClick={loadLatest} disabled={loading}>
            {loading ? (<Group gap={6}><Loader size="xs" /> <Text size="sm">Loading…</Text></Group>) : 'Reload'}
          </Button>
          <Button color="green" leftSection={<IconCloudUpload size={16} />} onClick={save} disabled={saving}>
            {saving ? 'Saving…' : 'Save New Version'}
          </Button>
        </Group>
      </Stack>
    </Card>
  );
};

export default OntologyEditor;
