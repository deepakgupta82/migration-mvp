

### **Nagarro AgentiMigrate MVP: Detailed Implementation Plan for Cline (Windows Edition)**

**MVP Objective:** To generate a local, web-based application on a Windows machine where a user can upload a set of client documents. They will then witness a crew of AI agents, orchestrated by CrewAI, collaborate in real-time to analyze these documents using a sophisticated RAG pipeline (powered by MegaParse and Weaviate) and a graph database (Neo4j) and produce a professional Cloud Readiness Report.

**Local Architecture:** A `docker-compose` setup with five services: `frontend`, `backend`, `megaparse`, `weaviate`, and `neo4j`, all managed via Docker Desktop for Windows.

---

### **Phase 0: Environment & Prerequisite Setup (Windows)**

**Instruction for Cline:** "Create a PowerShell script named `setup.ps1` in the project's root directory. This script must perform the following actions sequentially:"

1.  **Print a start message:** Use `Write-Host` to print "Starting Nagarro AgentiMigrate MVP Environment Setup for Windows..."
2.  **Verify Git Installation:** Check if `git.exe` is in the system's PATH using `Get-Command -ErrorAction SilentlyContinue`. If not, print an error message (e.g., "Error: Git is not installed...") and exit. If it exists, print "Git... OK".
3.  **Verify Docker Installation & Status:** Check if `docker.exe` is available. If not, print an error and exit. Then, run `docker info` and check the exit code. If it's not 0, it means the Docker daemon (via Docker Desktop) isn't running. Print an error instructing the user to start Docker Desktop and exit. If it's running, print "Docker... OK".
4.  **Verify Docker Compose Installation:** Check if `docker-compose.exe` is available. If not, print an error and exit. If it exists, print "Docker Compose... OK".
5.  **Clone MegaParse Repository:** Check if a directory named `MegaParse` exists using `Test-Path`. If it does, print a message that it's being skipped. If not, execute `git clone https://github.com/QuivrHQ/MegaParse.git`. Handle potential cloning errors with an error message and exit.
6.  **Print a completion message:** "Environment setup complete. You can now proceed with the project build."

---

### **Phase 1: Project Scaffolding & Dockerization**

**Instruction for Cline:** "Generate the complete project structure and the Docker configuration files as described below."

1.  **Generate Directory Structure:** Create a root directory named `mvp-agentic-assessment/` containing the following subdirectories: `MegaParse/` (from Phase 0), `backend/app/core/`, `frontend/src/components/`, and `project-service/`.

2.  **Generate `docker-compose.yml`:** Create this file in the root directory. It should define seven services:
    *   **`megaparse` service:**
        *   Build from the `./MegaParse` directory context.
        *   Map host port `5001` to container port `5000`.
        *   Set `restart: always` and `container_name: megaparse_service`.
    *   **`weaviate` service:**
        *   Use the image `semitechnologies/weaviate:1.25.4`.
        *   Map host port `8080` to container port `8080`.
        *   Set `restart: on-failure` and `container_name: weaviate_service`.
    *   **`neo4j` service:**
        *   Use the image `neo4j:5.20.0`.
        *   Map host ports `7474` to `7474` and `7687` to `7687`.
        *   Set `restart: always` and `container_name: neo4j_service`.
    *   **`postgres` service:**
        *   Use the image `postgres:15`.
        *   Map host port `5432` to `5432`.
        *   Set environment variables for the database, user, and password.
        *   Set `container_name: postgres_service`.
    *   **`project-service`:**
        *   Build from the `./project-service` directory context.
        *   Map host port `8002` to container port `8000`.
        *   Set the `DATABASE_URL` environment variable.
        *   Specify that it `depends_on` the `postgres` service.
        *   Set `container_name: project_service`.
    *   **`backend` service:**
        *   Build from the `./backend` directory context.
        *   Map host port `8000` to container port `8000`.
        *   Mount a volume from `./backend/app` to `/app` inside the container.
        *   Pass environment variables for `OPENAI_API_KEY` and `PROJECT_SERVICE_URL`.
        *   Specify that it `depends_on` the `megaparse`, `weaviate`, `neo4j`, and `project-service` services.
        *   Set `restart: on-failure` and `container_name: backend_service`.
    *   **`frontend` service:**
        *   Build from the `./frontend` directory context.
        *   Map host port `3000` to container port `3000`.
        *   Mount a volume from `./frontend/src` to `/app/src` inside the container.
        *   Specify that it `depends_on` the `backend` and `project-service` services.
        *   Set `restart: always` and `container_name: frontend_service`.

---

### **Phase 2: Building the Core Backend Services**

**Instruction for Cline:** "Generate the following files for the `backend` and `project-service` services."

1.  **Generate `project-service/` files:**
    *   **`requirements.txt`:** List `fastapi`, `uvicorn`, `pydantic`, `psycopg2-binary`, and `SQLAlchemy`.
    *   **`Dockerfile`:** Standard Python Dockerfile to run a FastAPI application.
    *   **`main.py`:** A FastAPI application with CRUD endpoints for managing projects (`/projects`). It should use an in-memory dictionary as a database for the MVP, but be structured to easily switch to PostgreSQL.

2.  **Generate `backend/requirements.txt`:** The file should list these Python package dependencies: `fastapi`, `uvicorn`, `python-dotenv`, `crewai`, `crewai_tools`, `langchain`, `langchain-openai`, `langchain-anthropic`, `langchain-google-vertexai`, `requests`, `websockets`, `weaviate-client`, `neo4j`, `sentence-transformers`, `pandas`, `lark`, `psycopg2-binary`, and `SQLAlchemy`.

