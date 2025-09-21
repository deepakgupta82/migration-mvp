import React from 'react';

/**
 * Progress Update Queue System
 * Prevents race conditions and flickering in progress updates by ensuring
 * sequential processing of updates with optional debouncing.
 */

export interface ProgressUpdate {
  id: string;
  type: 'assessment' | 'batch' | 'processing' | 'websocket';
  progress: number;
  timestamp: number;
  priority?: 'low' | 'normal' | 'high';
  metadata?: Record<string, any>;
}

export interface QueueOptions {
  debounceMs?: number;
  maxQueueSize?: number;
  enableBatching?: boolean;
}

export class ProgressUpdateQueue {
  private queue: ProgressUpdate[] = [];
  private processing = false;
  private debounceTimer: NodeJS.Timeout | null = null;
  private onUpdate: (update: ProgressUpdate) => void;
  private options: Required<QueueOptions>;

  constructor(
    onUpdate: (update: ProgressUpdate) => void,
    options: QueueOptions = {}
  ) {
    this.onUpdate = onUpdate;
    this.options = {
      debounceMs: options.debounceMs ?? 100,
      maxQueueSize: options.maxQueueSize ?? 50,
      enableBatching: options.enableBatching ?? true,
    };
  }

  /**
   * Add a progress update to the queue
   */
  enqueue(update: Omit<ProgressUpdate, 'id' | 'timestamp'>): void {
    const fullUpdate: ProgressUpdate = {
      ...update,
      id: `${update.type}_${Date.now()}_${Math.random()}`,
      timestamp: Date.now(),
      priority: update.priority ?? 'normal',
    };

    // Remove duplicate updates of the same type (keep the latest)
    this.queue = this.queue.filter(item => item.type !== update.type);

    // Add to queue with priority ordering
    this.insertWithPriority(fullUpdate);

    // Enforce max queue size
    if (this.queue.length > this.options.maxQueueSize) {
      this.queue = this.queue.slice(-this.options.maxQueueSize);
    }

    this.scheduleProcessing();
  }

  /**
   * Insert update into queue with priority ordering
   */
  private insertWithPriority(update: ProgressUpdate): void {
    const priorityOrder = { high: 3, normal: 2, low: 1 };
    const insertIndex = this.queue.findIndex(
      item => priorityOrder[item.priority!] < priorityOrder[update.priority!]
    );

    if (insertIndex === -1) {
      this.queue.push(update);
    } else {
      this.queue.splice(insertIndex, 0, update);
    }
  }

  /**
   * Schedule processing with debouncing
   */
  private scheduleProcessing(): void {
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
    }

    this.debounceTimer = setTimeout(() => {
      this.processQueue();
    }, this.options.debounceMs);
  }

  /**
   * Process the queue sequentially
   */
  private async processQueue(): Promise<void> {
    if (this.processing || this.queue.length === 0) {
      return;
    }

    this.processing = true;

    try {
      while (this.queue.length > 0) {
        const update = this.queue.shift()!;
        await this.processUpdate(update);
      }
    } finally {
      this.processing = false;
    }
  }

  /**
   * Process a single update
   */
  private async processUpdate(update: ProgressUpdate): Promise<void> {
    try {
      this.onUpdate(update);
    } catch (error) {
      console.error('Error processing progress update:', error, update);
    }
  }

  /**
   * Clear all pending updates
   */
  clear(): void {
    this.queue = [];
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = null;
    }
  }

  /**
   * Get current queue status
   */
  getStatus() {
    return {
      queueLength: this.queue.length,
      processing: this.processing,
      nextUpdate: this.queue[0] || null,
    };
  }

  /**
   * Force immediate processing (useful for critical updates)
   */
  forceProcess(): void {
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = null;
    }
    this.processQueue();
  }
}

/**
 * React hook for using the progress update queue
 */
export const useProgressQueue = (
  onUpdate: (update: ProgressUpdate) => void,
  options?: QueueOptions
) => {
  const queueRef = React.useRef<ProgressUpdateQueue | null>(null);

  // Initialize queue
  React.useEffect(() => {
    queueRef.current = new ProgressUpdateQueue(onUpdate, options);
    return () => {
      queueRef.current?.clear();
    };
  }, [onUpdate, options]);

  const enqueue = React.useCallback(
    (update: Omit<ProgressUpdate, 'id' | 'timestamp'>) => {
      queueRef.current?.enqueue(update);
    },
    []
  );

  const clear = React.useCallback(() => {
    queueRef.current?.clear();
  }, []);

  const forceProcess = React.useCallback(() => {
    queueRef.current?.forceProcess();
  }, []);

  const getStatus = React.useCallback(() => {
    return queueRef.current?.getStatus() || { queueLength: 0, processing: false, nextUpdate: null };
  }, []);

  return {
    enqueue,
    clear,
    forceProcess,
    getStatus,
  };
};