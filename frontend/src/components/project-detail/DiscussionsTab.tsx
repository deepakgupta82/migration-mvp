import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Card, Group, Text, Badge, Textarea, Button, ScrollArea, Loader, Paper, MultiSelect, Divider, Stack, Tooltip, ActionIcon, Avatar, ThemeIcon, Input, Transition, Modal } from '@mantine/core';
import { IconSend, IconRefresh, IconPlayerPlay, IconTrash, IconMessageChatbot, IconChevronRight, IconSearch, IconSparkles, IconClock, IconInfoCircle } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { apiService } from '../../services/api';

interface DiscussionsTabProps { projectId: string; }

interface DiscussionMessage {
  id: string;
  session_id: string;
  ts: string;
  source: string;
  content: string;
  message_type?: string;
  agent_name?: string;
  index?: number;
  total?: number;
}

interface DiscussionSessionMeta {
  session_id: string;
  created_at?: string;
  last_updated?: string;
  message_count?: number;
  participating_agents?: string[];
  status?: string;
}

interface QueryAnalysis {
  domains: string[];
  complexity: 'simple' | 'moderate' | 'complex';
  intent: string;
  tokens: number;
  has_question: boolean;
}

export const DiscussionsTab: React.FC<DiscussionsTabProps> = ({ projectId }) => {
  const [sessionId, setSessionId] = useState<string>('');
  const [queryAnalysis, setQueryAnalysis] = useState<QueryAnalysis | null>(null);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<DiscussionMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [availableAgents, setAvailableAgents] = useState<{ value: string; label: string; description?: string }[]>([]);
  const [infoAgent, setInfoAgent] = useState<{ name: string; description: string } | null>(null);
  const [selectedAgents, setSelectedAgents] = useState<string[]>([]);
  const [sessions, setSessions] = useState<DiscussionSessionMeta[]>([]);
  const [fetchingSessions, setFetchingSessions] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [agentTyping, setAgentTyping] = useState<string | null>(null);
  const [wsConnectionStatus, setWsConnectionStatus] = useState<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected');
  const scrollRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 3;
  // Resizable sidebar state (persisted)
  const [sidebarWidth, setSidebarWidth] = useState<number>(() => {
    const saved = typeof window !== 'undefined' ? window.localStorage.getItem('discussions.sidebarWidth') : null;
    const parsed = saved ? parseInt(saved, 10) : 280;
    return isNaN(parsed) ? 280 : Math.min(Math.max(parsed, 220), 480);
  });
  const isResizingRef = useRef(false);

  // Auto-scroll to bottom when new messages arrive
   useEffect(() => {
     if (scrollRef.current) {
       scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
     }
   }, [messages, agentTyping]);

   // Sort messages by timestamp to ensure correct order
   const sortedMessages = useMemo(() => {
     return [...messages].sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());
   }, [messages]);

  // Cleanup WebSocket connections and timeouts on unmount
  useEffect(() => {
    return () => {
      // Clear reconnection timeout
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }

      // Close WebSocket connection
      if (wsRef.current) {
        console.log('Cleaning up WebSocket connection');
        wsRef.current.close();
        wsRef.current = null;
      }

      setWsConnectionStatus('disconnected');
    };
  }, []);

  // Persist sidebar width
  useEffect(() => {
    try {
      window.localStorage.setItem('discussions.sidebarWidth', String(sidebarWidth));
    } catch {}
  }, [sidebarWidth]);

  // Handlers for sidebar resizing
  const onResizeMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isResizingRef.current = true;
    const startX = e.clientX;
    const startWidth = sidebarWidth;

    const onMouseMove = (ev: MouseEvent) => {
      if (!isResizingRef.current) return;
      const dx = ev.clientX - startX;
      const newWidth = Math.min(Math.max(startWidth + dx, 220), 480);
      setSidebarWidth(newWidth);
    };
    const onMouseUp = () => {
      isResizingRef.current = false;
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
  }, [sidebarWidth]);

  const loadAgents = async () => {
    try {
      const data = await apiService.getAutoGenAgents();
      if (data.available_agents) {
        setAvailableAgents(Object.entries<string>(data.available_agents).map(([k, v]) => ({ value: k, label: k, description: v })));
      }
    } catch (e) {
      console.warn('Failed to load agents', e);
      notifications.show({
        title: 'Failed to Load Agents',
        message: 'Could not load available AutoGen agents. Please check the service connection.',
        color: 'red',
      });
    }
  };

  const loadSessions = async () => {
    setFetchingSessions(true);
    try {
      const data = await apiService.getAutoGenConversationHistory(25);
      if (data.sessions) setSessions(data.sessions);
    } catch (e) {
      console.warn('Failed to load sessions', e);
      notifications.show({
        title: 'Failed to Load Sessions',
        message: 'Could not load conversation history. Please check the service connection.',
        color: 'red',
      });
    } finally { setFetchingSessions(false); }
  };

  // Analyze query for complexity, domains, and intent (client-side preview)
  const analyzeQuery = useCallback((message: string): QueryAnalysis => {
    const lowered = message.toLowerCase();
    const domains: string[] = [];
    
    // Domain detection
    if (/cost|budget|price|pricing|expense|tco|roi|savings|financial/.test(lowered)) domains.push('cost');
    if (/secure|security|iam|compliance|gdpr|hipaa|rbac|encryption|vulnerability/.test(lowered)) domains.push('security');
    if (/migrate|migration|lift|shift|refactor|rehost|replatform|move/.test(lowered)) domains.push('migration');
    if (/data|database|etl|warehouse|lake|analytics|sql|nosql|storage/.test(lowered)) domains.push('data');
    if (/modern|microservice|container|kubernetes|docker|serverless|cloud-native/.test(lowered)) domains.push('modernization');
    if (/deploy|ci\/cd|pipeline|automation|jenkins|gitlab|azure devops|terraform/.test(lowered)) domains.push('devops');
    
    // Complexity detection
    const wordCount = message.split(/\s+/).length;
    const hasQuestion = /what|how|why|when|where|which|who/.test(lowered);
    let complexity: 'simple' | 'moderate' | 'complex' = 'simple';
    
    if (wordCount > 140 || /strategy|architecture|comprehensive|plan|design|approach/.test(lowered)) {
      complexity = 'complex';
    } else if (wordCount > 70 || domains.length > 2) {
      complexity = 'moderate';
    } else if (hasQuestion && wordCount < 30) {
      complexity = 'simple';
    }
    
    // Intent detection
    let intent = 'question';
    if (/analyze|analysis|assess|evaluate|review/.test(lowered)) intent = 'analysis';
    else if (/recommend|suggest|advise|propose/.test(lowered)) intent = 'recommendation';
    else if (/plan|design|architect/.test(lowered)) intent = 'planning';
    else if (/how many|count|list|show/.test(lowered)) intent = 'query';
    
    return {
      domains: domains.length > 0 ? domains : ['general'],
      complexity,
      intent,
      tokens: wordCount,
      has_question: hasQuestion,
    };
  }, []);
  
  // Update analysis when input changes
  useEffect(() => {
    if (input.trim().length > 10) {
      setQueryAnalysis(analyzeQuery(input));
    } else {
      setQueryAnalysis(null);
    }
  }, [input, analyzeQuery]);

  const openWebSocket = (sid: string, isReconnect = false) => {
    // Clear any existing reconnection timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // Close existing connection if any
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    if (!isReconnect) {
      setWsConnectionStatus('connecting');
      reconnectAttemptsRef.current = 0;
    }

    try {
      const ws = apiService.createAutoGenWebSocket(sid);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('AutoGen WebSocket connected for session:', sid);
        setWsConnectionStatus('connected');
        reconnectAttemptsRef.current = 0;

        if (isReconnect) {
          notifications.show({
            title: 'Reconnected',
            message: 'Real-time updates restored.',
            color: 'green',
          });
        }
      };

      ws.onmessage = (evt) => {
        try {
          const packet = JSON.parse(evt.data);
          console.log('WebSocket message received:', packet);

          // Handle different message types from enhanced autogen_ws.py
          switch (packet.type) {
            case 'connection_established':
              console.log('WebSocket connection confirmed');
              break;

            case 'conversation_starting':
              setAgentTyping('Initializing agents...');
              setLoading(true);
              break;

            case 'agents_ready':
               setAgentTyping(null);
               setLoading(false); // Clear loading state when agents are ready
               // Add system message about agents being ready
               setMessages(prev => [...prev, {
                 id: Math.random().toString(36).slice(2),
                 session_id: sid,
                 ts: packet.timestamp || new Date().toISOString(),
                 source: 'system',
                 content: packet.message || 'All agents are ready to discuss your question.',
                 message_type: 'system_info'
               }]);
               break;

            case 'agent_initializing':
               setAgentTyping(packet.message || `🔄 Initializing ${packet.agent_name}...`);
               // Optionally add a system message for agent initialization
               setMessages(prev => [...prev, {
                 id: Math.random().toString(36).slice(2),
                 session_id: sid,
                 ts: packet.timestamp || new Date().toISOString(),
                 source: 'system',
                 content: packet.message || `🔄 Initializing ${packet.agent_name}...`,
                 message_type: 'system_info'
               }]);
               break;

            case 'agent_thinking':
               setAgentTyping(packet.message || `💭 ${packet.agent_name} is thinking...`);
               break;

            case 'agent_responding':
               setAgentTyping(packet.message || `✍️ ${packet.agent_name} is responding...`);
               break;

            case 'agents_thinking':
               setAgentTyping(packet.message || '🤔 Agents are analyzing your question...');
               break;

            case 'context_gathering':
               setAgentTyping(packet.message || '🔍 Gathering relevant context...');
               break;

            case 'agents_discussing':
               setAgentTyping(packet.message || '🗣️ Agents are discussing...');
               break;

            case 'conversation_processing':
               setAgentTyping(packet.message || '⚡ Processing conversation...');
               break;

            case 'agent_response':
              // Add individual agent response
              setMessages(prev => [...prev, {
                id: Math.random().toString(36).slice(2),
                session_id: sid,
                ts: packet.timestamp || new Date().toISOString(),
                source: packet.agent_name || 'agent',
                content: packet.content || '',
                message_type: 'agent_response',
                agent_name: packet.agent_name
              }]);
              setAgentTyping(null);
              break;

            case 'recommendations_start':
              setMessages(prev => [...prev, {
                id: Math.random().toString(36).slice(2),
                session_id: sid,
                ts: packet.timestamp || new Date().toISOString(),
                source: 'system',
                content: packet.message || `📋 Found ${packet.count || 0} key recommendations`,
                message_type: 'system_info'
              }]);
              setAgentTyping(null); // Clear any typing indicator
              break;

            case 'recommendation_received':
              setMessages(prev => [...prev, {
                id: Math.random().toString(36).slice(2),
                session_id: sid,
                ts: packet.timestamp || new Date().toISOString(),
                source: packet.recommendation?.agent || 'system',
                content: packet.recommendation?.recommendation || '',
                message_type: 'recommendation',
                index: packet.index,
                total: packet.total
              }]);
              break;

            case 'recommendations_ready':
              // Aggregated recommendations array
              if (Array.isArray(packet.recommendations) && packet.recommendations.length) {
                setMessages(prev => [
                  ...prev,
                  {
                    id: Math.random().toString(36).slice(2),
                    session_id: sid,
                    ts: new Date().toISOString(),
                    source: 'system',
                    content: `📋 ${packet.recommendations.length} recommendations ready`,
                    message_type: 'system_info'
                  },
                  ...packet.recommendations.map((r: any, idx: number) => ({
                    id: Math.random().toString(36).slice(2),
                    session_id: sid,
                    ts: new Date().toISOString(),
                    source: r.agent || 'system',
                    content: r.recommendation || '',
                    message_type: 'recommendation',
                    index: idx + 1,
                    total: packet.recommendations.length
                  }))
                ]);
              }
              break;

            case 'action_items_start':
              setMessages(prev => [...prev, {
                id: Math.random().toString(36).slice(2),
                session_id: sid,
                ts: packet.timestamp || new Date().toISOString(),
                source: 'system',
                content: packet.message || `🎯 Identified ${packet.count || 0} actionable next steps`,
                message_type: 'system_info'
              }]);
              setAgentTyping(null); // Clear any typing indicator
              break;

            case 'action_item_received':
              setMessages(prev => [...prev, {
                id: Math.random().toString(36).slice(2),
                session_id: sid,
                ts: packet.timestamp || new Date().toISOString(),
                source: packet.action_item?.agent || 'system',
                content: packet.action_item?.action || '',
                message_type: 'action_item',
                index: packet.index,
                total: packet.total
              }]);
              break;

            case 'action_items_ready':
              // Aggregated action items array
              if (Array.isArray(packet.action_items) && packet.action_items.length) {
                setMessages(prev => [
                  ...prev,
                  {
                    id: Math.random().toString(36).slice(2),
                    session_id: sid,
                    ts: new Date().toISOString(),
                    source: 'system',
                    content: `🎯 ${packet.action_items.length} action items ready`,
                    message_type: 'system_info'
                  },
                  ...packet.action_items.map((a: any, idx: number) => ({
                    id: Math.random().toString(36).slice(2),
                    session_id: sid,
                    ts: new Date().toISOString(),
                    source: a.agent || 'system',
                    content: a.action || '',
                    message_type: 'action_item',
                    index: idx + 1,
                    total: packet.action_items.length
                  }))
                ]);
              }
              break;

            case 'summary_ready':
              setMessages(prev => [...prev, {
                id: Math.random().toString(36).slice(2),
                session_id: sid,
                ts: new Date().toISOString(),
                source: 'system',
                content: packet.message || '📊 Analysis complete!',
                message_type: 'system_info'
              }]);

              // Add summary details
              if (packet.summary) {
                const summary = packet.summary;
                let summaryContent = '## Summary\n\n';
                if (summary.total_messages) summaryContent += `**Messages:** ${summary.total_messages}\n`;
                if (summary.agents_participated) summaryContent += `**Agents:** ${summary.agents_participated.join(', ')}\n`;
                if (summary.key_topics_discussed) summaryContent += `**Topics:** ${summary.key_topics_discussed.join(', ')}\n`;
                if (summary.implementation_complexity) summaryContent += `**Complexity:** ${summary.implementation_complexity}\n`;
                if (summary.estimated_timeline) summaryContent += `**Timeline:** ${summary.estimated_timeline}\n`;

                setMessages(prev => [...prev, {
                  id: Math.random().toString(36).slice(2),
                  session_id: sid,
                  ts: new Date().toISOString(),
                  source: 'system',
                  content: summaryContent,
                  message_type: 'summary'
                }]);
              }
              break;

            case 'conversation_completed':
               setAgentTyping(null);
               setLoading(false); // Clear loading state
               setWsConnectionStatus('connected'); // Ensure connection status is correct

               // Add completion message
               setMessages(prev => [...prev, {
                 id: Math.random().toString(36).slice(2),
                 session_id: sid,
                 ts: packet.timestamp || new Date().toISOString(),
                 source: 'system',
                 content: '✅ Conversation completed successfully!',
                 message_type: 'system_info'
               }]);

               if (packet.result?.full_conversation) {
                 // Add any remaining messages from the conversation
                 const newMessages = packet.result.full_conversation
                   .filter((m: any) => !messages.some(existing => existing.content === m.content && existing.source === m.source))
                   .map((m: any) => ({
                     id: Math.random().toString(36).slice(2),
                     session_id: sid,
                     ts: m.timestamp || packet.timestamp || new Date().toISOString(),
                     source: m.source || 'agent',
                     content: m.content || '',
                     message_type: m.message_type || 'agent_response'
                   }));

                 if (newMessages.length > 0) {
                   setMessages(prev => [...prev, ...newMessages]);
                 }
               }
               break;

            case 'conversation_error':
               setAgentTyping(null);
               setLoading(false); // Clear loading state on error
               setMessages(prev => [...prev, {
                 id: Math.random().toString(36).slice(2),
                 session_id: sid,
                 ts: packet.timestamp || new Date().toISOString(),
                 source: 'system',
                 content: `❌ Conversation Error: ${packet.error || 'An unexpected error occurred during the conversation'}`,
                 message_type: 'error'
               }]);

               // Show notification for conversation errors
               notifications.show({
                 title: 'Conversation Error',
                 message: packet.error || 'An error occurred during the AutoGen conversation',
                 color: 'red',
               });
               break;

            case 'pong':
              // Handle ping/pong for connection health
              console.log('WebSocket pong received');
              break;

            default:
              console.log('Unhandled WebSocket message type:', packet.type);
          }
        } catch (error) {
          console.error('WebSocket message parsing error:', error);
        }
      };

      ws.onerror = (error) => {
         console.error('WebSocket error:', error);
         setWsConnectionStatus('error');
         setAgentTyping(null); // Clear typing indicator on error
         setLoading(false); // Clear loading state on error

         // Add error message to chat
         setMessages(prev => [...prev, {
           id: Math.random().toString(36).slice(2),
           session_id: sid,
           ts: new Date().toISOString(),
           source: 'system',
           content: '❌ WebSocket connection error. Real-time updates may be unavailable.',
           message_type: 'error'
         }]);
       };

      ws.onclose = (event) => {
         console.log('WebSocket closed:', event.code, event.reason);
         wsRef.current = null;
         setWsConnectionStatus('disconnected');
         setAgentTyping(null); // Clear typing indicator
         setLoading(false); // Clear loading state

         // Attempt reconnection for unexpected closures (avoid cluttering chat UI)
         if (event.code !== 1000 && reconnectAttemptsRef.current < maxReconnectAttempts) {
           reconnectAttemptsRef.current++;
           const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 10000); // Exponential backoff

           console.log(`Attempting WebSocket reconnection ${reconnectAttemptsRef.current}/${maxReconnectAttempts} in ${delay}ms`);

           reconnectTimeoutRef.current = setTimeout(() => {
             openWebSocket(sid, true);
           }, delay);
         }
       };

    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      setWsConnectionStatus('error');
    }
  };

  const startDiscussion = async () => {
    if (!input.trim()) return;
    setLoading(true);
    try {
      // Generate a session id on the client to ensure WS and HTTP use the same id
      const sid = (typeof crypto !== 'undefined' && (crypto as any).randomUUID)
        ? (crypto as any).randomUUID()
        : Math.random().toString(36).slice(2);

      setSessionId(sid);

      // Optimistically show the user message
      setMessages([{
        id: Math.random().toString(36).slice(2),
        session_id: sid,
        ts: new Date().toISOString(),
        source: 'user',
        content: input,
        message_type: 'user_message'
      }]);

      // Open WebSocket first so backend detects it and streams
      try {
        openWebSocket(sid);
      } catch (wsError) {
        console.warn('WebSocket connection failed:', wsError);
      }

      // Start the discussion on the backend with our session_id
      const data = await apiService.startAutoGenDiscussion({
        message: input,
        selected_agents: selectedAgents,
        project_id: projectId,
        session_id: sid
      });

      if (data.status === 'success' || data.session_id) {
        notifications.show({
          title: 'Discussion Started',
          message: `Session ${sid} started successfully`,
          color: 'green'
        });
        setInput(''); // Clear input after successful start
      } else {
        notifications.show({
          title: 'Start Failed',
          message: data.error || 'Unknown error occurred',
          color: 'red'
        });
      }
    } catch (e: any) {
      console.error('Error starting discussion:', e);
      notifications.show({
        title: 'Error',
        message: `Failed to start discussion: ${String(e)}`,
        color: 'red'
      });
    } finally { setLoading(false); }
  };

  const sendFollowUp = async () => {
    if (!sessionId || !input.trim()) return;
    setLoading(true);
    try {
      const data = await apiService.sendAutoGenFollowUp(sessionId, {
        message: input,
        session_id: sessionId,
        override_agents: selectedAgents,
        fetch_context: true,
        project_id: projectId
      });

      if (data.status === 'success') {
        // Add user message to chat
        setMessages(prev => [...prev, {
          id: Math.random().toString(36).slice(2),
          session_id: sessionId,
          ts: new Date().toISOString(),
          source: 'user',
          content: input,
          message_type: 'user_message'
        }]);

        notifications.show({
          title: 'Message Sent',
          message: 'Follow-up message processed successfully',
          color: 'blue'
        });

        setInput(''); // Clear input after successful send
      } else {
        notifications.show({
          title: 'Send Failed',
          message: data.error || 'Unknown error occurred',
          color: 'red'
        });
      }
    } catch (e: any) {
      console.error('Error sending follow-up:', e);
      notifications.show({
        title: 'Error',
        message: `Failed to send message: ${String(e)}`,
        color: 'red'
      });
    } finally { setLoading(false); }
  };

  const loadSessionHistory = async (sid: string) => {
    setSessionId(sid);
    setMessages([]);
    try {
      const data = await apiService.getAutoGenSessionHistory(sid);
      if (data.status === 'success') {
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

        // Try to open WebSocket for real-time updates
        try {
          openWebSocket(sid);
        } catch (wsError) {
          console.warn('WebSocket connection failed for session history:', wsError);
        }

        notifications.show({
          title: 'Session Loaded',
          message: `Loaded conversation session ${sid}`,
          color: 'blue'
        });
      } else {
        notifications.show({
          title: 'Failed to Load Session',
          message: 'Could not load session history',
          color: 'red'
        });
      }
    } catch (error) {
      console.error('Error loading session history:', error);
      notifications.show({
        title: 'Error',
        message: 'Failed to load session history',
        color: 'red'
      });
    }
  };

  const handleClearChat = () => {
    setSessionId('');
    setMessages([]);
    setAgentTyping(null);
    setWsConnectionStatus('disconnected');
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  };

  const handleNewChat = () => {
    // Clear current chat
    handleClearChat();

    // Don't generate session ID upfront - will be set when starting discussion
    setSessionId('');

    // Clear messages to show empty state
    setMessages([]);
  };

  useEffect(() => { loadAgents(); loadSessions(); }, []);


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

  // Render a single message bubble with improved accessibility and message type handling
   const renderMessage = useCallback((m: DiscussionMessage, idx: number) => {
     const isUser = m.source === 'user';
     const isSystem = m.source === 'system';
     const prev = sortedMessages[idx - 1];
     const showHeader = !prev || prev.source !== m.source;

    // Determine message styling based on type
    const getMessageStyle = () => {
      if (isUser) {
        return {
          background: 'var(--mantine-color-blue-light)',
          border: '1px solid var(--mantine-color-blue-4)',
          maxWidth: '70%'
        };
      }

      switch (m.message_type) {
        case 'system_info':
          return {
            background: 'var(--mantine-color-yellow-0)',
            border: '1px solid var(--mantine-color-yellow-3)',
            maxWidth: '80%'
          };
        case 'recommendation':
          return {
            background: 'var(--mantine-color-green-0)',
            border: '1px solid var(--mantine-color-green-3)',
            maxWidth: '80%'
          };
        case 'action_item':
          return {
            background: 'var(--mantine-color-orange-0)',
            border: '1px solid var(--mantine-color-orange-3)',
            maxWidth: '80%'
          };
        case 'summary':
          return {
            background: 'var(--mantine-color-blue-0)',
            border: '1px solid var(--mantine-color-blue-3)',
            maxWidth: '85%'
          };
        case 'error':
          return {
            background: 'var(--mantine-color-red-0)',
            border: '1px solid var(--mantine-color-red-3)',
            maxWidth: '80%'
          };
        default:
          // Agent messages: light shaded based on agent
          const agentColor = getAgentColor(m.source);
          return {
            background: `var(--mantine-color-${agentColor}-0)`,
            border: `1px solid var(--mantine-color-${agentColor}-3)`,
            maxWidth: '75%'
          };
      }
    };

    // Get agent color based on name
    const getAgentColor = (agentName: string) => {
      const colors = ['blue', 'green', 'orange', 'purple', 'red', 'cyan', 'pink', 'lime'];
      const hash = agentName.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
      return colors[hash % colors.length];
    };

    const messageStyle = getMessageStyle();

    return (
      <div
        key={m.id}
        style={{
          display: 'flex',
          justifyContent: isUser ? 'flex-end' : isSystem ? 'center' : 'flex-start',
          marginBottom: 12
        }}
        role="listitem"
        aria-label={`Message from ${m.source} at ${new Date(m.ts).toLocaleTimeString()}`}
        tabIndex={0}
        className="focus-ring"
      >
        <div style={{
          display: 'flex',
          flexDirection: isUser ? 'row-reverse' : 'row',
          gap: 8,
          alignItems: 'flex-start'
        }}>
          {/* Avatar for non-system messages */}
          {!isSystem && showHeader && (
            <Avatar
              size={32}
              radius="xl"
              color={isUser ? 'blue' : getAgentColor(m.source)}
              aria-hidden="true"
            >
              {isUser ? 'U' : (m.agent_name || m.source || '?')[0]?.toUpperCase()}
            </Avatar>
          )}

          {/* Message content */}
          <Paper
            p={12}
            radius="lg"
            style={{
              ...messageStyle,
              transition: 'transform 0.2s ease',
              position: 'relative'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'scale(1.01)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'scale(1)';
            }}
          >
            {/* Message header */}
            {showHeader && !isSystem && (
              <Group gap={6} mb={6}>
                <Text size="xs" fw={600} aria-label={`Sender: ${m.source}`}>
                  {isUser ? 'You' : `${(m.agent_name || m.source)[0].toUpperCase()} ${(m.agent_name || m.source)}`}
                </Text>
                {m.message_type === 'recommendation' && (
                  <Badge size="xs" color="green" variant="light">💡 Recommendation</Badge>
                )}
                {m.message_type === 'action_item' && (
                  <Badge size="xs" color="orange" variant="light">🎯 Action Item</Badge>
                )}
                {m.index && m.total && (
                  <Badge size="xs" variant="outline">
                    {m.index}/{m.total}
                  </Badge>
                )}
              </Group>
            )}

            {/* System message styling */}
            {isSystem && (
              <Group justify="center" mb={4}>
                <Badge size="xs" color="yellow" variant="light">
                  {m.message_type === 'system_info' ? 'ℹ️ Info' :
                   m.message_type === 'error' ? '❌ Error' :
                   '🔧 System'}
                </Badge>
              </Group>
            )}

            {/* Message content */}
            <Text
              size="sm"
              style={{
                whiteSpace: 'pre-wrap',
                lineHeight: 1.5,
                wordBreak: 'break-word'
              }}
            >
              {m.content}
            </Text>

            {/* Timestamp */}
            <Text
              size="10px"
              c="dimmed"
              mt={8}
              ta={isUser ? 'right' : 'left'}
              aria-label={`Sent at ${new Date(m.ts).toLocaleTimeString()}`}
            >
              {new Date(m.ts).toLocaleTimeString()}
            </Text>
          </Paper>
        </div>
      </div>
    );
  }, [sortedMessages]);

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
          <div style={{ display: isSidebarCollapsed ? 'none' : 'flex', flexDirection: 'row', ...styles }}>
            <Card withBorder shadow="sm" radius="lg" p="sm" style={{ width: sidebarWidth, display: 'flex', flexDirection: 'column' }}>
            <Group justify="space-between" mb="xs">
              <Text fw={600} size="sm">Agents</Text>
              <Group gap={4}>
                <Tooltip label="New chat">
                  <ActionIcon size="sm" variant="subtle" aria-label="Start new chat" onClick={handleNewChat}><IconMessageChatbot size={14} /></ActionIcon>
                </Tooltip>
                <Tooltip label="Clear chat">
                  <ActionIcon size="sm" variant="subtle" color="red" aria-label="Clear session" onClick={handleClearChat}><IconTrash size={14} /></ActionIcon>
                </Tooltip>
                <Tooltip label="Refresh agents">
                  <ActionIcon size="sm" variant="subtle" aria-label="Refresh agents" onClick={loadAgents}><IconRefresh size={14} /></ActionIcon>
                </Tooltip>
                <ActionIcon size="sm" variant="subtle" aria-label="Collapse sidebar" onClick={() => setIsSidebarCollapsed(true)}><IconChevronRight size={14} /></ActionIcon>
              </Group>
            </Group>
            <MultiSelect
              data={availableAgents}
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
            <ScrollArea style={{ flex: 1 }} offsetScrollbars>
              <Stack gap={6}>
                {fetchingSessions && <Loader size="xs" />}
                {sessions.map(s => {
                  const active = s.session_id === sessionId;
                  return (
                    <Paper key={s.session_id} p={8} radius="md" shadow={active ? 'sm' : 'xs'} withBorder style={{ cursor: 'pointer', background: active ? 'var(--mantine-color-blue-light)' : 'var(--mantine-color-gray-0)' }} onClick={() => loadSessionHistory(s.session_id)} aria-label={`Session ${s.session_id}`}>
                      <Group justify="space-between" gap={4} wrap="nowrap">
                        <Group gap={4} wrap="nowrap">
                          <Text size="xs" fw={500}>{s.session_id.slice(0, 10)}...</Text>
                          <Badge size="xs" color="blue" variant="light">{s.message_count || 0}</Badge>
                          {s.participating_agents?.slice(0, 3).map(a => (
                            <Text key={a} size="xs" c="dimmed" style={{ fontWeight: 600 }}>
                              {a[0].toUpperCase()}
                            </Text>
                          ))}
                        </Group>
                        <Group gap={4} wrap="nowrap">
                          {s.created_at && <Text size="xs" c="dimmed">{new Date(s.created_at).toLocaleDateString()} {new Date(s.created_at).toLocaleTimeString()}</Text>}
                          <Tooltip label="Resume">
                            <ActionIcon size="xs" variant="light" color="blue"><IconPlayerPlay size={14} /></ActionIcon>
                          </Tooltip>
                        </Group>
                      </Group>
                      <Text size="xs" c="dimmed" mt={4}>First message preview...</Text>
                    </Paper>
                  );
                })}
              </Stack>
            </ScrollArea>
          </Card>
          {/* Resize handle */}
          <div
            onMouseDown={onResizeMouseDown}
            style={{
              width: 6,
              cursor: 'col-resize',
              userSelect: 'none',
              background: 'var(--mantine-color-gray-2)',
              borderRight: '1px solid var(--mantine-color-gray-3)',
              borderTopLeftRadius: 8,
              borderBottomLeftRadius: 8
            }}
            aria-label="Resize sidebar"
            role="separator"
            aria-orientation="vertical"
          />
          </div>
        )}
      </Transition>
      {isSidebarCollapsed && (
        <ActionIcon variant="light" radius="xl" style={{ position: 'absolute', left: 4, top: 4, zIndex: 10 }} onClick={() => setIsSidebarCollapsed(false)} aria-label="Expand sidebar">
          <IconChevronRight size={16} style={{ transform: 'rotate(180deg)' }} />
        </ActionIcon>
      )}
  <Card withBorder shadow="sm" radius="lg" p="sm" style={{ flex: 1, minWidth: 0, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
        <Group justify="space-between" mb="xs">
          <Group gap={8}>
            <Text fw={600} size="sm">Discussion</Text>
            {sessionId && <Badge size="xs" variant="outline">{sessionId.slice(0, 8)}</Badge>}
          </Group>
          <Group gap={6}>
            {/* WebSocket Connection Status */}
            <Tooltip label={
              wsConnectionStatus === 'connected' ? 'Real-time updates active' :
              wsConnectionStatus === 'connecting' ? 'Connecting...' :
              wsConnectionStatus === 'error' ? 'Connection error' :
              'Disconnected - real-time updates disabled'
            }>
              <Badge
                size="xs"
                variant="dot"
                color={
                  wsConnectionStatus === 'connected' ? 'green' :
                  wsConnectionStatus === 'connecting' ? 'yellow' :
                  wsConnectionStatus === 'error' ? 'red' : 'gray'
                }
                style={{ cursor: 'pointer' }}
                onClick={() => {
                  if (wsConnectionStatus !== 'connected' && sessionId) {
                    openWebSocket(sessionId);
                  }
                }}
              >
                {wsConnectionStatus === 'connected' ? 'Live' :
                 wsConnectionStatus === 'connecting' ? 'Connecting' :
                 wsConnectionStatus === 'error' ? 'Error' : 'Offline'}
              </Badge>
            </Tooltip>

            {agentTyping && <Group gap={4} c="dimmed" style={{ fontSize: 11 }}><IconSparkles size={14} /> <span>{agentTyping} typing...</span></Group>}
            {loading && <Loader size="xs" />}
          </Group>
        </Group>
        <Paper withBorder radius="md" p="sm" style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', background: 'var(--mantine-color-gray-0)', position: 'relative', overflow: 'hidden' }}>
          <ScrollArea viewportRef={scrollRef} style={{ flex: 1, minHeight: 0 }} offsetScrollbars type="hover">
            <div style={{ padding: '2px 4px 6px 4px' }} role="list">
              {sortedMessages.length === 0 && <EmptyState />}
              {sortedMessages.map(renderMessage)}
              {agentTyping && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }} role="status" aria-label={`${agentTyping} is typing`}>
                  <Avatar size={26} radius="xl" color="gray" aria-hidden="true">{agentTyping[0].toUpperCase()}</Avatar>
                  <Paper radius="lg" p={8} shadow="xs" style={{ background: 'var(--mantine-color-gray-1)', border: '1px solid var(--mantine-color-gray-3)' }}>
                    <div className="typing" style={{ display: 'flex', gap: 4, alignItems: 'center' }} aria-hidden="true">
                      {[0,1,2].map(i => (
                        <span
                          key={i}
                          style={{
                            width: 6,
                            height: 6,
                            borderRadius: 6,
                            background: 'var(--mantine-color-gray-5)',
                            animation: `blink 1.4s ${i * 0.2}s infinite`
                          }}
                        />
                      ))}
                    </div>
                  </Paper>
                </div>
              )}
            </div>
          </ScrollArea>
          {/* Hidden help text for screen readers */}
          <div id="message-input-help" style={{ display: 'none' }}>
            Press Enter to send message, Shift+Enter for new line, Escape to clear
          </div>

          <Divider my={8} />
          
          {/* Query Analysis Preview */}
          {queryAnalysis && (
            <Paper p="xs" mb="xs" radius="md" style={{ backgroundColor: '#f8f9fa', border: '1px solid #e9ecef' }}>
              <Group gap="xs">
                <Tooltip label="Query complexity indicator" withinPortal>
                  <Badge 
                    size="sm" 
                    variant="light" 
                    color={queryAnalysis.complexity === 'complex' ? 'red' : queryAnalysis.complexity === 'moderate' ? 'yellow' : 'green'}
                  >
                    {queryAnalysis.complexity}
                  </Badge>
                </Tooltip>
                
                <Tooltip label="Query intent" withinPortal>
                  <Badge size="sm" variant="outline" color="blue">
                    {queryAnalysis.intent}
                  </Badge>
                </Tooltip>
                
                {queryAnalysis.domains.map((domain, idx) => (
                  <Tooltip key={idx} label={`Domain: ${domain}`} withinPortal>
                    <Badge size="sm" variant="dot" color="violet">
                      {domain}
                    </Badge>
                  </Tooltip>
                ))}
                
                <Text size="xs" c="dimmed" ml="auto">
                  {queryAnalysis.tokens} words
                  {queryAnalysis.has_question && ' • Question detected'}
                </Text>
              </Group>
            </Paper>
          )}
          
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
                if (e.key === 'Escape') setInput('');
              }}
              aria-describedby="message-input-help"
            />
            <Tooltip label={sessionId ? 'Send follow-up' : 'Start discussion'} openDelay={300} withinPortal>
              <ActionIcon
                size="lg"
                radius="md"
                color="blue"
                variant="filled"
                onClick={() => sessionId ? sendFollowUp() : startDiscussion()}
                disabled={loading || !input.trim()}
                aria-label={sessionId ? 'Send follow-up message' : 'Start new discussion'}
              >
                <IconSend size={16} />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Paper>
      </Card>
    </Group>
  );
};
 
