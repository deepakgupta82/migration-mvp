/**
 * Service Discovery Client for dynamic service location resolution
 * Queries the service registry at localhost:8011 for real-time service discovery
 */

export interface ServiceInfo {
  name: string;
  host: string;
  port: number;
  health_endpoint: string;
  status: string;
  last_check?: string;
  response_time?: number;
  version?: string;
  metadata?: Record<string, any>;
}

export interface ServiceRegistryResponse {
  services: Record<string, ServiceInfo>;
  summary: {
    total: number;
    healthy: number;
    unhealthy: number;
    error: number;
    timeout: number;
    unknown: number;
    health_percentage: number;
  };
  timestamp: string;
}

export interface CachedService {
  info: ServiceInfo;
  cachedAt: number;
  ttl: number;
}

export interface WebSocketMessage {
  type: 'initial_status' | 'health_update' | 'service_update' | 'ping';
  service_name?: string;
  status?: string;
  action?: string;
  timestamp?: string;
  data?: any;
}

/**
 * ServiceDiscoveryClient handles dynamic service discovery with caching and real-time updates
 */
export class ServiceDiscoveryClient {
  private static instance: ServiceDiscoveryClient;
  private cache: Map<string, CachedService> = new Map();
  private registryUrl: string;
  private cacheTtl: number = 30000; // 30 seconds default TTL
  private websocket: WebSocket | null = null;
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 5;
  private reconnectDelay: number = 1000;
  private listeners: Set<(message: WebSocketMessage) => void> = new Set();
  private isInitialized: boolean = false;

  private constructor(registryUrl: string = 'http://localhost:8011') {
    this.registryUrl = registryUrl;
  }

  public static getInstance(registryUrl?: string): ServiceDiscoveryClient {
    if (!ServiceDiscoveryClient.instance) {
      ServiceDiscoveryClient.instance = new ServiceDiscoveryClient(registryUrl);
    }
    return ServiceDiscoveryClient.instance;
  }

  /**
   * Initialize the service discovery client
   */
  public async initialize(): Promise<void> {
    if (this.isInitialized) return;

    try {
      // Initial service discovery
      await this.refreshServices();

      // Connect to WebSocket for real-time updates
      this.connectWebSocket();

      this.isInitialized = true;
      console.log('ServiceDiscoveryClient initialized successfully');
    } catch (error) {
      console.error('Failed to initialize ServiceDiscoveryClient:', error);
      throw error;
    }
  }

  /**
   * Get service URL with fallback mechanisms
   */
  public async getServiceUrl(serviceName: string, useHttps: boolean = false): Promise<string> {
    const service = await this.getService(serviceName);
    if (!service) {
      throw new Error(`Service ${serviceName} not found or unavailable`);
    }

    const protocol = useHttps ? 'https' : 'http';
    return `${protocol}://${service.host}:${service.port}`;
  }

  /**
   * Get service information with caching
   */
  public async getService(serviceName: string): Promise<ServiceInfo | null> {
    // Check cache first
    const cached = this.cache.get(serviceName);
    if (cached && this.isCacheValid(cached)) {
      return cached.info;
    }

    // Cache miss or expired, refresh services
    try {
      await this.refreshServices();
      const refreshed = this.cache.get(serviceName);
      return refreshed?.info || null;
    } catch (error) {
      console.error(`Failed to get service ${serviceName}:`, error);
      return null;
    }
  }

  /**
   * Get all available services
   */
  public async getAllServices(): Promise<Record<string, ServiceInfo>> {
    // Check if we have any cached services
    if (this.cache.size === 0 || this.shouldRefreshCache()) {
      await this.refreshServices();
    }

    const services: Record<string, ServiceInfo> = {};
    for (const [name, cached] of this.cache.entries()) {
      if (this.isCacheValid(cached)) {
        services[name] = cached.info;
      }
    }
    return services;
  }

