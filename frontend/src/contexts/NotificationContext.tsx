/**
 * Notification Context - Centralized notification management
 * Tracks all user interactions, file uploads, assessments, and errors
 */

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';

export interface AppNotification {
  id: string;
  title: string;
  message: string;
  type: 'success' | 'error' | 'warning' | 'info';
  timestamp: Date;
  read: boolean;
  projectId?: string;
  projectName?: string;
  metadata?: Record<string, any>;
  correlationId?: string; // Added for tracking user-initiated tasks
}

interface NotificationContextType {
  notifications: AppNotification[];
  unreadCount: number;
  addNotification: (notification: Omit<AppNotification, 'id' | 'timestamp' | 'read'>) => void;
  markAsRead: (id: string) => void;
  markAllAsRead: () => void;
  clearNotification: (id: string) => void;
  clearAllNotifications: () => void;
  fetchNotifications: () => void;
}

const NotificationContext = createContext<NotificationContextType | undefined>(undefined);

export const useNotifications = () => {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotifications must be used within a NotificationProvider');
  }
  return context;
};

interface NotificationProviderProps {
  children: React.ReactNode;
}

export const NotificationProvider: React.FC<NotificationProviderProps> = ({ children }) => {
  // Real notifications fetched from collaboration service
  const [notifications, setNotifications] = useState<AppNotification[]>([]);

  // Fetch notifications from collaboration service
  const fetchNotifications = useCallback(async () => {
    try {
      // For now, use a default user_id. In a real app, this would come from auth context
      const userId = 'user_001';
      const response = await fetch(`http://localhost:8016/users/${userId}/notifications`);
      
      if (response.ok) {
        const data = await response.json();
        const fetchedNotifications = data.notifications?.map((notification: any) => ({
          id: notification.notification_id,
          title: notification.title,
          message: notification.message,
          type: mapNotificationType(notification.notification_type),
          timestamp: new Date(notification.created_at),
          read: notification.is_read,
          projectId: notification.workspace_id,
          projectName: notification.metadata?.project_name,
          metadata: notification.metadata,
          correlationId: notification.correlation_id
        })) || [];
        
        setNotifications(fetchedNotifications);
      }
    } catch (error) {
      console.error('Failed to fetch notifications:', error);
      // Keep existing notifications on error
    }
  }, []);

  // Map backend notification types to frontend types
  const mapNotificationType = (backendType: string): 'success' | 'error' | 'warning' | 'info' => {
    switch (backendType) {
      case 'success':
      case 'task_completed':
        return 'success';
      case 'error':
      case 'urgent':
        return 'error';
      case 'warning':
        return 'warning';
      case 'info':
      case 'task_assigned':
      case 'file_shared':
      case 'meeting_invitation':
      case 'mention':
      default:
        return 'info';
    }
  };

  // Load notifications on component mount and set up periodic refresh
  useEffect(() => {
    fetchNotifications();
    
    // Refresh notifications every 30 seconds
    const interval = setInterval(fetchNotifications, 30000);
    
    return () => clearInterval(interval);
  }, [fetchNotifications]);

  const addNotification = useCallback((notification: Omit<AppNotification, 'id' | 'timestamp' | 'read'>) => {
    const newNotification: AppNotification = {
      ...notification,
      id: Date.now().toString() + Math.random().toString(36).substr(2, 9),
      timestamp: new Date(),
      read: false,
    };

    setNotifications(prev => [newNotification, ...prev]);
  }, []);

  const markAsRead = useCallback((id: string) => {
    setNotifications(prev =>
      prev.map(notification =>
        notification.id === id ? { ...notification, read: true } : notification
      )
    );
  }, []);

  const markAllAsRead = useCallback(() => {
    setNotifications(prev =>
      prev.map(notification => ({ ...notification, read: true }))
    );
  }, []);

  const clearNotification = useCallback((id: string) => {
    setNotifications(prev => prev.filter(notification => notification.id !== id));
  }, []);

  const clearAllNotifications = useCallback(() => {
    setNotifications([]);
  }, []);

  const unreadCount = notifications.filter(n => !n.read).length;

  const value: NotificationContextType = {
    notifications,
    unreadCount,
    addNotification,
    markAsRead,
    markAllAsRead,
    clearNotification,
    clearAllNotifications,
    fetchNotifications,
  };

  return (
    <NotificationContext.Provider value={value}>
      {children}
    </NotificationContext.Provider>
  );
};

export default NotificationContext;
