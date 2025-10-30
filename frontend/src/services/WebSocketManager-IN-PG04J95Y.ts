/**
 * Centralized WebSocket Manager for Migration Platform
 * Manages single WebSocket connection per project with message routing
 */

import React, { useEffect, useRef, useCallback } from 'react';
import { apiService } from './api';
import {
  MessageType,
  AnyStandardizedMessage,
  StandardizedAssessmentMessage,
  StandardizedProcessingMessage,
  StandardizedLogMessage,
  StandardizedStatsMessage
} from '../types/messages';
import {
  parseAndValidateMessage,
  messageMatchesCriteria,
  validateProjectId,
  normalizeProjectId,
  validateAndNormalizeTimestamp
} from '../utils/messageValidation';
import { metricsService } from './MetricsService';

// Re-export for backward compatibility (type-only to satisfy isolatedModules)
export { MessageType } from '../types/messages';
export type { AnyStandardizedMessage } from '../types/messages';

// WebSocket connection states
export enum ConnectionState {
  DISCONNECTED = 'disconnected',
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  RECONNECTING = 'reconnecting',
  FAILED = 'failed'
}

// Legacy message interfaces for backward compatibility
export interface BaseMessage {
  type: string;
  timestamp: string;
  project_id?: string;
  data?: any;
}

export interface AssessmentMessage extends BaseMessage {
  type: 'agent_action' | 'tool_result' | 'tool_error' | 'agent_finish' | 'agent_start';
  agent_name?: string;
  tool?: string;
  tool_input?: string;
  output?: string;
  error?: string;
  status?: string;
  log?: string;
  goal?: string;
  action_description?: string;
}

export interface ProcessingMessage extends BaseMessage {
  type: 'operation_progress' | 'operation_completed' | 'operation_failed';
  operation_name?: string;
  current_step?: number;
  total_steps?: number;
  progress_percentage?: number;
  message?: string;
  service?: string;
}

export interface LogMessage extends BaseMessage {
  type: 'log_entry';
  level: 'INFO' | 'WARNING' | 'ERROR' | 'DEBUG';
  service: string;
  message: string;
  metadata?: Record<string, any>;
}

export interface StatsMessage extends BaseMessage {
  type: 'project_stats_update' | 'platform_stats_update';
  event_type?: string;
  changes?: Record<string, any>;
}

// Subscription callback types - now properly typed
export type MessageCallback<T extends AnyStandardizedMessage = AnyStandardizedMessage> = (message: T) => void;
export type AssessmentCallback = MessageCallback<StandardizedAssessmentMessage>;
export type ProcessingCallback = MessageCallback<StandardizedProcessingMessage>;
export type LogCallback = MessageCallback<StandardizedLogMessage>;
export type StatsCallback = MessageCallback<StandardizedStatsMessage>;

// Connection configuration
interface ConnectionConfig {
  projectId: string;
  messageTypes: MessageType[];
  onConnectionStateChange?: (state: ConnectionState) => void;
  onError?: (error: string) => void;
}

// Singleton WebSocket manager instance
class WebSocketManager {
  private connections = new Map<string, WebSocket>();
  private connectionStates = new Map<string, ConnectionState>();
  private subscriptions = new Map<string, Map<string, MessageCallback>>();
  private reconnectTimeouts = new Map<string, NodeJS.Timeout>();
  private reconnectAttempts = new Map<string, number>();
  private maxReconnectAttempts = 5;
  private baseReconnectDelay = 1000;
  private maxReconnectDelay = 30000;

