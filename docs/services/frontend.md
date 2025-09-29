# Frontend Service Documentation

## Service Overview

The Frontend service is a modern React-based web application that provides the user interface for the Migration Platform. It uses Mantine UI components with a professional SharePoint-like design system, implements client-side routing, and communicates with backend microservices via REST APIs and WebSocket connections.

**Port:** 3000
**Technology:** React, TypeScript, Mantine UI
**Routing:** React Router
**State Management:** React Context API

## Functionality

The Frontend service delivers a comprehensive web interface with the following capabilities:

- **Dashboard:** Real-time platform statistics and system health monitoring
- **Project Management:** CRUD operations for migration projects with detailed views
- **Document Processing:** File upload, processing status tracking, and document management
- **AI Agent Integration:** Crew management, workflow execution, and AI task monitoring
- **Settings Management:** LLM configuration, user management, and platform settings
- **Real-time Updates:** WebSocket connections for live logs, stats, and processing updates
- **Knowledge Base:** Document search and AI-powered query capabilities
- **Reporting:** Document generation and download management

## Application Structure

### Core Components
- **App.tsx:** Main application component with routing and providers
- **AppLayout:** Main layout wrapper with navigation and header
- **ErrorBoundary:** Global error handling and fallback UI

### Views
- **DashboardView:** Platform overview with statistics and health status
- **ProjectsView:** Project listing and management interface
- **ProjectDetailView:** Detailed project view with documents and AI interactions
- **SettingsView:** Platform configuration and management pages
- **LogsView:** Real-time log streaming and monitoring
- **CrewManagementView:** AI agent and crew configuration
- **LessonsLearnedView:** AI-generated insights and lessons learned

### Settings Pages
- **LLMConfigurationPage:** LLM provider and model management
- **UserManagementPage:** User administration and role management
- **PlatformServicesPage:** Service health and connectivity monitoring
- **GlobalDocumentTemplatesPage:** Document template management
- **EnvironmentVariablesPage:** Configuration management

## Key Components

### UI Framework
- **MantineProvider:** Theme and component configuration
- **ModalsProvider:** Modal dialog management
- **Notifications:** Toast notification system
- **Custom Theme:** SharePoint-inspired corporate blue color scheme

### State Management
- **NotificationContext:** Global notification state and handlers
- **LLMConfigContext:** LLM configuration state management
- **AssessmentContext:** Project assessment data management
- **LogContext:** Real-time log streaming state

### Specialized Components
- **FileUpload:** Document upload with drag-and-drop support
- **InteractiveGraphVisualizer:** Knowledge graph visualization
- **WebSocketManager:** Real-time communication handling
- **ModelManager:** AI model configuration interface
- **CrewAITerminal:** AI agent interaction terminal

## Data Flow

### API Communication
1. **REST API Calls:** HTTP requests to backend gateway for data operations
2. **WebSocket Connections:** Real-time subscriptions for logs, stats, and updates
3. **File Uploads:** Multipart form data for document processing
4. **Authentication:** JWT token management and automatic refresh

### State Updates
1. **Context Providers:** Centralized state management across components
2. **Real-time Sync:** WebSocket events trigger state updates
3. **Optimistic Updates:** UI updates before server confirmation
4. **Error Handling:** Graceful error states and retry mechanisms

### Navigation Flow
1. **Route-based Rendering:** React Router for client-side navigation
2. **Lazy Loading:** Code splitting for performance optimization
3. **Protected Routes:** Authentication-based route protection
4. **Breadcrumb Navigation:** Hierarchical navigation context

## Complete Working Details

### Technology Stack
- **React 18:** Modern React with hooks and concurrent features
- **TypeScript:** Type-safe development with interfaces and type checking
- **Mantine UI:** Professional component library with customization
- **React Router:** Client-side routing and navigation
- **Axios/WebSocket:** API communication and real-time updates

### Configuration
- **Environment Variables:** API endpoints and configuration settings
- **Theme Customization:** Corporate branding and design tokens
- **Component Overrides:** Custom styling for Mantine components
- **Responsive Design:** Mobile and desktop layout support

### Performance Optimizations
- **Code Splitting:** Lazy loading of route components
- **Memoization:** React.memo and useMemo for expensive operations
- **Virtual Scrolling:** Efficient rendering of large lists
- **Image Optimization:** Lazy loading and responsive images

### Security
- **JWT Authentication:** Secure token-based authentication
- **Input Validation:** Form validation and sanitization
- **XSS Protection:** Safe HTML rendering and content escaping
- **CSRF Protection:** Request forgery prevention

### Accessibility
- **Keyboard Navigation:** Full keyboard accessibility support
- **Screen Reader Support:** ARIA labels and semantic HTML
- **Color Contrast:** WCAG compliant color schemes
- **Focus Management:** Proper focus handling in modals and navigation

### Integration Points
- **Backend Gateway:** Primary API communication endpoint
- **Document Service:** File upload and processing operations
- **AI Agent Service:** Crew workflow management and execution
- **Reporting Service:** Document generation and download
- **Vector/Graph Services:** Knowledge base search and visualization

### Development Features
- **Hot Reload:** Fast development with live code updates
- **Error Boundaries:** Graceful error handling and debugging
- **Development Tools:** React DevTools integration
- **Type Checking:** TypeScript for compile-time error detection

The Frontend service provides a modern, professional interface that enables users to effectively manage cloud migration projects through an intuitive and responsive web application.