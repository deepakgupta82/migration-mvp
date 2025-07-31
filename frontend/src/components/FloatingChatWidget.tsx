import React, { useState, useRef, useEffect } from 'react';
import {
  Paper,
  Text,
  Stack,
  Group,
  ActionIcon,
  ScrollArea,
  TextInput,
  Loader,
  Badge,
  Transition,
  Box,
  Avatar,
  Tooltip,
} from '@mantine/core';
import {
  IconMessage,
  IconX,
  IconSend,
  IconRobot,
  IconUser,
  IconMinus,
} from '@tabler/icons-react';
import { apiService } from '../services/api';
import { notifications } from '@mantine/notifications';

interface Message {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface FloatingChatWidgetProps {
  projectId: string;
  isVisible?: boolean;
}

const FloatingChatWidget: React.FC<FloatingChatWidgetProps> = ({
  projectId,
  isVisible = true
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      type: 'assistant',
      content: 'Hello! I\'m your AI assistant. I can help you find information from your project documents. What would you like to know?',
      timestamp: new Date(),
    },
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages are added
  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: inputValue.trim(),
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);

    try {
      // Make API call to the backend RAG service
      const response = await apiService.queryKnowledgeBase(projectId, userMessage.content);

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: response.answer || 'I apologize, but I could not find relevant information in the knowledge base for your question.',
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: 'I\'m sorry, but I encountered an error while processing your request. Please try again later.',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);

      notifications.show({
        title: 'Chat Error',
        message: 'Failed to get response from AI assistant',
        color: 'red',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  };

  const formatTime = (timestamp: Date) => {
    return timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  if (!isVisible) return null;

  return (
    <Box
      style={{
        position: 'fixed',
        bottom: '20px',
        right: '20px',
        zIndex: 1000,
      }}
    >
      {/* Chat Toggle Button */}
      {!isOpen && (
        <Tooltip label="Chat with Documents" position="left">
          <ActionIcon
            size={60}
            radius="xl"
            color="blue"
            variant="filled"
            onClick={() => {
              setIsOpen(true);
              setIsMinimized(false); // Reset minimized state when opening
            }}
            style={{
              boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
              transition: 'transform 0.2s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'scale(1.1)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'scale(1)';
            }}
          >
            <IconMessage size={24} />
          </ActionIcon>
        </Tooltip>
      )}

      {/* Chat Window */}
      <Transition mounted={isOpen} transition="slide-up" duration={300}>
        {(styles) => (
          <Paper
            style={{
              ...styles,
              width: '380px',
              height: isMinimized ? '60px' : '500px',
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.12)',
              border: '1px solid #e9ecef',
              overflow: 'hidden',
              transition: 'height 0.3s ease',
            }}
            radius="lg"
          >
            {/* Chat Header */}
            <Group
              justify="space-between"
              p="md"
              style={{
                borderBottom: isMinimized ? 'none' : '1px solid #e9ecef',
                background: 'linear-gradient(135deg, #228be6 0%, #1c7ed6 100%)',
                color: 'white',
              }}
            >
              <Group gap="sm">
                <Avatar size="sm" color="white" variant="filled">
                  <IconRobot size={16} />
                </Avatar>
                <div>
                  <Text size="sm" fw={600}>
                    Document Assistant
                  </Text>
                  <Text size="xs" opacity={0.8}>
                    Ask me about your project
                  </Text>
                </div>
              </Group>
              <Group gap="xs">
                <ActionIcon
                  size="sm"
                  variant="subtle"
                  color="white"
                  onClick={() => {
                    setIsMinimized(true);
                    setIsOpen(false); // Close the chat completely when minimized
                  }}
                >
                  <IconMinus size={14} />
                </ActionIcon>
                <ActionIcon
                  size="sm"
                  variant="subtle"
                  color="white"
                  onClick={() => setIsOpen(false)}
                >
                  <IconX size={14} />
                </ActionIcon>
              </Group>
            </Group>

            {/* Chat Content */}
            {!isMinimized && (
              <>
                {/* Messages Area */}
                <ScrollArea
                  h={380}
                  p="md"
                  viewportRef={scrollAreaRef}
                  style={{ backgroundColor: '#f8f9fa' }}
                >
                  <Stack gap="md">
                    {messages.map((message) => (
                      <Group
                        key={message.id}
                        align="flex-start"
                        gap="sm"
                        justify={message.type === 'user' ? 'flex-end' : 'flex-start'}
                      >
                        {message.type === 'assistant' && (
                          <Avatar size="sm" color="blue" variant="filled">
                            <IconRobot size={14} />
                          </Avatar>
                        )}

                        <Paper
                          p="sm"
                          radius="lg"
                          style={{
                            maxWidth: '280px',
                            backgroundColor: message.type === 'user' ? '#228be6' : 'white',
                            color: message.type === 'user' ? 'white' : '#333',
                            border: message.type === 'assistant' ? '1px solid #e9ecef' : 'none',
                          }}
                        >
                          <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
                            {message.content}
                          </Text>
                          <Text
                            size="xs"
                            opacity={0.7}
                            mt={4}
                            ta={message.type === 'user' ? 'right' : 'left'}
                          >
                            {formatTime(message.timestamp)}
                          </Text>
                        </Paper>

                        {message.type === 'user' && (
                          <Avatar size="sm" color="gray" variant="filled">
                            <IconUser size={14} />
                          </Avatar>
                        )}
                      </Group>
                    ))}

                    {isLoading && (
                      <Group align="flex-start" gap="sm">
                        <Avatar size="sm" color="blue" variant="filled">
                          <IconRobot size={14} />
                        </Avatar>
                        <Paper p="sm" radius="lg" style={{ backgroundColor: 'white', border: '1px solid #e9ecef' }}>
                          <Group gap="xs">
                            <Loader size="xs" />
                            <Text size="sm" c="dimmed">
                              Thinking...
                            </Text>
                          </Group>
                        </Paper>
                      </Group>
                    )}
                  </Stack>
                </ScrollArea>

                {/* Input Area */}
                <Group
                  gap="xs"
                  p="md"
                  style={{
                    borderTop: '1px solid #e9ecef',
                    backgroundColor: 'white',
                  }}
                >
                  <TextInput
                    flex={1}
                    placeholder="Ask about your documents..."
                    value={inputValue}
                    onChange={(event) => setInputValue(event.currentTarget.value)}
                    onKeyPress={handleKeyPress}
                    disabled={isLoading}
                    radius="xl"
                    size="sm"
                  />
                  <ActionIcon
                    size="lg"
                    radius="xl"
                    color="blue"
                    variant="filled"
                    onClick={handleSendMessage}
                    disabled={!inputValue.trim() || isLoading}
                  >
                    <IconSend size={16} />
                  </ActionIcon>
                </Group>
              </>
            )}
          </Paper>
        )}
      </Transition>
    </Box>
  );
};

export default FloatingChatWidget;