  /**
   * Get WebSocket URL for a specific message type with fallback logic
   */
  private getWebSocketUrl(messageType: MessageType, projectId?: string): string {
    const baseUrls = {
      [MessageType.ASSESSMENT]: process.env.REACT_APP_WS_ASSESSMENT_URL || 'ws://localhost:8009/ws/run_assessment',
      [MessageType.PROCESSING]: process.env.REACT_APP_WS_PROCESSING_URL || 'ws://localhost:8009/ws/document-processing',
      [MessageType.LOGS]: process.env.REACT_APP_WS_LOGS_URL || 'ws://localhost:8009/ws/logs',
      [MessageType.STATS]: process.env.REACT_APP_WS_PROJECT_URL || 'ws://localhost:8009/ws/project'
    };

    let baseUrl = baseUrls[messageType];

    // Add project ID if needed
    if (projectId && messageType !== MessageType.LOGS) {
      baseUrl += `/${projectId}`;
    } else if (messageType === MessageType.LOGS) {
      baseUrl += '/document_processing';
    }

    // Add token parameter
    const token = this.getAuthToken();
    if (token) {
      const separator = baseUrl.includes('?') ? '&' : '?';
      baseUrl += `${separator}token=${encodeURIComponent(token)}`;
    }

    return baseUrl;
  }

  /**
   * Get fallback WebSocket URLs for different backend configurations
   */
  private getFallbackWebSocketUrls(messageType: MessageType, projectId?: string): string[] {
    const token = this.getAuthToken();
    const fallbackUrls: string[] = [];

    // Current location-based fallback (for production deployments)
    if (typeof window !== 'undefined') {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;

      const locationBasedUrls = {
        [MessageType.ASSESSMENT]: `${protocol}//${host}/ws/run_assessment/${projectId}`,
        [MessageType.PROCESSING]: `${protocol}//${host}/ws/document-processing/${projectId}`,
        [MessageType.LOGS]: `${protocol}//${host}/ws/logs/document_processing`,
        [MessageType.STATS]: `${protocol}//${host}/ws/project/${projectId}`
      };

      if (token) {
        Object.values(locationBasedUrls).forEach(url => {
          const separator = url.includes('?') ? '&' : '?';
          fallbackUrls.push(`${url}${separator}token=${encodeURIComponent(token)}`);
        });
      } else {
        fallbackUrls.push(...Object.values(locationBasedUrls));
      }
    }

    // Alternative ports for development (8009 is websocket service, others are fallbacks)
    const altPorts = ['8009', '8000', '8001', '8002', '8080'];
    altPorts.forEach(port => {
      const altUrls = {
        [MessageType.ASSESSMENT]: `ws://localhost:${port}/ws/run_assessment/${projectId}`,
        [MessageType.PROCESSING]: `ws://localhost:${port}/ws/document-processing/${projectId}`,
        [MessageType.LOGS]: `ws://localhost:${port}/ws/logs/document_processing`,
        [MessageType.STATS]: `ws://localhost:${port}/ws/project/${projectId}`
      };

      if (token) {
        Object.values(altUrls).forEach(url => {
          const separator = url.includes('?') ? '&' : '?';
          fallbackUrls.push(`${url}${separator}token=${encodeURIComponent(token)}`);
        });
      } else {
        fallbackUrls.push(...Object.values(altUrls));
      }
    });

    return fallbackUrls;
  }

  /**
   * Get authentication token for WebSocket connections
   */
  private getAuthToken(): string {
    // Try to get user auth token first
    const userToken = localStorage.getItem('authToken');
    if (userToken) {
      return userToken;
    }

    // Fallback to service token from environment
    return process.env.REACT_APP_WS_TOKEN || 'service-backend-token';
  }

  /**
   * Get or create WebSocket connection for a project
   */
  private getConnection(projectId: string, messageTypes: MessageType[]): WebSocket {
    const normalizedProjectId = normalizeProjectId(projectId);
    const connectionKey = `${normalizedProjectId}_${messageTypes.sort().join('_')}`;

    if (this.connections.has(connectionKey)) {
      const existingWs = this.connections.get(connectionKey)!;
      if (existingWs.readyState === WebSocket.OPEN) {
        return existingWs;
      }
      // Clean up closed connection
      this.cleanupConnection(connectionKey);
    }

    // Create new connection
    const ws = this.createWebSocket(normalizedProjectId, messageTypes);
    this.connections.set(connectionKey, ws);
    this.connectionStates.set(connectionKey, ConnectionState.CONNECTING);

    return ws;
  }

