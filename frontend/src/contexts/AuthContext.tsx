import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

// Enhanced user interface with backward compatibility
interface User {
  id: string;
  email: string;
  username?: string;
  firstName?: string;
  lastName?: string;
  role: 'platform_admin' | 'project_admin' | 'project_user' | 'user' | 'admin'; // Added 'admin' for backward compatibility
  isActive: boolean;
  lastLogin?: string;
  projectRoles?: ProjectRole[];
}

interface ProjectRole {
  projectId: string;
  projectName: string;
  role: string;
  assignedAt: string;
  assignedBy?: string;
}

interface AuthContextType {
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  hasPermission: (permission: string, projectId?: string) => boolean;
  isLoading: boolean;
  enhancedMode: boolean;
  setEnhancedMode: (enabled: boolean) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  // Start with existing hardcoded user for backward compatibility
  const [user, setUser] = useState<User | null>({
    id: '1',
    email: 'admin@nagarro.com',
    role: 'admin', // Use 'admin' for backward compatibility with existing UI
    isActive: true,
    // NEW fields default to undefined (backward compatible)
  });

  const [isLoading, setIsLoading] = useState(false);
  const [enhancedMode, setEnhancedMode] = useState(false);

  // Load enhanced mode preference from localStorage
  useEffect(() => {
    const savedEnhancedMode = localStorage.getItem('authEnhancedMode');
    if (savedEnhancedMode) {
      setEnhancedMode(JSON.parse(savedEnhancedMode));
    }
  }, []);

  // Save enhanced mode preference to localStorage
  useEffect(() => {
    localStorage.setItem('authEnhancedMode', JSON.stringify(enhancedMode));
  }, [enhancedMode]);

  const login = async (email: string, password: string): Promise<void> => {
    setIsLoading(true);
    try {
      // TODO: Implement actual login API call
      // For now, simulate login with hardcoded user
      await new Promise(resolve => setTimeout(resolve, 1000)); // Simulate API call
      
      setUser({
        id: '1',
        email: email,
        username: email.split('@')[0],
        firstName: 'Admin',
        lastName: 'User',
        role: 'platform_admin',
        isActive: true,
        lastLogin: new Date().toISOString(),
      });
    } catch (error) {
      throw new Error('Login failed');
    } finally {
      setIsLoading(false);
    }
  };

  const logout = (): void => {
    setUser(null);
    localStorage.removeItem('authToken');
  };

  const hasPermission = (permission: string, projectId?: string): boolean => {
    if (!user) return false;

    // Helper function to check if user is platform admin (backward compatible)
    const isPlatformAdmin = user.role === 'platform_admin' || user.role === 'admin';

    // EXISTING behavior for platform_admin (UNCHANGED)
    if (isPlatformAdmin) return true;

    // NEW enhanced permission logic (ADDITIVE)
    switch (permission) {
      case 'view_users':
      case 'manage_users':
      case 'manage_platform_settings':
        return isPlatformAdmin;

      case 'view_project':
      case 'edit_project':
        if (isPlatformAdmin) return true;
        if (!projectId || !user.projectRoles) return false;

        const projectRole = user.projectRoles.find(pr => pr.projectId === projectId);
        return projectRole !== undefined;

      case 'manage_project_users':
        if (isPlatformAdmin) return true;
        if (!projectId || !user.projectRoles) return false;

        const adminRole = user.projectRoles.find(
          pr => pr.projectId === projectId && pr.role === 'project_admin'
        );
        return adminRole !== undefined;

      default:
        return false;
    }
  };

  const contextValue: AuthContextType = {
    user,
    login,
    logout,
    hasPermission,
    isLoading,
    enhancedMode,
    setEnhancedMode,
  };

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

// Utility functions for permission checking
export const checkPermission = (
  user: User | null,
  permission: string,
  projectId?: string
): boolean => {
  if (!user) return false;

  // Helper function to check if user is platform admin (backward compatible)
  const isPlatformAdmin = user.role === 'platform_admin' || user.role === 'admin';

  if (isPlatformAdmin) return true;

  switch (permission) {
    case 'view_users':
    case 'manage_users':
    case 'manage_platform_settings':
      return isPlatformAdmin;

    case 'view_project':
    case 'edit_project':
      if (!projectId || !user.projectRoles) return false;
      return user.projectRoles.some(pr => pr.projectId === projectId);

    case 'manage_project_users':
      if (!projectId || !user.projectRoles) return false;
      return user.projectRoles.some(
        pr => pr.projectId === projectId && pr.role === 'project_admin'
      );

    default:
      return false;
  }
};

export default AuthContext;
