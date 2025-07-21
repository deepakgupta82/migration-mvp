

### **Nagarro AgentiMigrate MVP: Detailed Implementation Plan for Cline (Windows Edition)**

**MVP Objective:** To generate a local, web-based application on a Windows machine where a user can upload a set of client documents. They will then witness a crew of AI agents, orchestrated by CrewAI, collaborate in real-time to analyze these documents using a sophisticated RAG pipeline (powered by MegaParse and ChromaDB) and produce a professional Cloud Readiness Report.

**Local Architecture:** A `docker-compose` setup with four services: `frontend`, `backend`, `megaparse`, and `chromadb`, all managed via Docker Desktop for Windows.

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

1.  **Generate Directory Structure:** Create a root directory named `mvp-agentic-assessment/` containing the following subdirectories: `MegaParse/` (from Phase 0), `backend/app/core/`, and `frontend/src/components/`.

2.  **Generate `docker-compose.yml`:** Create this file in the root directory. It should define four services:
    *   **`megaparse` service:**
        *   Build from the `./MegaParse` directory context.
        *   Map host port `5001` to container port `5000`.
        *   Set `restart: always` and `container_name: megaparse_service`.
    *   **`chromadb` service:**
        *   Use the image `chromadb/chroma:0.5.0`.
        *   Map host port `8001` to container port `8000`.
        *   Set `restart: always` and `container_name: chromadb_service`.
    *   **`backend` service:**
        *   Build from the `./backend` directory context.
        *   Map host port `8000` to container port `8000`.
        *   Mount a volume from `./backend/app` to `/app` inside the container.
        *   Pass environment variables, specifically `OPENAI_API_KEY`, using the `${OPENAI_API_KEY}` syntax.
        *   Specify that it `depends_on` the `megaparse` and `chromadb` services.
        *   Set `restart: on-failure` and `container_name: backend_service`.
    *   **`frontend` service:**
        *   Build from the `./frontend` directory context.
        *   Map host port `3000` to container port `3000`.
        *   Mount a volume from `./frontend/src` to `/app/src` inside the container.
        *   Specify that it `depends_on` the `backend` service.
        *   Set `restart: always` and `container_name: frontend_service`.

---

### **Phase 2: Building the Core Backend Services**

**Instruction for Cline:** "Generate the following files for the `backend` service."

1.  **Generate `backend/requirements.txt`:** The file should list these Python package dependencies: `fastapi`, `uvicorn`, `python-dotenv`, `crewai`, `crewai_tools`, `langchain_openai`, `requests`, `websockets`, `chromadb-client`, `sentence-transformers`, `pandas`, and `lark`.

2.  **Generate `backend/Dockerfile`:**
    *   Use the `python:3.11-slim` base image.
    *   Set the working directory to `/app`.
    *   Copy `requirements.txt` into the container.
    *   Run `pip install` for the requirements.
    *   Copy the local `app` directory into the container's `app` directory.
    *   Set the `CMD` to run `uvicorn` for `main:app` on host `0.0.0.0` and port `8000`.

3.  **Generate `backend/app/core/rag_service.py`:**
    *   Create a Python class named `RAGService`.
    *   Its `__init__` method should accept a `project_id` and initialize a `chromadb.HttpClient`, connecting to the `chromadb` container at host `chromadb` and port `8000`. It should get or create a collection named using the `project_id`.
    *   Create a method `add_file(self, file_path: str)`. This method will send the file at `file_path` to the `megaparse` service endpoint (`http://megaparse:5000/v1/parse`). Upon receiving the parsed content, it will chunk the text and add the chunks and their unique IDs to the ChromaDB collection. It should return a status message string.
    *   Create a method `query(self, question: str, n_results: int = 5)`. This method will query the ChromaDB collection with the given question and return the concatenated text of the resulting documents.