  /**
   * Create WebSocket connection based on message types with validation and fallbacks
   */
  private createWebSocket(projectId: string, messageTypes: MessageType[]): WebSocket {
    // Use the first message type as primary, with fallback logic
    const primaryMessageType = messageTypes[0] || MessageType.LOGS;

    // Get WebSocket URL with environment variables and fallbacks
    const wsUrl = this.getWebSocketUrl(primaryMessageType, projectId);

    // Validate the URL
    if (!this.validateWebSocketUrl(wsUrl)) {
      throw new Error(`Invalid WebSocket URL: ${wsUrl}`);
    }

    console.log(`Creating WebSocket connection: ${wsUrl}`);

    try {
      return new WebSocket(wsUrl);
    } catch (error) {
      console.error(`Failed to create WebSocket connection: ${error}`);
      throw error;
    }
  }

  /**
   * Subscribe to messages for a project with proper typing
   */
  subscribe<T extends AnyStandardizedMessage>(
    projectId: string,
    messageType: MessageType,
    callback: MessageCallback<T>,
    subscriptionId?: string
  ): string {
    // Validate project ID
    if (!validateProjectId(projectId)) {
      throw new Error(`Invalid project ID: ${projectId}`);
    }

    const normalizedProjectId = normalizeProjectId(projectId);
    const connectionKey = `${normalizedProjectId}_${messageType}`;
    const subId = subscriptionId || `${connectionKey}_${Date.now()}_${Math.random()}`;

    if (!this.subscriptions.has(connectionKey)) {
      this.subscriptions.set(connectionKey, new Map());
    }

    const connectionSubs = this.subscriptions.get(connectionKey)!;
    connectionSubs.set(subId, callback as MessageCallback);

    // Ensure connection is established
    this.ensureConnection(normalizedProjectId, [messageType]);

    return subId;
  }

  /**
   * Unsubscribe from messages
   */
  unsubscribe(projectId: string, messageType: MessageType, subscriptionId: string): void {
    const connectionKey = `${projectId}_${messageType}`;
    const connectionSubs = this.subscriptions.get(connectionKey);

    if (connectionSubs) {
      connectionSubs.delete(subscriptionId);

      // Clean up if no more subscriptions
      if (connectionSubs.size === 0) {
        this.subscriptions.delete(connectionKey);
        this.cleanupConnection(`${projectId}_${messageType}`);
      }
    }
  }

  /**
   * Ensure connection is established
   */
  private ensureConnection(projectId: string, messageTypes: MessageType[]): void {
    const ws = this.getConnection(projectId, messageTypes);
    const connectionKey = `${projectId}_${messageTypes.sort().join('_')}`;

    if (ws.readyState === WebSocket.CONNECTING) {
      // Already connecting, just wait
      return;
    }

    if (ws.readyState === WebSocket.OPEN) {
      // Already connected
      return;
    }

    // Set up event handlers
    this.setupWebSocketHandlers(ws, connectionKey, projectId, messageTypes);
  }

  /**
   * Validate WebSocket connection URL
   */
  private validateWebSocketUrl(url: string): boolean {
    try {
      const urlObj = new URL(url);
      return urlObj.protocol === 'ws:' || urlObj.protocol === 'wss:';
    } catch (error) {
      console.error('Invalid WebSocket URL:', url, error);
      return false;
    }
  }

