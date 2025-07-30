# Nagarro AgentiMigrate - Enterprise Architecture

**Version:** 2.0
**Audience:** Enterprise & Solutions Architects
**Status:** As-Built (Q3 2025)

## 1. Executive Summary

Nagarro AgentiMigrate is an intelligent, multi-cloud modernization platform designed to automate and de-risk the enterprise cloud transformation lifecycle. It employs a framework of collaborative, specialized AI agents to execute the entire pre-migration journey—from deep-state discovery and dependency mapping to strategic planning and deliverable generation.

This document details the platform's technical architecture, which is founded on principles of Zero-Trust security, Domain-Driven Design, and full auditability to meet the stringent requirements of enterprise environments.

---

## 2. Architectural Principles

The platform's design is governed by the following tenets:

*   **Zero-Trust, Client-Perimeter Deployment:** The entire platform is architected to run within the client's own cloud environment (VPC/VNet) or on-premises. This foundational security principle eliminates data exfiltration and complex data residency concerns. All inter-service communication is designed to be encrypted.
*   **Domain-Driven, Composable Design:** The system is decomposed into bounded contexts (Project Management, Assessment, Reporting) realized as independent microservices. This promotes clear ownership, independent scalability, and technological flexibility.
*   **Asynchronous & Real-Time Communication:** The platform uses a combination of synchronous REST APIs for direct commands and WebSockets for real-time, long-running agentic workflows. This ensures a responsive user experience while supporting complex background processing.
*   **Polyglot Persistence:** We employ a "best tool for the job" database strategy. The platform utilizes a mix of relational (PostgreSQL), graph (Neo4j), vector (Weaviate), and object (MinIO) storage, each chosen for its suitability to model a specific type of data (state, relationships, semantics, and artifacts).
*   **Glass Box AI & Full Auditability:** Agent decision-making is not a black box. Every agent action, tool invocation, and generated artifact is logged, providing a complete audit trail for governance, diagnostics, and building trust in the AI's conclusions.
*   **Cloud-Agnostic by Design:** The core logic is designed to be portable. The use of containerization and environment-based configuration allows the platform to be deployed on any major cloud provider (AWS, Azure, GCP) or on-premises with minimal changes.

---

## 3. System Architecture & Components

The platform is a set of containerized microservices orchestrated by Docker Compose for local deployment and designed for Kubernetes in production.

 *(Placeholder for a visual diagram)*

### Core Services

*   **Frontend (Command Center):** A React (TypeScript) single-page application with comprehensive UI/UX providing:
    *   Project management with real-time statistics and metrics
    *   Dual-workflow file upload and processing interface
    *   Real-time assessment monitoring with persistent progress tracking
    *   Interactive chat interface for document Q&A
    *   Professional document generation and download capabilities
    *   Responsive design with draggable panels and optimized layouts

*   **Backend (Assessment Service):** A FastAPI (Python) service with comprehensive logging and dual-workflow architecture:
    *   **Phase 1 - Knowledge Base Creation:** Document processing pipeline with MinIO integration
    *   **Phase 2A - Agent-Driven Assessment:** CrewAI orchestration for specialized agent crews
    *   **Phase 2B - Lightweight Chat:** Direct RAG queries without full agent crew overhead
    *   WebSocket communication for real-time progress tracking
    *   Multi-provider LLM integration with fallback mechanisms
    *   Comprehensive error handling and audit logging

*   **Project Service:** A dedicated FastAPI (Python) service with enhanced authentication:
    *   UUID-based user management and service-to-service authentication
    *   Platform settings management for LLM configurations
    *   Full RBAC (Role-Based Access Control) security model
    *   Project lifecycle management with status tracking
    *   File metadata management and statistics

*   **Reporting Service:** A FastAPI (Python) service for enterprise-grade deliverable generation:
    *   Professional PDF and DOCX document generation using Pandoc and LaTeX
    *   Integration with MinIO for artifact storage and retrieval
    *   Template-based document generation with project-specific data
    *   Download management with proper MIME type handling

*   **MegaParse Service:** Enhanced document parsing service:
    *   Multi-format document parsing (PDF, DOCX, PPTX, etc.)
    *   Clean text extraction optimized for RAG pipeline ingestion
    *   Error handling for corrupted or unsupported file formats

### Data Stores

