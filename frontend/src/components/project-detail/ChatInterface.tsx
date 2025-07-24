/**
 * Chat Interface Component - RAG Knowledge Base Chat
 */

import React, { useState, useRef, useEffect } from 'react';
import {
  Card,
  Text,
  TextInput,
  Button,
  ScrollArea,
  Group,
  Avatar,
  Paper,
  Loader,
  ActionIcon,
} from '@mantine/core';
import { IconSend, IconUser, IconRobot, IconRefresh } from '@tabler/icons-react';
import { apiService } from '../../services/api';

interface Message {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface ChatInterfaceProps {
  projectId: string;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ projectId }) => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      type: 'assistant',
      content: 'Hello! I can help you explore your project\'s knowledge base. Ask me anything about the uploaded documents, infrastructure components, or migration recommendations.',
      timestamp: new Date(),
    },
  ]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async () => {
    if (!inputValue.trim() || loading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: inputValue.trim(),
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setLoading(true);

    try {
      const response = await apiService.queryProjectKnowledge(projectId, userMessage.content);
      
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: response.answer,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: 'I apologize, but I encountered an error while processing your question. Please try again or rephrase your question.',
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  };

  const clearChat = () => {
    setMessages([
      {
        id: '1',
        type: 'assistant',
        content: 'Hello! I can help you explore your project\'s knowledge base. Ask me anything about the uploaded documents, infrastructure components, or migration recommendations.',
        timestamp: new Date(),
      },
    ]);
  };

  const suggestedQuestions = [
    'What are the main applications in this infrastructure?',
    'What databases are being used?',
    'What are the key migration risks?',
    'Show me the server dependencies',
    'What cloud migration strategy is recommended?',
  ];

  return (
    <Card shadow="sm" p="lg" radius="md" withBorder style={{ height: '600px', display: 'flex', flexDirection: 'column' }}>
      <Group position="apart" mb="md">
        <Text size="lg" weight={600}>
          Knowledge Base Chat
        </Text>
        <ActionIcon variant="subtle" onClick={clearChat}>
          <IconRefresh size={16} />
        </ActionIcon>
      </Group>

      {/* Messages Area */}
      <ScrollArea
        style={{ flex: 1, marginBottom: '16px' }}
        viewportRef={scrollAreaRef}
      >
        <div style={{ padding: '8px' }}>
          {messages.map((message) => (
            <Group
              key={message.id}
              align="flex-start"
              spacing="md"
              mb="md"
              style={{
                justifyContent: message.type === 'user' ? 'flex-end' : 'flex-start',
              }}
            >
              {message.type === 'assistant' && (
                <Avatar color="blue" size="sm">
                  <IconRobot size={16} />
                </Avatar>
              )}
              
              <Paper
                p="md"
                style={{
                  maxWidth: '70%',
                  backgroundColor: message.type === 'user' ? '#1c7ed6' : '#f8f9fa',
                  color: message.type === 'user' ? 'white' : 'inherit',
                }}
              >
                <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
                  {message.content}
                </Text>
                <Text
                  size="xs"
                  color={message.type === 'user' ? 'rgba(255,255,255,0.7)' : 'dimmed'}
                  mt="xs"
                >
                  {message.timestamp.toLocaleTimeString()}
                </Text>
              </Paper>

              {message.type === 'user' && (
                <Avatar color="gray" size="sm">
                  <IconUser size={16} />
                </Avatar>
              )}
            </Group>
          ))}

          {loading && (
            <Group align="flex-start" spacing="md" mb="md">
              <Avatar color="blue" size="sm">
                <IconRobot size={16} />
              </Avatar>
              <Paper p="md" style={{ backgroundColor: '#f8f9fa' }}>
                <Group spacing="xs">
                  <Loader size="xs" />
                  <Text size="sm" color="dimmed">
                    Thinking...
                  </Text>
                </Group>
              </Paper>
            </Group>
          )}
        </div>
      </ScrollArea>

      {/* Suggested Questions */}
      {messages.length === 1 && (
        <div style={{ marginBottom: '16px' }}>
          <Text size="sm" color="dimmed" mb="xs">
            Try asking:
          </Text>
          <Group spacing="xs">
            {suggestedQuestions.slice(0, 3).map((question, index) => (
              <Button
                key={index}
                size="xs"
                variant="light"
                onClick={() => setInputValue(question)}
              >
                {question}
              </Button>
            ))}
          </Group>
        </div>
      )}

      {/* Input Area */}
      <Group spacing="md" style={{ alignItems: 'flex-end' }}>
        <TextInput
          placeholder="Ask about your infrastructure, migration strategy, or any technical details..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyPress={handleKeyPress}
          style={{ flex: 1 }}
          disabled={loading}
        />
        <Button
          onClick={handleSendMessage}
          disabled={!inputValue.trim() || loading}
          loading={loading}
        >
          <IconSend size={16} />
        </Button>
      </Group>
    </Card>
  );
};