  /**
   * Set up WebSocket event handlers with enhanced error handling
   */
  private setupWebSocketHandlers(
    ws: WebSocket,
    connectionKey: string,
    projectId: string,
    messageTypes: MessageType[]
  ): void {
    ws.onopen = () => {
      console.log(`WebSocket connected for ${connectionKey}`);
      this.connectionStates.set(connectionKey, ConnectionState.CONNECTED);
      this.reconnectAttempts.set(connectionKey, 0);

      // Clear any pending reconnect timeout
      const timeout = this.reconnectTimeouts.get(connectionKey);
      if (timeout) {
        clearTimeout(timeout);
        this.reconnectTimeouts.delete(connectionKey);
      }

      // Track connection event
      metricsService.trackWebSocketEvent('connect', {
        connectionId: connectionKey,
        connectionState: 'connected'
      });
    };

    ws.onmessage = (event) => {
      try {
        // Validate message data
        if (!event.data || typeof event.data !== 'string') {
          console.warn(`Invalid WebSocket message received for ${connectionKey}:`, event.data);
          return;
        }

        // Track message received event
        metricsService.trackWebSocketEvent('message_received', {
          connectionId: connectionKey,
          connectionState: 'connected'
        });

        this.handleMessage(event.data, projectId, messageTypes);
      } catch (error) {
        console.error(`Error handling WebSocket message for ${connectionKey}:`, error);
        // Don't close connection for message parsing errors, just log them
      }
    };

    ws.onclose = (event) => {
      const reason = event.reason || 'No reason provided';
      console.log(`WebSocket closed for ${connectionKey}: Code ${event.code}, Reason: ${reason}`);
      this.connectionStates.set(connectionKey, ConnectionState.DISCONNECTED);

      // Track disconnection event
      metricsService.trackWebSocketEvent('disconnect', {
        connectionId: connectionKey,
        connectionState: 'disconnected',
        errorMessage: `Code ${event.code}: ${reason}`
      });

      // Attempt reconnection for abnormal closures or network errors
      const shouldReconnect = event.code === 1006 || // Abnormal closure
                            event.code === 1011 || // Internal server error
                            event.code > 1000;     // Custom error codes

      if (shouldReconnect) {
        console.warn(`Attempting reconnection for ${connectionKey} due to abnormal closure`);
        this.attemptReconnection(connectionKey, projectId, messageTypes);
      }
    };

    ws.onerror = (error) => {
      console.error(`WebSocket error for ${connectionKey}:`, error);
      this.connectionStates.set(connectionKey, ConnectionState.FAILED);

      // Track error event
      metricsService.trackWebSocketEvent('error', {
        connectionId: connectionKey,
        connectionState: 'failed',
        errorMessage: error.toString()
      });

      // Attempt reconnection on error
      this.attemptReconnection(connectionKey, projectId, messageTypes);
    };
  }

  /**
   * Handle incoming messages with validation and normalization
   */
  private handleMessage(data: string, projectId: string, messageTypes: MessageType[]): void {
    try {
      // Parse and validate the message
      const validation = parseAndValidateMessage(data);
      if (!validation.isValid) {
        console.warn(`Invalid WebSocket message received:`, validation.errors);
        return;
      }

      const standardizedMessage = validation.normalizedMessage!;
      if (!standardizedMessage) {
        console.warn('No normalized message after validation');
        return;
      }

      // Route message to appropriate subscribers
      for (const messageType of messageTypes) {
        const connectionKey = `${projectId}_${messageType}`;
        const connectionSubs = this.subscriptions.get(connectionKey);

        if (connectionSubs) {
          // Check if message matches this subscription type and project
          if (messageMatchesCriteria(standardizedMessage, messageType, projectId)) {
            connectionSubs.forEach(callback => {
              try {
                callback(standardizedMessage as AnyStandardizedMessage);
              } catch (error) {
                console.error('Error in message callback:', error);
              }
            });
          }
        }
      }
    } catch (error) {
      console.error('Error processing WebSocket message:', error);
    }
  }