  /**
   * Refresh service information from registry
   */
  public async refreshServices(): Promise<void> {
    try {
      const response = await fetch(`${this.registryUrl}/services`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        // Add timeout
        signal: AbortSignal.timeout(5000),
      });

      if (!response.ok) {
        throw new Error(`Registry request failed: ${response.status} ${response.statusText}`);
      }

      const data: ServiceRegistryResponse = await response.json();
      const now = Date.now();

      // Update cache with new data
      for (const [name, serviceInfo] of Object.entries(data.services)) {
        this.cache.set(name, {
          info: serviceInfo,
          cachedAt: now,
          ttl: this.cacheTtl,
        });
      }

      console.log(`Refreshed ${Object.keys(data.services).length} services from registry`);
    } catch (error) {
      console.error('Failed to refresh services from registry:', error);
      throw error;
    }
  }

  /**
   * Check if a service is healthy
   */
  public async isServiceHealthy(serviceName: string): Promise<boolean> {
    const service = await this.getService(serviceName);
    return service?.status === 'healthy';
  }

  /**
   * Get service health status
   */
  public async getServiceHealth(serviceName: string): Promise<string> {
    const service = await this.getService(serviceName);
    return service?.status || 'unknown';
  }

  /**
   * Set cache TTL in milliseconds
   */
  public setCacheTtl(ttlMs: number): void {
    this.cacheTtl = ttlMs;
  }

  /**
   * Add event listener for WebSocket messages
   */
  public addEventListener(callback: (message: WebSocketMessage) => void): void {
    this.listeners.add(callback);
  }

  /**
   * Remove event listener
   */
  public removeEventListener(callback: (message: WebSocketMessage) => void): void {
    this.listeners.delete(callback);
  }

  /**
   * Cleanup resources
   */
  public cleanup(): void {
    if (this.websocket) {
      this.websocket.close();
      this.websocket = null;
    }
    this.listeners.clear();
    this.cache.clear();
    this.isInitialized = false;
  }

  // Private methods

  private isCacheValid(cached: CachedService): boolean {
    return (Date.now() - cached.cachedAt) < cached.ttl;
  }

  private shouldRefreshCache(): boolean {
    // Refresh if more than half of cache entries are expired
    let expiredCount = 0;
    for (const cached of this.cache.values()) {
      if (!this.isCacheValid(cached)) {
        expiredCount++;
      }
    }
    return expiredCount > this.cache.size / 2;
  }

  private connectWebSocket(): void {
    if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      const wsUrl = `ws://localhost:8011/ws`;
      this.websocket = new WebSocket(wsUrl);

      this.websocket.onopen = () => {
        console.log('ServiceDiscoveryClient WebSocket connected');
        this.reconnectAttempts = 0;
      };

      this.websocket.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          this.handleWebSocketMessage(message);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      this.websocket.onclose = () => {
        console.log('ServiceDiscoveryClient WebSocket disconnected');
        this.attemptReconnect();
      };

      this.websocket.onerror = (error) => {
        console.error('ServiceDiscoveryClient WebSocket error:', error);
      };

    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
      this.attemptReconnect();
    }
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max WebSocket reconnect attempts reached');
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1); // Exponential backoff

    console.log(`Attempting WebSocket reconnect ${this.reconnectAttempts}/${this.maxReconnectAttempts} in ${delay}ms`);

    setTimeout(() => {
      this.connectWebSocket();
    }, delay);
  }

  private handleWebSocketMessage(message: WebSocketMessage): void {
    console.log('Received WebSocket message:', message);

    // Update cache based on message type
    if (message.type === 'health_update' && message.service_name) {
      const cached = this.cache.get(message.service_name);
      if (cached) {
        cached.info.status = message.status || 'unknown';
        cached.cachedAt = Date.now(); // Refresh cache timestamp
      }
    } else if (message.type === 'service_update' && message.service_name) {
      if (message.action === 'unregistered') {
        this.cache.delete(message.service_name);
      } else if (message.action === 'registered') {
        // Service registered, refresh cache
        this.refreshServices().catch(error =>
          console.error('Failed to refresh services after registration:', error)
        );
      }
    } else if (message.type === 'initial_status' && message.data) {
      // Update entire cache with initial status
      const data = message.data as ServiceRegistryResponse;
      const now = Date.now();
      for (const [name, serviceInfo] of Object.entries(data.services)) {
        this.cache.set(name, {
          info: serviceInfo,
          cachedAt: now,
          ttl: this.cacheTtl,
        });
      }
    }

    // Notify listeners
    for (const listener of this.listeners) {
      try {
        listener(message);
      } catch (error) {
        console.error('Error in WebSocket message listener:', error);
      }
    }
  }
}

// Export singleton instance
export const serviceDiscoveryClient = ServiceDiscoveryClient.getInstance();