*   **PostgreSQL (Relational):** The primary data store for the `Project Service`. It holds structured data like projects, users, files, and settings. Its transactional nature ensures data integrity.
*   **Weaviate (Vector):** The core of the RAG pipeline. It stores document chunks as vector embeddings, enabling powerful semantic search capabilities.
*   **Neo4j (Graph):** Stores the "digital twin" of the client's IT landscape. It models entities (servers, applications, databases) and their explicit relationships (e.g., `HOSTS`, `CONNECTS_TO`), enabling complex dependency analysis.
*   **MinIO (Object Storage):** An S3-compatible object store serving as the primary file storage system:
    *   **Project Files:** All uploaded documents stored in `project-files` bucket
    *   **Generated Reports:** PDF and DOCX deliverables in `reports` bucket
    *   **Architecture Diagrams:** Generated diagrams in `diagrams` bucket
    *   **Temporary Processing:** Staging area for document processing workflows
    *   **Backup and Templates:** Configuration templates and backup artifacts

---

## 4. Data Flow: A Typical Assessment

1.  **Project Creation:** A user creates a project in the **Frontend**. The request goes to the **Backend**, which proxies it to the **Project Service**. The **Project Service** creates a new project record in **PostgreSQL**.
2.  **File Upload:** The user uploads documents via the **Frontend**. The files are sent to the **Backend**, which saves them to a temporary volume.
3.  **Assessment Kickoff:** The user starts the assessment. The **Frontend** opens a WebSocket to the **Backend**.
4.  **Document Ingestion (RAG & Graph Population):**
    *   The **Backend** iterates through the uploaded files.
    *   Each file is sent to the **MegaParse Service** to extract text.
    *   The extracted text is passed to the **RAG Service**, which chunks the text, generates vector embeddings, and stores them in **Weaviate**.
    *   The text is also passed to an **Entity Extraction Agent**, which identifies entities and relationships and populates the **Neo4j** graph database.
5.  **Agentic Analysis (CrewAI):**
    *   The **Backend** initializes the `Assessment Crew`.
    *   **Real-time Logging:** As agents work, the `AgentLogStreamHandler` captures every action and tool use, streaming structured logs to the **Frontend** via the WebSocket for the "Live Console".
    *   Agents execute their tasks sequentially, using custom tools to query **Weaviate** (for semantic context) and **Neo4j** (for structural dependencies).
    *   All agent actions and tool outputs are streamed back to the **Frontend** in real-time via the WebSocket.
6.  **Report Generation & Persistence:**
    *   The final agent generates a comprehensive report in Markdown format.
    *   The **Backend** saves this raw Markdown to the project record in **PostgreSQL** via the **Project Service**.
    *   The **Backend** then calls the **Reporting Service**, sending it the Markdown content.
    *   The **Reporting Service** generates PDF and DOCX files and stores them in **MinIO**.
    *   The **Reporting Service** calls back to the **Project Service** to save the public URLs of the generated artifacts in the project record.
7.  **Consumption:** The user can view the formatted Markdown report, interact with the RAG chat interface, explore the dependency graph, and download the final PDF/DOCX deliverables from the **Frontend**.

---

## 5. Security & Identity

*   **Authentication:** The `Project Service` acts as the identity provider, issuing JWT (JSON Web Tokens) upon successful login. All subsequent API requests to protected endpoints must include this token.
*   **Authorization:** A role-based access control (RBAC) system is implemented:
    *   **`user`:** Can only view and manage their own associated projects.
    *   **`platform_admin`:** Has full access to all projects, users, and system settings.
*   **API Key Management:** Platform settings, including LLM API keys, are stored in the database (with encryption recommended for production) and managed by platform admins.

---

## 6. Deployment & Operations

*   **Local Environment:** A fully automated setup is provided via `setup-platform.ps1`. It uses Docker Compose to orchestrate all services and includes build optimizations for a rapid development cycle.
*   **Production Environment:** The architecture is designed for deployment to a Kubernetes cluster (e.g., EKS, AKS, GKE). The repository includes sample Kubernetes manifests (`.yaml` files) for each service, which can be deployed via standard tools like `kubectl`, Helm, or ArgoCD.
*   **Configuration:** All environment-specific settings (database URLs, API keys, service endpoints) are managed via environment variables, following the 12-Factor App methodology.

---

## 7. Future Considerations & Scalability

*   **Asynchronous Task Queues:** For even greater scalability, the communication between the `Backend` and `Reporting Service` could be decoupled using a message bus like RabbitMQ or NATS. The backend would publish a `ReportGenerationRequested` event, and the reporting service would consume it.
*   **CI/CD:** The project is structured to easily integrate with CI/CD pipelines (e.g., GitHub Actions) for automated testing, image building, and deployment.
*   **Monitoring & Observability:** For production, integrating tools like Prometheus for metrics, Grafana for dashboards, and an APM solution (e.g., Datadog, OpenTelemetry) would be the next logical step.