  /**
   * Attempt reconnection with exponential backoff and fallback URLs
   */
  private attemptReconnection(connectionKey: string, projectId: string, messageTypes: MessageType[]): void {
    const attempts = this.reconnectAttempts.get(connectionKey) || 0;

    if (attempts >= this.maxReconnectAttempts) {
      console.error(`Max reconnection attempts reached for ${connectionKey}`);
      this.connectionStates.set(connectionKey, ConnectionState.FAILED);

      // Track failed reconnection
      metricsService.trackWebSocketEvent('error', {
        connectionId: connectionKey,
        connectionState: 'failed',
        errorMessage: 'Max reconnection attempts reached',
        reconnectAttempts: attempts
      });
      return;
    }

    this.connectionStates.set(connectionKey, ConnectionState.RECONNECTING);
    this.reconnectAttempts.set(connectionKey, attempts + 1);

    // Track reconnection attempt
    metricsService.trackWebSocketEvent('reconnect', {
      connectionId: connectionKey,
      connectionState: 'reconnecting',
      reconnectAttempts: attempts + 1
    });

    const delay = Math.min(
      this.baseReconnectDelay * Math.pow(2, attempts),
      this.maxReconnectDelay
    );

    console.log(`Attempting to reconnect ${connectionKey} in ${delay}ms (attempt ${attempts + 1})`);

    const timeout = setTimeout(() => {
      this.reconnectTimeouts.delete(connectionKey);

      // After a few failed attempts, try fallback URLs
      if (attempts >= 2) {
        this.tryFallbackConnection(connectionKey, projectId, messageTypes);
      } else {
        this.ensureConnection(projectId, messageTypes);
      }
    }, delay);

    this.reconnectTimeouts.set(connectionKey, timeout);
  }

  /**
   * Try fallback WebSocket URLs when primary connection fails
   */
  private tryFallbackConnection(connectionKey: string, projectId: string, messageTypes: MessageType[]): void {
    const primaryMessageType = messageTypes[0] || MessageType.LOGS;
    const fallbackUrls = this.getFallbackWebSocketUrls(primaryMessageType, projectId);

    console.log(`Trying fallback URLs for ${connectionKey}:`, fallbackUrls);

    // Try each fallback URL in sequence
    const tryNextUrl = (urlIndex: number) => {
      if (urlIndex >= fallbackUrls.length) {
        console.error(`All fallback URLs failed for ${connectionKey}`);
        this.connectionStates.set(connectionKey, ConnectionState.FAILED);
        return;
      }

      const url = fallbackUrls[urlIndex];
      console.log(`Trying fallback URL ${urlIndex + 1}/${fallbackUrls.length}: ${url}`);

      try {
        if (!this.validateWebSocketUrl(url)) {
          console.warn(`Invalid fallback URL: ${url}, trying next...`);
          tryNextUrl(urlIndex + 1);
          return;
        }

        const ws = new WebSocket(url);
        this.connections.set(connectionKey, ws);
        this.setupWebSocketHandlers(ws, connectionKey, projectId, messageTypes);

        // Set a timeout for connection attempt
        const connectionTimeout = setTimeout(() => {
          if (ws.readyState === WebSocket.CONNECTING) {
            console.warn(`Fallback URL ${url} connection timeout, trying next...`);
            ws.close();
            tryNextUrl(urlIndex + 1);
          }
        }, 5000); // 5 second timeout

        ws.onopen = () => {
          clearTimeout(connectionTimeout);
          console.log(`Fallback WebSocket connected for ${connectionKey} using: ${url}`);
          this.connectionStates.set(connectionKey, ConnectionState.CONNECTED);
          this.reconnectAttempts.set(connectionKey, 0);

          // Clear any pending reconnect timeout
          const timeout = this.reconnectTimeouts.get(connectionKey);
          if (timeout) {
            clearTimeout(timeout);
            this.reconnectTimeouts.delete(connectionKey);
          }
        };

        ws.onerror = () => {
          clearTimeout(connectionTimeout);
          console.warn(`Fallback URL ${url} failed, trying next...`);
          tryNextUrl(urlIndex + 1);
        };

      } catch (error) {
        console.error(`Error creating fallback WebSocket for ${url}:`, error);
        tryNextUrl(urlIndex + 1);
      }
    };

    tryNextUrl(0);
  }

