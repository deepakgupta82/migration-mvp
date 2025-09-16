import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Card, Group, Text, Badge, Textarea, Button, ScrollArea, Loader, Paper, MultiSelect, Divider, Stack, Tooltip, ActionIcon, Avatar, ThemeIcon, Input, Transition, Modal } from '@mantine/core';
import { IconSend, IconRefresh, IconBolt, IconPlayerPlay, IconTrash, IconMessageChatbot, IconChevronRight, IconSearch, IconSparkles, IconClock, IconInfoCircle } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';

interface DiscussionsTabProps { projectId: string; }

interface DiscussionMessage {
  id: string;
  session_id: string;
  ts: string;
  source: string;
  content: string;
  message_type?: string;
  agent_name?: string;
}

interface DiscussionSessionMeta {
  session_id: string;
  created_at?: string;
  last_updated?: string;
  message_count?: number;
  participating_agents?: string[];
  status?: string;
}

export const DiscussionsTab: React.FC<DiscussionsTabProps> = ({ projectId }) => {
  const [sessionId, setSessionId] = useState<string>('');
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<DiscussionMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [availableAgents, setAvailableAgents] = useState<{ value: string; label: string; description?: string }[]>([]);
  const [infoAgent, setInfoAgent] = useState<{ name: string; description: string } | null>(null);
  const [selectedAgents, setSelectedAgents] = useState<string[]>([]);
  const [sessions, setSessions] = useState<DiscussionSessionMeta[]>([]);
  const [fetchingSessions, setFetchingSessions] = useState(false);
  const [agentQuery, setAgentQuery] = useState('');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [agentTyping, setAgentTyping] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Auto-scroll
  useEffect(() => { if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight; }, [messages]);

  const baseUrl = 'http://localhost:8008/api/autogen';
  const wsBase = 'ws://localhost:8008/ws/autogen';

  const loadAgents = async () => {
    try {
      const res = await fetch(`${baseUrl}/agents`);
      const data = await res.json();
      if (data.available_agents) {
        setAvailableAgents(Object.entries<string>(data.available_agents).map(([k, v]) => ({ value: k, label: k, description: v })));
      }
    } catch (e) { console.warn('Failed to load agents', e); }
  };

  const loadSessions = async () => {
    setFetchingSessions(true);
    try {
      const res = await fetch(`${baseUrl}/conversations/history?limit=25`);
      const data = await res.json();
      if (data.sessions) setSessions(data.sessions);
    } catch (e) {
      console.warn('Failed to load sessions', e);
    } finally { setFetchingSessions(false); }
  };

  const openWebSocket = (sid: string) => {
    if (wsRef.current) { wsRef.current.close(); }
    const ws = new WebSocket(`${wsBase}/${sid}`);
    wsRef.current = ws;
    ws.onopen = () => { /* Optionally notify */ };
    ws.onmessage = (evt) => {
      try {
        const packet = JSON.parse(evt.data);
        if (packet.type === 'agent_responding') {
          setAgentTyping(packet.agent_name || 'agent');
        }
        if (packet.type === 'recommendation_received' || packet.type === 'action_item_received' || packet.type === 'agent_responding') {
          setMessages(prev => [...prev, {
            id: Math.random().toString(36).slice(2),
            session_id: sid,
            ts: new Date().toISOString(),
            source: packet.agent_name || packet.recommendation?.agent || packet.action_item?.agent || 'system',
            content: packet.message || packet.recommendation?.recommendation || packet.action_item?.action || '',
            message_type: packet.type
          }]);
          if (packet.type !== 'agent_responding') {
            setAgentTyping(null);
          }
        }
        if (packet.type === 'conversation_completed' && packet.result) {
          setMessages(prev => [...prev, ...(packet.result.full_conversation || []).map((m: any) => ({
            id: Math.random().toString(36).slice(2),
            session_id: sid,
            ts: m.timestamp,
            source: m.source,
            content: m.content,
            message_type: m.message_type
          }))]);
          setAgentTyping(null);
        }
      } catch { /* ignore */ }
    };
    ws.onerror = () => { /* ignore */ };
    ws.onclose = () => { wsRef.current = null; };
  };

  const startDiscussion = async () => {
    if (!input.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(`${baseUrl}/discussions/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: input, selected_agents: selectedAgents, project_id: projectId })
      });
      const data = await res.json();
      if (res.ok) {
        setSessionId(data.session_id);
        setMessages([]);
        notifications.show({ title: 'Discussion Started', message: `Session ${data.session_id}`, color: 'green' });
        openWebSocket(data.session_id);
      } else {
        notifications.show({ title: 'Start Failed', message: data.detail || 'Unknown error', color: 'red' });
      }
    } catch (e: any) {
      notifications.show({ title: 'Error', message: String(e), color: 'red' });
    } finally { setLoading(false); }
  };

  const sendFollowUp = async () => {
    if (!sessionId || !input.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(`${baseUrl}/discussions/${sessionId}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: input, session_id: sessionId, override_agents: selectedAgents, project_id: projectId })
      });
      const data = await res.json();
      if (res.ok) {
        notifications.show({ title: 'Message Sent', message: 'Follow-up processed', color: 'blue' });
      } else {
        notifications.show({ title: 'Send Failed', message: data.detail || 'Unknown error', color: 'red' });
      }
    } catch (e:any) {
      notifications.show({ title: 'Error', message: String(e), color: 'red' });
    } finally { setLoading(false); setInput(''); }
  };

  const loadSessionHistory = async (sid: string) => {
    setSessionId(sid);
    setMessages([]);
    try {
      const res = await fetch(`${baseUrl}/conversations/${sid}/history`);
      const data = await res.json();
      if (res.ok) {
        if (data.messages) {
          setMessages(data.messages.map((m: any) => ({
            id: String(m.id || Math.random()),
            session_id: sid,
            ts: m.ts || m.timestamp,
            source: m.source || m.agent_name || 'unknown',
            content: m.content,
            message_type: m.message_type
          })));
        }
        openWebSocket(sid);
      }
    } catch { /* ignore */ }
  };

  useEffect(() => { loadAgents(); loadSessions(); }, []);

  const filteredAgents = agentQuery
    ? availableAgents.filter(a => a.value.toLowerCase().includes(agentQuery.toLowerCase()) || (a.description || '').toLowerCase().includes(agentQuery.toLowerCase()))
    : availableAgents;

  const AgentSelectItem = React.forwardRef<HTMLDivElement, any>(({ value, label, description, ...others }, ref) => (
    <div ref={ref} {...others} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', padding: '4px 6px' }}>
      <Tooltip label={description || 'No description'} openDelay={400} withinPortal maw={320} multiline>
        <Text size="sm" style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>{label}</Text>
      </Tooltip>
      <Tooltip label="Agent info" openDelay={300} withinPortal>
        <ActionIcon
          size="sm"
          variant="subtle"
          aria-label={`Info about ${label}`}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setInfoAgent({ name: label, description: description || 'No description available.' });
          }}
        >
          <IconInfoCircle size={14} />
        </ActionIcon>
      </Tooltip>
    </div>
  ));
  AgentSelectItem.displayName = 'AgentSelectItem';

  // Render a single message bubble (restored after prior edit removed it)
  const renderMessage = useCallback((m: DiscussionMessage, idx: number) => {
    const isUser = m.source === 'user';
    const prev = messages[idx - 1];
    const showHeader = !prev || prev.source !== m.source;
    return (
      <div key={m.id} style={{ display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start' }} role="listitem" aria-label={`message from ${m.source}`}> 
        <div style={{ maxWidth: '70%', display: 'flex', flexDirection: isUser ? 'row-reverse' : 'row', gap: 8 }}>
          {showHeader && (
            <Avatar size={28} radius="xl" color={isUser ? 'blue' : 'gray'}>{(m.source || '?')[0]?.toUpperCase()}</Avatar>
          )}
          <Paper p={10} radius="lg" shadow="xs" style={{ background: isUser ? 'var(--mantine-color-blue-light)' : 'var(--mantine-color-gray-1)', border: '1px solid var(--mantine-color-gray-3)' }}>
            {showHeader && <Text size="xs" fw={600} mb={4}>{m.source}</Text>}
            <Text size="sm" style={{ whiteSpace: 'pre-wrap', lineHeight: 1.4 }}>{m.content}</Text>
            <Text size="10px" c="dimmed" mt={6} ta={isUser ? 'right' : 'left'}>{new Date(m.ts).toLocaleTimeString()}</Text>
          </Paper>
        </div>
      </div>
    );
  }, [messages]);

  const EmptyState = () => (
    <Stack align="center" justify="center" gap={4} mt="md" style={{ opacity: 0.7 }}>
      <ThemeIcon size={60} radius="xl" variant="light" color="blue"><IconMessageChatbot size={32} /></ThemeIcon>
      <Text size="sm" fw={500}>Start a migration discussion</Text>
      <Text size="xs" c="dimmed" ta="center" style={{ maxWidth: 300 }}>Pick agents, ask a question, and collaborate with specialist AI personas.</Text>
    </Stack>
  );

  return (
    <Group align="stretch" gap="md" wrap="nowrap" style={{ height: '70vh', position: 'relative' }}>
      <Modal opened={!!infoAgent} onClose={() => setInfoAgent(null)} title={infoAgent?.name} size="lg" radius="md" overlayProps={{ opacity: 0.15, blur: 2 }}>
        <ScrollArea.Autosize mah={320} type="auto" offsetScrollbars>
          <Text size="sm" style={{ lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>{infoAgent?.description}</Text>
        </ScrollArea.Autosize>
        <Group justify="flex-end" mt="md">
          <Button size="xs" variant="light" onClick={() => setInfoAgent(null)}>Close</Button>
        </Group>
      </Modal>
      <Transition mounted={!isSidebarCollapsed} transition="slide-right" duration={180} timingFunction="ease">
        {(styles) => (
          <Card withBorder shadow="sm" radius="lg" p="sm" style={{ width: 280, display: isSidebarCollapsed ? 'none' : 'flex', flexDirection: 'column', ...styles }}>
            <Group justify="space-between" mb="xs">
              <Text fw={600} size="sm">Agents</Text>
              <Group gap={4}>
                <ActionIcon size="sm" variant="subtle" aria-label="Refresh agents" onClick={loadAgents}><IconRefresh size={14} /></ActionIcon>
                <ActionIcon size="sm" variant="subtle" aria-label="Collapse sidebar" onClick={() => setIsSidebarCollapsed(true)}><IconChevronRight size={14} /></ActionIcon>
              </Group>
            </Group>
            <Input leftSection={<IconSearch size={14} />} placeholder="Search agents" value={agentQuery} onChange={e => setAgentQuery(e.currentTarget.value)} size="xs" mb={6} radius="md" />
            <MultiSelect
              data={filteredAgents}
              placeholder="Select agents"
              value={selectedAgents}
              onChange={setSelectedAgents}
              searchable
              maxDropdownHeight={260}
              radius="md"
              nothingFoundMessage="No agents"
              aria-label="Agents selector"
              hidePickedOptions
              renderOption={AgentSelectItem}
            />
            <Divider my={10} label="Sessions" labelPosition="center" />
            <ScrollArea h={220} offsetScrollbars>
              <Stack gap={6}>
                {fetchingSessions && <Loader size="xs" />}
                {sessions.map(s => {
                  const active = s.session_id === sessionId;
                  return (
                    <Paper key={s.session_id} p={8} radius="md" shadow={active ? 'sm' : 'xs'} withBorder style={{ cursor: 'pointer', background: active ? 'var(--mantine-color-blue-light)' : 'var(--mantine-color-gray-0)' }} onClick={() => loadSessionHistory(s.session_id)} aria-label={`Session ${s.session_id}`}> 
                      <Group justify="space-between" gap={4} wrap="nowrap">
                        <Text size="xs" fw={500} truncate style={{ maxWidth: 140 }}>{s.session_id.slice(0, 10)}...</Text>
                        <Tooltip label="Resume">
                          <ActionIcon size="xs" variant="light" color="blue"><IconPlayerPlay size={14} /></ActionIcon>
                        </Tooltip>
                      </Group>
                      <Group gap={6} mt={6} wrap="nowrap">
                        <Badge size="xs" color="blue" variant="light" leftSection={<IconMessageChatbot size={10} />}>{s.message_count || 0}</Badge>
                        {s.participating_agents?.slice(0, 2).map(a => {
                          const info = availableAgents.find(ag => ag.value === a);
                          return (
                            <Group key={a} gap={2} wrap="nowrap">
                              <Badge
                                size="xs"
                                variant="outline"
                                color="gray"
                                style={{ cursor: 'pointer' }}
                                onClick={() => setInfoAgent({ name: a, description: info?.description || 'No description available.' })}
                                title="Click for agent info"
                              >
                                {a.split('_')[0]}
                              </Badge>
                              <ActionIcon
                                size="xs"
                                variant="subtle"
                                aria-label={`Info about ${a}`}
                                onClick={() => setInfoAgent({ name: a, description: info?.description || 'No description available.' })}
                              >
                                <IconInfoCircle size={12} />
                              </ActionIcon>
                            </Group>
                          );
                        })}
                        {s.created_at && <Group gap={2} c="dimmed"><IconClock size={10} /><Text size="9px">{new Date(s.created_at).toLocaleTimeString()}</Text></Group>}
                      </Group>
                    </Paper>
                  );
                })}
              </Stack>
            </ScrollArea>
            <Divider my={10} />
            <Stack gap={6} mt="auto">
              <Button size="xs" radius="md" leftSection={<IconBolt size={14} />} loading={loading} onClick={startDiscussion} disabled={!input.trim()} aria-label="Start discussion">Start</Button>
              <Button size="xs" radius="md" variant="outline" leftSection={<IconPlayerPlay size={14} />} onClick={sendFollowUp} disabled={!sessionId || !input.trim() || loading} aria-label="Send follow-up">Send</Button>
              <Button size="xs" radius="md" color="red" variant="subtle" leftSection={<IconTrash size={14} />} onClick={() => { setSessionId(''); setMessages([]); }} aria-label="Clear session">Clear</Button>
            </Stack>
          </Card>
        )}
      </Transition>
      {isSidebarCollapsed && (
        <ActionIcon variant="light" radius="xl" style={{ position: 'absolute', left: 4, top: 4, zIndex: 10 }} onClick={() => setIsSidebarCollapsed(false)} aria-label="Expand sidebar">
          <IconChevronRight size={16} style={{ transform: 'rotate(180deg)' }} />
        </ActionIcon>
      )}
      <Card withBorder shadow="sm" radius="lg" p="sm" style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <Group justify="space-between" mb="xs">
          <Group gap={8}>
            <Text fw={600} size="sm">Discussion</Text>
            {sessionId && <Badge size="xs" variant="outline">{sessionId.slice(0, 8)}</Badge>}
          </Group>
          <Group gap={6}>
            {agentTyping && <Group gap={4} c="dimmed" style={{ fontSize: 11 }}><IconSparkles size={14} /> <span>{agentTyping} typing...</span></Group>}
            {loading && <Loader size="xs" />}
          </Group>
        </Group>
        <Paper withBorder radius="md" p="sm" style={{ flex: 1, display: 'flex', flexDirection: 'column', background: 'var(--mantine-color-gray-0)', position: 'relative' }}>
          <ScrollArea viewportRef={scrollRef} style={{ flex: 1 }} offsetScrollbars type="hover">
            <div style={{ padding: '2px 4px 6px 4px' }} role="list">
              {messages.length === 0 && <EmptyState />}
              {messages.map(renderMessage)}
              {agentTyping && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
                  <Avatar size={26} radius="xl" color="gray">{agentTyping[0].toUpperCase()}</Avatar>
                  <Paper radius="lg" p={8} shadow="xs" style={{ background: 'var(--mantine-color-gray-1)', border: '1px solid var(--mantine-color-gray-3)' }}>
                    <div className="typing" style={{ display: 'flex', gap: 4 }}>
                      {[0,1,2].map(i => <span key={i} style={{ width: 6, height: 6, borderRadius: 6, background: 'var(--mantine-color-gray-5)', animation: `blink 1s ${(i*0.2)}s infinite` }} />)}
                    </div>
                  </Paper>
                </div>
              )}
            </div>
          </ScrollArea>
          <Divider my={8} />
          <Group align="flex-end" gap="xs" wrap="nowrap" style={{ paddingTop: 2 }}>
            <Textarea
              placeholder="Type your question..."
              value={input}
              onChange={e => setInput(e.currentTarget.value)}
              autosize
              minRows={2}
              maxRows={4}
              style={{ flex: 1 }}
              radius="md"
              disabled={loading}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  sessionId ? sendFollowUp() : startDiscussion();
                }
              }}
              aria-label="Discussion input"
            />
            <Tooltip label={sessionId ? 'Send follow-up' : 'Start new discussion'}>
              <ActionIcon color="blue" variant="filled" size="lg" radius="md" onClick={sessionId ? sendFollowUp : startDiscussion} loading={loading} aria-label="Send message">
                <IconSend size={16} />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Paper>
      </Card>
    </Group>
  );
};

export default DiscussionsTab;
