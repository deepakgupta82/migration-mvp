# Frontend Architecture Documentation

## Frontend Overview

The frontend is a modern React-based single-page application (SPA) designed for the Nagarro Ascent migration platform. It provides a professional, SharePoint-like interface for managing cloud migration assessment projects, featuring real-time monitoring, AI-powered analysis, and comprehensive project management capabilities.

The application is built with a modular architecture using React 18, TypeScript, and Mantine UI components, with lazy-loaded views for optimal performance. It communicates with multiple backend microservices through a centralized API service layer with dynamic service discovery.

## Tech Stack

### Core Framework
- **React 18.2.0** - Modern React with concurrent features and hooks
- **TypeScript 5.4.5** - Type-safe JavaScript with strict mode enabled
- **React Router DOM 6.26.0** - Client-side routing for SPA navigation

### UI Framework
- **Mantine 7.0.0** - Modern React UI library with comprehensive component suite
- **Mantine Hooks 7.0.0** - Utility hooks for enhanced functionality
- **Mantine Dropzone 7.17.8** - File upload components
- **Mantine Modals 7.17.8** - Modal dialog management
- **Mantine Notifications 7.17.8** - Toast notification system

### Additional Libraries
- **Axios 1.6.0** - HTTP client for API requests
- **React Force Graph 2D 1.28.0** - Interactive graph visualization
- **React Markdown 8.0.0** - Markdown rendering with syntax highlighting
- **React Window 1.8.11** - Virtualized lists for performance
- **UUID 11.1.0** - Unique identifier generation
- **Tabler Icons React 3.34.1** - Comprehensive icon library

### Development Tools
- **React Scripts 5.0.1** - Create React App build tooling
- **ESLint** - Code linting with React-specific rules
- **TypeScript Compiler** - Type checking and compilation

### Build Configuration
- **Webpack** (via React Scripts) - Module bundling
- **Babel** - JavaScript transpilation
- **PostCSS** - CSS processing
- **Proxy Configuration** - Development proxy to `http://localhost:8000`

## Key Components

### Layout Components
- **AppLayout** - Main application layout with navigation sidebar
- **ErrorBoundary** - Global error handling and fallback UI

### Core Views
- **DashboardView** - Main dashboard with project statistics and recent projects
- **ProjectsView** - Project listing and management interface
- **ProjectDetailView** - Detailed project view with document management
- **SettingsView** - Application configuration interface
- **LogsView** - System and application logs viewer
- **SystemLogsView** - Backend service logs monitoring
- **CrewManagementView** - AI agent crew configuration
- **LessonsLearnedView** - Knowledge base and insights

### Settings Pages
- **LLMConfigurationPage** - Language model provider settings
- **OAuthAuthenticationPage** - Authentication configuration
- **UserManagementPage** - User and role management
- **KnowledgeBasePage** - Knowledge repository settings
- **EnvironmentVariablesPage** - System environment configuration
- **PlatformServicesPage** - Backend service management
- **AIAgentsPage** - AI agent configuration
- **GlobalDocumentTemplatesPage** - Document template management
- **ChunkingEmbeddingPage** - Data processing settings
- **ModelManager** - AI model management interface
- **LLMPromptsPage** - LLM prompts discovery and editing

### Feature Components
- **FileUpload** - Drag-and-drop file upload interface
- **InteractiveGraphVisualizer** - Knowledge graph visualization
- **AnalyticsDashboard** - Project analytics and metrics
- **BatchAnalysisMonitor** - Batch processing status tracking
- **ProcessingProgressView** - Document processing progress
- **MinIODirectoryBrowser** - Object storage file browser
- **FloatingChatWidget** - AI assistant chat interface
- **LiveConsole** - Real-time command execution interface
- **ReportDisplay** - Assessment report viewer
- **StructuredDataDisplay** - JSON/structured data viewer
- **JsonlAnalysisDisplay** - JSONL format analysis results

### Utility Components
- **CriticalSystemBanner** - System status alerts
- **ServiceHealthBanner** - Backend service health indicators
- **PerformanceMonitor** - System performance metrics
- **MetricsVisualization** - Data visualization components
- **MetricsExport** - Data export functionality
- **QualityScoresDisplay** - Analysis quality metrics
- **RightLogPane** - Log display panel
- **TestLLMModal** - LLM testing interface
- **LLMConfigSelector** - Model configuration selector
- **LLMConfigurationModal** - LLM settings modal
- **ProcessLLMConfiguration** - Processing configuration
- **Notification Components** - Toast and alert systems

## API Integrations

### Service Architecture
The frontend integrates with multiple backend microservices through a centralized API service layer:

- **API Gateway** (`http://localhost:8000`) - Main entry point for all API calls
- **Project Service** (`http://localhost:8002`) - Project management and metadata
- **Stats Service** (`http://localhost:8004`) - Real-time statistics and monitoring
- **Document Service** (`http://localhost:8003`) - Document processing and analysis
- **AI Agent Service** (`http://localhost:8008`) - AI agent and AutoGen functionality
- **Notification Service** (`http://localhost:8016`) - User notifications
- **Knowledge Service** - RAG and knowledge base queries