3.  **Generate `backend/Dockerfile`:**
    *   Use the `python:3.11-slim` base image.
    *   Set the working directory to `/app`.
    *   Copy `requirements.txt` into the container.
    *   Run `pip install` for the requirements.
    *   Copy the local `app` directory into the container's `app` directory.
    *   Set the `CMD` to run `uvicorn` for `main:app` on host `0.0.0.0` and port `8000`.

4.  **Generate `backend/app/core/project_service.py`:**
    *   Create a Python class `ProjectServiceClient` that acts as a client for the `project-service`.
    *   It should have methods for `create_project`, `get_project`, `list_projects`, etc., which make HTTP requests to the `project-service` endpoints.

5.  **Generate `backend/app/core/rag_service.py`:**
    *   Create a Python class named `RAGService`.
    *   Its `__init__` method should accept a `project_id` and initialize a `weaviate.Client`, connecting to the `weaviate` container at host `weaviate` and port `8080`.
    *   Create a method `add_document(self, content: str, doc_id: str)`. This method will add a document to the Weaviate collection.
    *   Create a method `query(self, question: str, n_results: int = 5)`. This method will query the Weaviate collection with the given question and return the concatenated text of the resulting documents.

6.  **Generate `backend/app/core/graph_service.py`:**
    *   Create a Python class named `GraphService`.
    *   Its `__init__` method should initialize a `neo4j.GraphDatabase.driver` connecting to the `neo4j` container at `bolt://neo4j:7687`.
    *   Create a method `execute_query(self, query: str)`. This method will execute a Cypher query against the Neo4j database.

7.  **Generate `backend/app/core/crew.py`:**
    *   Define custom CrewAI tools named `RAGQueryTool` and `GraphQueryTool` that inherit from `BaseTool`. These tools will use instances of the `RAGService` and `GraphService` to execute queries.
    *   Define a function `create_assessment_crew(project_id: str, llm)`. Inside this function:
        *   Instantiate the `RAGService`, `GraphService`, and the custom tools.
        *   Define an `engagement_analyst` agent with the goal of extracting technical and business requirements using the `RAGQueryTool` and `GraphQueryTool`. The task description should guide the agent to first use the Graph tool for structural queries, then the RAG tool for semantic queries.
        *   Define a `principal_cloud_architect` agent and a `lead_planning_manager` agent.
        *   Define tasks for each agent.
        *   Return an initialized `Crew` object.

8.  **Generate `backend/app/main.py`:**
    *   Initialize a FastAPI `app`.
    *   Configure CORS middleware.
    *   Add endpoints for project management (`/projects`, `/projects/{project_id}`) that proxy requests to the `project-service` using the `ProjectServiceClient`.
    *   Create a `POST` endpoint at `/upload/{project_id}` that accepts multiple files.
    *   Create a WebSocket endpoint at `/ws/run_assessment/{project_id}` to run the assessment crew.

---

### **Phase 3: Building the Frontend UI**

**Instruction for Cline:** "Generate the following files for the `frontend` service using React, TypeScript, and the Mantine component library."

1.  **Generate `frontend/package.json`:** Include dependencies for `react`, `react-dom`, `axios`, `@mantine/core`, `@mantine/hooks`, and `react-markdown`.

2.  **Generate `frontend/src/App.tsx`:** Create the main application shell using Mantine's `AppShell`. The UI should be tab-based:
    *   **Dashboard Tab:** Display a table of existing projects fetched from the `/projects` endpoint.
    *   **Create Project Tab:** A form with fields for Project Name, Client Name, and Description. Submitting this form should make a POST request to the `/projects` endpoint.
    *   **File Upload Tab:** This tab will contain the `FileUpload` component.

3.  **Generate `frontend/src/components/FileUpload.tsx`:**
    *   This component will manage the state for file uploads and assessment runs.
    *   It should contain a file dropzone UI element.
    *   It should render a button "Upload & Start Assessment".
    *   When clicked, it will first upload the files and then open a WebSocket connection to run the assessment.
    *   It will render the `LiveConsole` and `ReportDisplay` components.

4.  **Generate `frontend/src/components/LiveConsole.tsx`:**
    *   This component accepts a `logs` prop (string array) and renders them in a terminal-like view.

5.  **Generate `frontend/src/components/ReportDisplay.tsx`:**
    *   This component accepts a `report` prop (string) and renders the Markdown content.

---

### **Phase 4: Final Touches & Demo Preparation (Windows)**

**Instruction for Cline:** "Generate the final utility script for running the MVP on Windows."

1.  **Generate `run-mvp.ps1`:** Create this PowerShell script in the root directory.
    *   It should first run `docker-compose down -v --remove-orphans` to ensure a clean state.
    *   Next, it should define any necessary environment variables. For example: `$env:OPENAI_API_KEY="your_key_here"`. Instruct the user that they must edit this line.
    *   Then, it should run `docker-compose up --build -d` to build and start all services in the background.
    *   The script should check if the last command succeeded. If not, print an error and exit.
    *   Finally, it should print a status message to the console using `Write-Host`, listing the URLs where the frontend, backend, and other services are available (e.g., `Frontend available at: http://localhost:3000`). It should also include instructions on how to view logs (`docker-compose logs -f`) and shut down the services (`docker-compose down`).
