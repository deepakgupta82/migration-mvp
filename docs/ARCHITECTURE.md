# Migration Platform Architecture

## Overview

The Nagarro Ascent Migration Platform is a comprehensive cloud migration and AI-powered knowledge management system built on a microservices architecture. The platform provides end-to-end support for cloud migration projects, including document processing, AI agent orchestration, knowledge management, and real-time collaboration.

## High-Level Architecture

The platform follows a microservices architecture with the following key components:

- **Frontend**: React/TypeScript single-page application
- **Backend**: FastAPI-based API gateway and core services
- **Services Layer**: Specialized microservices for different domains
- **Data Layer**: Multiple databases for different data types
- **Infrastructure**: Kubernetes-based deployment with cloud provider support

### Architecture Diagram

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │     Backend     │    │   Services      │
│   (React/TS)    │◄──►│   (FastAPI)     │◄──►│   (Microservices)│
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
          │                       │                       │
          ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   WebSocket     │    │   PostgreSQL    │    │   Vector DB     │
│   Services      │    │   (Relational)  │    │   (Weaviate)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                          │
┌─────────────────┐    ┌─────────────────┐               │
│   Redis         │    │   Neo4j         │◄──────────────┘
│   (Cache)       │    │   (Graph)       │
└─────────────────┘    └─────────────────┘
```

## Tech Stack

### Backend & Services
- **Language**: Python 3.9+
- **Framework**: FastAPI with Uvicorn ASGI server
- **API Documentation**: OpenAPI/Swagger
- **Authentication**: JWT tokens, service-to-service auth
- **Logging**: Structured JSON logging with Loki integration
- **Health Monitoring**: Kubernetes probes, service registry

### Frontend
- **Language**: TypeScript
- **Framework**: React 18 with React Router
- **UI Library**: Mantine UI components
- **State Management**: React Context, custom hooks
- **HTTP Client**: Axios
- **Build Tool**: Create React App

### Data Storage
- **Primary Database**: PostgreSQL (relational data, user management, projects)
- **Cache**: Redis (session storage, temporary data)
- **Vector Database**: Weaviate (embeddings for RAG)
- **Graph Database**: Neo4j (knowledge graphs, relationships)
- **Object Storage**: MinIO (document storage)
- **Search/Indexing**: Weaviate (semantic search)

### AI/ML Stack
- **LLM Providers**: OpenAI, Anthropic, Google Vertex AI, Google Generative AI
- **Embeddings**: LangChain ecosystem
- **Agent Framework**: CrewAI, AutoGen
- **Document Processing**: Custom parsers, OCR (Tesseract)

### Infrastructure
- **Containerization**: Docker
- **Orchestration**: Kubernetes
- **Service Discovery**: Custom service registry
- **Load Balancing**: NGINX ingress
- **Monitoring**: Prometheus metrics
- **Logging**: Loki with Grafana
- **CI/CD**: GitHub Actions (inferred from .github directory)

## Services Overview

### Core Services

#### Service Registry (Port 8011)
- **Purpose**: Service discovery and health monitoring
- **Responsibilities**:
  - Register/unregister services
  - Health checks and status monitoring
  - Real-time health notifications via WebSocket
  - Docker container monitoring
- **Dependencies**: Docker API, PostgreSQL, Redis

#### Backend Gateway (Port 8000)
- **Purpose**: API gateway and core business logic
- **Responsibilities**:
  - Request routing and authentication
  - Project management coordination
  - Document processing orchestration
  - CrewAI agent management
- **Dependencies**: PostgreSQL, Redis, all microservices

#### Project Service (Port 8002)
- **Purpose**: Project lifecycle management
- **Responsibilities**:
  - Project CRUD operations
  - Deliverable management
  - Template handling
  - Generation request processing
- **Dependencies**: PostgreSQL, Alembic migrations

#### LLM Service (Port 8007)
- **Purpose**: Large Language Model orchestration
- **Responsibilities**:
  - LLM provider management and configuration
  - Rate limiting and usage tracking
  - Model testing and validation
  - Caching and optimization
- **Dependencies**: Redis, PostgreSQL, external LLM APIs

#### Graph Service (Port 8006)
- **Purpose**: Knowledge graph management
- **Responsibilities**:
  - Neo4j database operations
  - Entity extraction from documents
  - Relationship mapping and graph construction
  - Infrastructure topology visualization
- **Dependencies**: Neo4j, Redis

#### Knowledge Service (Port 8017)
- **Purpose**: Advanced RAG and knowledge management
- **Responsibilities**:
  - Semantic search and retrieval
  - Knowledge graph construction
  - Context-aware question answering
  - Document indexing and curation
- **Dependencies**: Vector service, LLM service, storage service

#### AI Agent Service (Port 8008)
- **Purpose**: AI agent orchestration
- **Responsibilities**:
  - CrewAI workflow management
  - AutoGen copilot integration
  - Multi-agent task orchestration
  - Real-time agent communication
- **Dependencies**: LLM service, project service, WebSocket service

### Supporting Services

#### Document Service (Port 8003)
- **Purpose**: Document processing and analysis
- **Responsibilities**:
  - Document upload and parsing
  - Text extraction and OCR
  - Document classification
  - Metadata extraction

#### Vector Service (Port 8005)
- **Purpose**: Vector embeddings and similarity search
- **Responsibilities**:
  - Embedding generation
  - Vector storage and retrieval
  - Similarity search operations
- **Dependencies**: Weaviate, embedding models

#### Storage Service (Port 8010)
- **Purpose**: File storage and management
- **Responsibilities**:
  - File upload/download
  - Metadata management
  - Storage optimization
- **Dependencies**: MinIO

#### WebSocket Service (Port 8009)
- **Purpose**: Real-time communication
- **Responsibilities**:
  - WebSocket connections
  - Real-time notifications
  - Live updates and streaming
- **Dependencies**: Redis pub/sub

#### Analytics Service (Port 8014)
- **Purpose**: Data analytics and reporting
- **Responsibilities**:
  - Usage analytics
  - Performance metrics
  - Report generation
- **Dependencies**: PostgreSQL, Redis

#### Stats Service (Port 8004)
- **Purpose**: Platform statistics
- **Responsibilities**:
  - Real-time metrics collection
  - Dashboard data provision
  - Performance monitoring
- **Dependencies**: PostgreSQL, WebSocket

#### Security Service (Port 8015)
- **Purpose**: Security and access control
- **Responsibilities**:
  - Authentication and authorization
  - Security scanning
  - Compliance monitoring

#### Collaboration Service (Port 8016)
- **Purpose**: Team collaboration features
- **Responsibilities**:
  - Real-time collaboration
  - Comment systems
  - Version control integration

## Data Flow

### Document Processing Flow
1. **Upload**: Documents uploaded via frontend to storage service
2. **Processing**: Document service extracts text and metadata
3. **Indexing**: Vector service generates embeddings and stores in Weaviate
4. **Graph Building**: Graph service creates knowledge graph in Neo4j
5. **Search Ready**: Knowledge service enables semantic search

### AI Agent Workflow
1. **Request**: User initiates agent workflow via frontend
2. **Orchestration**: AI agent service coordinates CrewAI agents
3. **LLM Processing**: LLM service provides model access and caching
4. **Knowledge Retrieval**: Knowledge service provides context via RAG
5. **Real-time Updates**: WebSocket service streams progress to frontend

### Project Management Flow
1. **Creation**: Projects created via project service
2. **Document Association**: Documents linked to projects
3. **Agent Processing**: AI agents analyze project documents
4. **Knowledge Building**: Insights stored in knowledge graph
5. **Reporting**: Analytics service generates project reports

## Service Interactions

Services communicate through:
- **HTTP REST APIs**: Primary communication method
- **WebSocket**: Real-time updates and streaming
- **Shared Databases**: PostgreSQL for relational data, Redis for cache
- **Message Queues**: Redis pub/sub for async communication
- **Service Registry**: Dynamic service discovery

### Key Integration Points

#### Service Client
- Centralized HTTP client for service-to-service communication
- Automatic authentication headers
- Correlation ID propagation
- Timeout and retry handling

#### Shared Libraries
- Common utilities in `common/` directory
- Shared data models and DTOs
- Configuration management
- Logging and monitoring utilities

## Deployment

### Kubernetes Deployment
- **Orchestration**: Kubernetes clusters
- **Services**: Deployed as individual pods
- **Databases**: StatefulSets with persistent volumes
- **Ingress**: NGINX ingress controller
- **ConfigMaps/Secrets**: Environment-specific configuration

### Cloud Providers
- **AWS**: ECS, Lambda, RDS, S3 via Terraform modules
- **Azure**: Azure services integration
- **Multi-cloud**: Hybrid deployments supported

### Development Environment
- **Local Development**: Docker Compose for local services
- **Hot Reload**: Services support development mode with auto-reload
- **Service Registry**: Local service discovery and health monitoring

## Security

### Authentication & Authorization
- JWT-based authentication
- Service-to-service tokens
- Role-based access control
- API key management for external services

### Data Protection
- Encrypted data at rest and in transit
- Secure API communication
- Input validation and sanitization
- Rate limiting and abuse prevention

## Monitoring & Observability

### Health Checks
- Kubernetes readiness/liveness probes
- Service-level health endpoints
- Dependency health monitoring
- Circuit breaker patterns

### Logging
- Structured JSON logging
- Correlation ID tracking
- Loki aggregation
- Grafana dashboards

### Metrics
- Prometheus metrics collection
- Custom business metrics
- Performance monitoring
- Error tracking

## Scalability Considerations

### Horizontal Scaling
- Stateless services can scale horizontally
- Database read replicas for read-heavy workloads
- Load balancing across service instances

### Data Partitioning
- Project-based data isolation
- Sharding strategies for large datasets
- Cache optimization for frequently accessed data

### Performance Optimization
- Async processing for heavy operations
- Caching layers (Redis, application-level)
- Optimized database queries
- CDN integration for static assets

## Development & Deployment Workflow

### Local Development
1. Services run in development mode with hot reload
2. Docker Compose for external dependencies
3. Local databases and caches
4. Service registry for local discovery

### CI/CD Pipeline
1. Code committed to repository
2. Automated testing and linting
3. Docker image building
4. Kubernetes deployment
5. Health checks and rollbacks

### Environment Management
- Multiple environments (dev, staging, prod)
- Environment-specific configurations
- Secret management
- Blue-green deployments

This architecture provides a robust, scalable foundation for AI-powered cloud migration and knowledge management, with clear separation of concerns and comprehensive monitoring capabilities.