### Service Discovery
The application uses dynamic service discovery with fallback URLs for resilience:
- Services are discovered via service registry on port 8011
- Automatic fallback to environment variables if discovery fails
- Health checks ensure service availability before routing requests

### Authentication
- Service-to-service authentication using bearer tokens
- Correlation ID tracking for request tracing
- WebSocket authentication for real-time connections

### Key API Endpoints

#### Project Management
- `GET/POST/PUT/DELETE /api/projects` - CRUD operations
- `POST /api/projects/{id}/upload` - File uploads
- `GET /api/projects/{id}/files` - File listings
- `DELETE /api/projects/{id}/files/{fileId}` - File deletion

#### Document Processing
- `POST /api/projects/{id}/process-selected` - Batch processing
- `GET /api/documents/{id}/search` - Content search
- `POST /api/documents/{id}/analyze` - Document analysis
- `GET /api/documents/{id}/content/{filename}` - Content retrieval

#### Knowledge Base
- `POST /api/projects/{id}/chat` - AI chat queries
- `POST /api/projects/{id}/query` - Knowledge queries
- `GET /api/projects/{id}/discoveries` - Extracted insights

#### Real-time Features
- WebSocket: `ws://localhost:8000/ws/platform-stats` - Platform statistics
- WebSocket: `ws://localhost:8000/ws/project-stats/{id}` - Project statistics
- WebSocket: `ws://localhost:8000/ws/run_assessment/{id}` - Assessment monitoring

#### AI Agent Integration
- `POST /api/autogen/discussions/start` - Start AI discussions
- `POST /api/autogen/discussions/{id}/query` - Continue discussions
- WebSocket: `ws://localhost:8008/ws/autogen/{sessionId}` - Real-time AI interactions

## Data Flow

### Request Flow
1. **User Interaction** - UI components trigger actions (button clicks, form submissions)
2. **Hook Layer** - Custom hooks handle state management and API calls
3. **Context Layer** - React contexts manage global application state
4. **API Service** - Centralized service handles HTTP requests with service discovery
5. **Backend Services** - Microservices process requests and return data
6. **Response Flow** - Data flows back through the same layers, updating UI

### State Management
- **React Context** - Global state management for:
  - Assessment data (`AssessmentContext`)
  - Authentication (`AuthContext`)
  - LLM configuration (`LLMConfigContext`)
  - Logging (`LogContext`)
  - Notifications (`NotificationContext`)

### Real-time Updates
- **WebSocket Connections** - Real-time data streaming for:
  - Platform statistics updates
  - Project processing status
  - Assessment progress
  - AI agent conversations
- **Event-driven Architecture** - Components subscribe to context changes for reactive updates

### Data Persistence
- **Local State** - Component-level state for UI interactions
- **Context State** - Application-wide state persistence
- **Server State** - Backend services maintain authoritative data
- **Optimistic Updates** - UI updates immediately, reconciled with server responses

## User Interface Details

### Design System
- **Corporate Theme** - SharePoint-inspired blue (#0072c6) and professional gray palette
- **Typography** - Segoe UI font family with structured hierarchy (h1-h6)
- **Component Styling** - Consistent border radius, shadows, and spacing
- **Responsive Design** - Mobile-first approach with adaptive layouts

### Layout Structure
- **Navigation Sidebar** - Collapsible navigation with active state indicators
- **Main Content Area** - Flexible layout adapting to content
- **Header Bar** - Application branding and user controls
- **Footer** - System status and version information

### Key UI Patterns
- **Card-based Layout** - Information organized in elevated cards
- **Data Tables** - Sortable, filterable tables with action menus
- **Progress Indicators** - Loading states and processing progress
- **Status Badges** - Color-coded status indicators
- **Modal Dialogs** - Contextual actions and confirmations
- **Toast Notifications** - Non-intrusive status messages

### Interactive Features
- **File Upload** - Drag-and-drop with progress tracking
- **Graph Visualization** - Interactive knowledge graphs with ForceGraph2D
- **Real-time Monitoring** - Live statistics and processing status
- **Search and Filter** - Advanced data filtering capabilities
- **Batch Operations** - Multi-item selection and processing
- **AI Chat Interface** - Conversational AI assistant

### Accessibility
- **Keyboard Navigation** - Full keyboard accessibility
- **Screen Reader Support** - ARIA labels and semantic HTML
- **Color Contrast** - WCAG-compliant color ratios
- **Focus Management** - Proper focus indicators and tab order

### Performance Optimizations
- **Lazy Loading** - Route-based code splitting
- **Virtual Scrolling** - Efficient rendering of large lists
- **Memoization** - React.memo and useMemo for expensive operations
- **Bundle Splitting** - Optimized chunk loading
- **Image Optimization** - Efficient asset loading

## Settings → LLM Prompts

A dedicated page in the left navigation lets you discover, edit, and hot-reload prompts across services.

- Navigate to Settings → LLM Prompts.
- Select a service in the left column; prompts appear in the center table.
- Click Edit to open a modal editor for purpose, description, variables, and template text.
- Saving writes to the repo and triggers a reload of the target service.

This frontend architecture provides a robust, scalable, and user-friendly interface for the migration assessment platform, enabling efficient project management and AI-powered analysis workflows.