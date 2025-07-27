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
      // Simulate API delay
      await new Promise(resolve => setTimeout(resolve, 1500));

      // Generate contextual responses based on the question
      let responseContent = '';
      const question = userMessage.content.toLowerCase();

      if (question.includes('infrastructure') || question.includes('architecture')) {
        responseContent = `Based on the analyzed documents, I can see your infrastructure includes:\n\n• **Web Servers**: Load-balanced application servers\n• **Database Layer**: Primary database with potential for clustering\n• **Storage Systems**: File storage and caching layers\n• **Network Components**: Load balancers and API gateways\n\n**Migration Recommendations:**\n• Consider containerizing the web servers for better scalability\n• Evaluate managed database services for reduced maintenance\n• Implement auto-scaling for variable workloads`;
      } else if (question.includes('cost') || question.includes('pricing') || question.includes('budget')) {
        responseContent = `**Cost Analysis Summary:**\n\n• **Current Infrastructure**: Estimated monthly cost of $2,500-$4,000\n• **Cloud Migration**: Projected 20-30% cost reduction\n• **Key Savings**: Reduced hardware maintenance, optimized resource usage\n\n**Cost Optimization Opportunities:**\n• Right-sizing instances based on actual usage\n• Reserved instances for predictable workloads\n• Automated scaling to reduce over-provisioning`;
      } else if (question.includes('risk') || question.includes('security') || question.includes('compliance')) {
        responseContent = `**Risk Assessment:**\n\n• **Security**: Medium risk - requires security group configuration\n• **Compliance**: Data residency requirements identified\n• **Downtime**: Low risk with proper migration planning\n\n**Mitigation Strategies:**\n• Implement blue-green deployment for zero downtime\n• Enhanced monitoring and alerting\n• Regular security audits and compliance checks`;
      } else if (question.includes('timeline') || question.includes('schedule') || question.includes('duration')) {
        responseContent = `**Migration Timeline:**\n\n• **Phase 1**: Infrastructure setup (2-3 weeks)\n• **Phase 2**: Application migration (3-4 weeks)\n• **Phase 3**: Testing and optimization (2 weeks)\n• **Phase 4**: Go-live and monitoring (1 week)\n\n**Total Duration**: 8-10 weeks\n\n*Timeline may vary based on complexity and testing requirements.*`;
      } else if (question.includes('database') || question.includes('data')) {
        responseContent = `**Database Migration Analysis:**\n\n• **Current Setup**: PostgreSQL on-premises\n• **Recommended Target**: Amazon RDS or Azure Database\n• **Data Size**: Approximately 50GB\n\n**Migration Strategy:**\n• Database schema validation\n• Incremental data sync during migration\n• Connection string updates for applications\n• Performance testing post-migration`;
      } else {
        responseContent = `I can help you with questions about your migration project. Here are some topics I can assist with:\n\n• **Infrastructure & Architecture**: Current setup and cloud recommendations\n• **Cost Analysis**: Budget estimates and optimization opportunities\n• **Risk Assessment**: Security, compliance, and mitigation strategies\n• **Timeline Planning**: Migration phases and duration estimates\n• **Database Migration**: Data migration strategies and best practices\n\nWhat specific aspect of your migration would you like to explore?`;
      }

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: responseContent,
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
      <Group justify="space-between" mb="md">
        <Text size="lg" fw={600}>
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
              gap="md"
              mb="md"
              style={{
                justifyContent: message.type === 'user' ? 'flex-end' : 'flex-start',
              }}
            >
              {message.type === 'assistant' && (
                <Avatar c="blue" size="sm">
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
                  c={message.type === 'user' ? 'rgba(255,255,255,0.7)' : 'dimmed'}
                  mt="xs"
                >
                  {message.timestamp.toLocaleTimeString()}
                </Text>
              </Paper>

              {message.type === 'user' && (
                <Avatar c="gray" size="sm">
                  <IconUser size={16} />
                </Avatar>
              )}
            </Group>
          ))}

          {loading && (
            <Group align="flex-start" gap="md" mb="md">
              <Avatar color="blue" size="sm">
                <IconRobot size={16} />
              </Avatar>
              <Paper p="md" style={{ backgroundColor: '#f8f9fa' }}>
                <Group gap="xs">
                  <Loader size="xs" />
                  <Text size="sm" c="dimmed">
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
          <Text size="sm" c="dimmed" mb="xs">
            Try asking:
          </Text>
          <Group gap="xs">
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
      <Group gap="md" style={{ alignItems: 'flex-end' }}>
        <TextInput
          placeholder="Ask about your infrastructure, migration strategy, or any technical details..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyPress}
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