4.  **Generate `backend/app/core/crew.py`:**
    *   Define a custom CrewAI tool named `RAGQueryTool` that inherits from `BaseTool`. This tool will use an instance of the `RAGService` to execute queries.
    *   Define a function `create_assessment_crew(project_id: str)`. Inside this function:
        *   Instantiate the `RAGService` and the `RAGQueryTool`.
        *   Define a `document_analyst` agent with the goal of extracting technical and business requirements using the `RAGQueryTool`.
        *   Define a `cloud_strategist` agent with the goal of creating a migration strategy, also using the `RAGQueryTool`.
        *   Define an `analysis_task` assigned to the `document_analyst`. The task description should guide the agent to query the RAG tool for specific information like servers, business goals, and compliance rules.
        *   Define a `planning_task` assigned to the `cloud_strategist`. The description must instruct the agent to generate a Markdown-formatted "Cloud Readiness Report" with specific sections: Executive Summary, Key Risks, Recommended Approach, and a High-Level Plan. This task must have its `context` set to the output of the `analysis_task`.
        *   Return an initialized `Crew` object with the defined agents and tasks, set to `Process.sequential`.

5.  **Generate `backend/app/main.py`:**
    *   Initialize a FastAPI `app`.
    *   Configure CORS middleware to allow requests from `http://localhost:3000`.
    *   Create a `POST` endpoint at `/upload/{project_id}` that accepts multiple files and saves them to a temporary directory based on the `project_id`.
    *   Create a WebSocket endpoint at `/ws/run_assessment/{project_id}`.
        *   Upon connection, it should redirect `sys.stdout` to a handler that sends messages over the WebSocket to provide a live log stream.
        *   It should then initialize the `RAGService` by adding all uploaded files for the project.
        *   Next, it will create and `kickoff()` the assessment crew.
        *   The final result from the crew (the Markdown report) should be sent over the WebSocket, prefixed and suffixed with special markers (e.g., `FINAL_REPORT_MARKDOWN_START`/`END`) so the frontend can identify it.
        *   Finally, it must restore `sys.stdout` and close the connection.

---

### **Phase 3: Building the Frontend UI**

**Instruction for Cline:** "Generate the following files for the `frontend` service using React, TypeScript, and the Mantine component library."

1.  **Generate `frontend/package.json`:** Include dependencies for `react`, `react-dom`, `axios`, `@mantine/core`, `@mantine/hooks`, and `react-markdown`.

2.  **Generate `frontend/src/App.tsx`:** Create the main application shell using Mantine's `AppShell` component, including a header with the title "Nagarro AgentiMigrate MVP". The main content area should render the `FileUpload` component.

3.  **Generate `frontend/src/components/FileUpload.tsx`:**
    *   This component will manage the application's state: `files`, `projectId`, `isUploading`, `isAssessing`, `logs` (as a string array), and `finalReport`.
    *   It should contain a file dropzone UI element. When files are added, it should generate a UUID for the `projectId`.
    *   It should render a single button "Upload & Start Assessment".
    *   When clicked, the component will first make an HTTP POST request to the `/upload/{projectId}` endpoint with the files.
    *   Upon successful upload, it will establish a WebSocket connection to `/ws/run_assessment/{projectId}`.
    *   It will listen for messages on the WebSocket, appending general log messages to the `logs` state array and identifying the final report via the special markers to set the `finalReport` state.
    *   It will conditionally render the `LiveConsole` and `ReportDisplay` components based on the current state.

4.  **Generate `frontend/src/components/LiveConsole.tsx`:**
    *   This component accepts a `logs` prop (string array).
    *   It should render the logs within a styled, scrollable `<pre>` tag, giving it the appearance of a terminal.

5.  **Generate `frontend/src/components/ReportDisplay.tsx`:**
    *   This component accepts a `report` prop (string).
    *   It will use the `react-markdown` library to render the report string as formatted HTML.
    *   It should only be visible when the `report` prop is not empty.

---

### **Phase 4: Final Touches & Demo Preparation (Windows)**

**Instruction for Cline:** "Generate the final utility script for running the MVP on Windows."

1.  **Generate `run-mvp.ps1`:** Create this PowerShell script in the root directory.
    *   It should first run `docker-compose down -v --remove-orphans` to ensure a clean state.
    *   Next, it should define any necessary environment variables. For example: `$env:OPENAI_API_KEY="your_key_here"`. Instruct the user that they must edit this line.
    *   Then, it should run `docker-compose up --build -d` to build and start all services in the background.
    *   The script should check if the last command succeeded. If not, print an error and exit.
    *   Finally, it should print a status message to the console using `Write-Host`, listing the URLs where the frontend, backend, and other services are available (e.g., `Frontend available at: http://localhost:3000`). It should also include instructions on how to view logs (`docker-compose logs -f`) and shut down the services (`docker-compose down`).