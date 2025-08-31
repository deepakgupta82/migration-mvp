import { useState, useEffect, useCallback, useRef } from 'react';
import { CrewAIMessage, ConnectionState, UseWebSocketReturn } from './types';

export const useWebSocket = (
  url: string,
  channels: string[] = ['crewai_activities', 'crewai_terminal'],
  projectId?: string
): UseWebSocketReturn => {
  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected');
  const [messages, setMessages] = useState<CrewAIMessage[]>([]);
  const [error, setError] = useState<Error | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;
  const reconnectDelay = 3000;

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      setConnectionState('connecting');
      setError(null);

      const wsUrl = projectId
        ? `${url}?project_id=${projectId}&channels=${channels.join(',')}`
        : `${url}?channels=${channels.join(',')}`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnectionState('connected');
        reconnectAttempts.current = 0;
        console.log('CrewAI Terminal WebSocket connected');
      };

      ws.onmessage = (event) => {
        try {
          const message: CrewAIMessage = JSON.parse(event.data);
          setMessages(prev => [...prev, message]);
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
          setError(new Error('Failed to parse incoming message'));
        }
      };

      ws.onclose = (event) => {
        setConnectionState('disconnected');
        wsRef.current = null;

        if (!event.wasClean && reconnectAttempts.current < maxReconnectAttempts) {
          reconnectAttempts.current++;
          setConnectionState('reconnecting');
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, reconnectDelay);
        }
      };

      ws.onerror = (event) => {
        setConnectionState('error');
        setError(new Error('WebSocket connection error'));
        console.error('WebSocket error:', event);
      };

    } catch (err) {
      setConnectionState('error');
      setError(err instanceof Error ? err : new Error('Connection failed'));
    }
  }, [url, channels, projectId]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close(1000, 'Component unmounting');
      wsRef.current = null;
    }

    setConnectionState('disconnected');
    reconnectAttempts.current = 0;
  }, []);

  const reconnect = useCallback(() => {
    disconnect();
    setTimeout(() => connect(), 100);
  }, [connect, disconnect]);

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket is not connected. Message not sent:', message);
    }
  }, []);

  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    connectionState,
    messages,
    error,
    reconnect,
    disconnect,
    sendMessage,
  };
};

// Hook for processing and filtering terminal entries
export const useTerminalProcessor = (
  messages: CrewAIMessage[],
  maxEntries: number = 1000
) => {
  const [processedMessages, setProcessedMessages] = useState<CrewAIMessage[]>([]);

  useEffect(() => {
    // Process messages with debouncing for high-frequency updates
    const processMessages = () => {
      setProcessedMessages(prev => {
        const newMessages = [...prev, ...messages];
        // Keep only the most recent messages
        return newMessages.slice(-maxEntries);
      });
    };

    if (messages.length > 0) {
      // Debounce processing for high-frequency updates
      const timeoutId = setTimeout(processMessages, 100);
      return () => clearTimeout(timeoutId);
    }
  }, [messages, maxEntries]);

  return processedMessages;
};

// Hook for managing terminal scroll behavior
export const useTerminalScroll = (
  autoScrollEnabled: boolean,
  containerRef: React.RefObject<HTMLDivElement>
) => {
  const [isUserScrolling, setIsUserScrolling] = useState(false);
  const scrollTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const scrollToBottom = useCallback(() => {
    if (containerRef.current && autoScrollEnabled && !isUserScrolling) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [autoScrollEnabled, isUserScrolling]);

  const handleScroll = useCallback(() => {
    if (!containerRef.current) return;

    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const isAtBottom = scrollTop + clientHeight >= scrollHeight - 10;

    if (!isAtBottom && !isUserScrolling) {
      setIsUserScrolling(true);
    } else if (isAtBottom && isUserScrolling) {
      setIsUserScrolling(false);
    }

    // Reset user scrolling detection after a delay
    if (scrollTimeoutRef.current) {
      clearTimeout(scrollTimeoutRef.current);
    }

    scrollTimeoutRef.current = setTimeout(() => {
      setIsUserScrolling(false);
    }, 3000);
  }, [isUserScrolling]);

  useEffect(() => {
    return () => {
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current);
      }
    };
  }, []);

  return {
    scrollToBottom,
    handleScroll,
    isUserScrolling,
  };
};