  /**
   * Clean up connection and related resources
   */
  private cleanupConnection(connectionKey: string): void {
    const ws = this.connections.get(connectionKey);
    if (ws) {
      ws.close(1000, 'Cleaning up connection');
      this.connections.delete(connectionKey);
    }

    this.connectionStates.delete(connectionKey);

    const timeout = this.reconnectTimeouts.get(connectionKey);
    if (timeout) {
      clearTimeout(timeout);
      this.reconnectTimeouts.delete(connectionKey);
    }

    this.reconnectAttempts.delete(connectionKey);
  }

  /**
   * Send message through WebSocket with validation
   */
  sendMessage(projectId: string, messageTypes: MessageType[], message: any): void {
    // Validate project ID
    if (!validateProjectId(projectId)) {
      console.error(`Invalid project ID for sending message: ${projectId}`);
      return;
    }

    const normalizedProjectId = normalizeProjectId(projectId);
    const ws = this.getConnection(normalizedProjectId, messageTypes);
    const connectionKey = `${normalizedProjectId}_${messageTypes.sort().join('_')}`;

    if (ws.readyState === WebSocket.OPEN) {
      try {
        // Ensure message has required fields
        const messageToSend = {
          ...message,
          project_id: normalizedProjectId,
          timestamp: message.timestamp || new Date().toISOString(),
        };

        ws.send(JSON.stringify(messageToSend));

        // Track message sent event
        metricsService.trackWebSocketEvent('message_sent', {
          connectionId: connectionKey,
          connectionState: 'connected'
        });
      } catch (error) {
        console.error(`Error sending WebSocket message:`, error);
      }
    } else {
      console.warn(`WebSocket not ready for ${connectionKey}, message not sent:`, message);
    }
  }

  /**
   * Get connection state for a project and message types
   */
  getConnectionState(projectId: string, messageTypes: MessageType[]): ConnectionState {
    const connectionKey = `${projectId}_${messageTypes.sort().join('_')}`;
    return this.connectionStates.get(connectionKey) || ConnectionState.DISCONNECTED;
  }

  /**
   * Disconnect all connections for a project
   */
  disconnectProject(projectId: string): void {
    // Find all connections for this project
    for (const [connectionKey, ws] of this.connections.entries()) {
      if (connectionKey.startsWith(`${projectId}_`)) {
        this.cleanupConnection(connectionKey);
      }
    }
  }

  /**
   * Clean up all connections and resources
   */
  cleanup(): void {
    for (const connectionKey of this.connections.keys()) {
      this.cleanupConnection(connectionKey);
    }

    this.subscriptions.clear();
    this.reconnectTimeouts.clear();
    this.reconnectAttempts.clear();
  }
}

// Export singleton instance
export const webSocketManager = new WebSocketManager();

// React hook for using WebSocket manager
export const useWebSocket = (
  projectId: string,
  messageType: MessageType,
  callback: MessageCallback,
  enabled: boolean = true
) => {
  const subscriptionIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!enabled || !projectId) return;

    const subscriptionId = webSocketManager.subscribe(projectId, messageType, callback);
    subscriptionIdRef.current = subscriptionId;

    return () => {
      if (subscriptionIdRef.current) {
        webSocketManager.unsubscribe(projectId, messageType, subscriptionIdRef.current);
        subscriptionIdRef.current = null;
      }
    };
  }, [projectId, messageType, callback, enabled]);

  const sendMessage = useCallback((message: any) => {
    webSocketManager.sendMessage(projectId, [messageType], message);
  }, [projectId, messageType]);

  const connectionState = webSocketManager.getConnectionState(projectId, [messageType]);

  return {
    sendMessage,
    connectionState,
    isConnected: connectionState === ConnectionState.CONNECTED
  };
};