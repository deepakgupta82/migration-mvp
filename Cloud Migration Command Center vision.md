# Nagarro's Ascent: Cloud Migration Command Center - Refactoring Master Plan

## 1. Executive Vision: From Report Generator to AI Co-pilot

This document outlines the strategic engineering plan to evolve the Nagarro's Ascent platform from a document assessment tool into a comprehensive, AI-powered **Cloud Migration Command Center**.

The core architecture will be a **Knowledge-First, Microservice-Oriented** system. The platform will leverage a hybrid agentic model, using **CrewAI** for automated, predictable deliverable generation and **AutoGen** for dynamic, interactive co-pilot sessions with Human-in-the-Loop (HITL) capabilities. The system will be supercharged by ingesting ground-truth data from native cloud tools like **AWS Migration Evaluator** and the **AWS MCP Documentation Server**. Eventually, this will be expanded to Azure also.

This plan details the specific, sequential engineering tasks required to build this vision. Ensure that the development of this plan is aligned to other aspects current platform like logging, stats, websocket streaming and exposing configurable parameters to environment variables section of the settings in ui.

---

## **Phase 1: Supercharge the Knowledge Core**

*   **Objective:** To dramatically improve the quality and accuracy of the AI's knowledge by moving beyond static document parsing to ingest high-fidelity, structured data from authoritative sources.
*   **Key Files to Modify:**
    *   `services/document-service/app/core/document_processor.py`
    *   New service: `services/data-importer-service/`
    *   New service: `services/aws-data-service/`
    *   `services/graph-service/app/core/graph_processor.py`

*   **Step-by-Step Action Plan:**

    1.  **Action: Upgrade Document Intake Engine.**
        *   **Source File(s):** `services/document-service/requirements.txt`, `services/document-service/app/core/document_processor.py`
        *   **Technical Details:**
            *   Add `unstructured[all]` to the `document-service`'s `requirements.txt`.
            *   In `document_processor.py`, replace the `markitdown` and PDF fallback logic in the `_perform_conversion_sync` method with a call to the `unstructured` library. The goal is to use `unstructured.partition(filename=file_path)` to get a list of structured `Element` objects.
            *   Iterate through these elements to build a clean Markdown output, preserving tables, headers, and lists. This will become the new `content`.

    2.  **Action: Create the Data Importer Microservice.**
        *   **Source File(s):** New service.
        *   **Technical Details:**
            *   Create a new folder: `services/data-importer-service`.
            *   Set up a basic FastAPI application inside it (similar to your other services).
            *   The primary function of this service will be to parse CSV/JSON exports from **AWS Migration Evaluator** and **Azure Migrate**.
            *   Create an endpoint like `POST /importers/aws/migration-evaluator`. This endpoint will receive the report file, parse its rows, and make a series of HTTP calls to the `graph-service` to create/update nodes with the discovered data (server specs, performance metrics, etc.).

    3.  **Action: Deploy the AWS MCP Documentation Server.**
        *   **Source File(s):** New service, based on the `awslabs/mcp` repository.
        *   **Technical Details:**
            *   Create a new folder: `services/aws-data-service`.
            *   Copy the `aws-documentation-mcp-server` code into this folder and create a `Dockerfile` for it.
            *   This service will run as part of your `docker-compose` stack.
            *   Create a new background task (either a separate script or an n8n workflow) that runs daily. This task will call the `aws-data-service` API to get the latest pricing/spec data, then iterate through the nodes in your Neo4j graph and update their properties (e.g., `current_price_per_hour`, `graviton_upgrade_equivalent`).

*   **Dependency Changes:**
    *   **Add:** `unstructured[all]` to `services/document-service/requirements.txt`.
*   **Verification Steps:**
    *   Confirm that processing a complex PDF in the UI results in a clean, well-structured Markdown file in MinIO.
    *   Confirm that uploading an AWS Migration Evaluator CSV via the new importer service results in new, detailed server nodes appearing in the Neo4j graph.
    *   Confirm that nodes in the graph are being enriched with pricing data from the `aws-data-service`.

---

## **Phase 2: Implement the Interactive Architect's Co-pilot**

*   **Objective:** To introduce the **AutoGen** framework and create the first interactive, collaborative AI team for architects, focusing on the Strategy & Design phases.
*   **Key Files to Modify:**
    *   `services/ai-agent-service/requirements.txt`
    *   `services/ai-agent-service/app/core/agent_processor.py` (or a new `autogen_processor.py`)
    *   `services/ai-agent-service/app/routers/agents.py`
    *   `frontend/src/views/ProjectDetailView.tsx`
    *   New frontend component: `frontend/src/components/project-detail/CoPilotChat.tsx`

*   **Step-by-Step Action Plan:**

    1.  **Action: Augment `ai-agent-service` with AutoGen.**
        *   **Source File(s):** `services/ai-agent-service/requirements.txt`
        *   **Technical Details:** Add `pyautogen` to the requirements file and install it in the service's virtual environment.

    2.  **Action: Implement the "Strategy & Design" AutoGen Team.**
        *   **Source File(s):** A new file, e.g., `services/ai-agent-service/app/core/autogen_teams.py`.
        *   **Technical Details:** Define the AutoGen agents as planned: `UserProxyAgent`, `CloudStrategistAgent`, `LeadArchitectAgent`, `FinOpsAgent`, and `SecurityAgent`. Each agent will be an `AssistantAgent` with a specialized system prompt. Register your foundational "Tools" (like `KnowledgeBaseSearchTool`) with these agents so they can execute them.

    3.  **Action: Create the Co-pilot API Endpoint.**
        *   **Source File(s):** `services/ai-agent-service/app/routers/agents.py`
        *   **Technical Details:** Create a new WebSocket endpoint: `WEBSOCKET /api/agents/projects/{id}/copilot-chat`. When a connection is made, this endpoint will initialize the "Strategy & Design" team from the previous step. It will then manage the multi-agent conversation, streaming the messages from all agents (including prompts for the human) back to the client.

    4.  **Action: Build the Co-pilot UI.**
        *   **Source File(s):** New component `frontend/src/components/project-detail/CoPilotChat.tsx`.
        *   **Technical Details:** Build a rich chat interface. This component will establish a WebSocket connection to the new endpoint. It will display the streaming conversation from all agents and provide a text input for the human architect to send messages back to the `UserProxyAgent`.

*   **Dependency Changes:**
    *   **Add:** `pyautogen` to `services/ai-agent-service/requirements.txt`.
*   **Verification Steps:**
    *   Verify that opening the new Co-pilot chat in the UI successfully establishes a WebSocket connection.
    *   Confirm that sending a message from the UI triggers a multi-agent conversation in the `ai-agent-service` logs.
    *   Confirm that agents can successfully use tools like `KnowledgeBaseSearchTool`.
    *   Verify that prompts for human input are correctly displayed in the UI.

---

## **Phase 3: Automate Migration & Operations**

*   **Objective:** To make the AI's output directly executable by generating Infrastructure as Code and detailed migration plans.
*   **Key Files to Modify:**
    *   `services/ai-agent-service/app/core/autogen_teams.py`
    *   `services/ai-agent-service/app/core/tools.py` (or similar for tools)
    *   `frontend/src/views/ProjectDetailView.tsx`

*   **Step-by-Step Action Plan:**

    1.  **Action: Implement the "Implementation" Agent Team.**
        *   **Source File(s):** `services/ai-agent-service/app/core/autogen_teams.py`
        *   **Technical Details:** Define a new AutoGen team or CrewAI crew that includes the `IaCExpertAgent` and `MigrationPlannerAgent`.

    2.  **Action: Create the IaC Generation Tool.**
        *   **Source File(s):** `services/ai-agent-service/app/core/tools.py`
        *   **Technical Details:** Implement the `IaCGeneratorTool`. This tool will take a structured JSON description of a cloud architecture as input. It will then make an HTTP call to the `llm-service` with a highly specific, few-shot prompt that instructs the LLM to convert the JSON into a valid Terraform `.tf` file. It returns the code as a string.

    3.  **Action: Implement the "Optimization" Crew.**
        *   **Source File(s):** `services/ai-agent-service/app/core/autogen_teams.py`
        *   **Technical Details:** Create a crew that is specifically designed to work with the data from the MCP report. Its primary agent, the `FinOpsAgent`, will use the `NativeToolDataQueryTool` to find high-priority optimization targets in the Neo4j graph.

*   **Dependency Changes:**
    *   None, assuming `httpx` is already in `ai-agent-service`.
*   **Verification Steps:**
    *   Verify that the "Implementation" team can be triggered and that it produces a valid Terraform file as output.
    *   Confirm that the "Optimization" crew correctly identifies cost-saving opportunities from a project where MCP data has been imported.

---

## **Phase 4: Evolve the User Interface for the Full Lifecycle**

*   **Objective:** To create a seamless user experience that guides architects through the entire E2E cloud services lifecycle.
*   **Key Files to Modify:**
    *   `frontend/src/views/ProjectDetailView.tsx`
    *   New frontend components for the phase-specific workspaces.

*   **Step-by-Step Action Plan:**

    1.  **Action: Implement the "Phase Selector" UI.**
        *   **Source File(s):** `frontend/src/views/ProjectDetailView.tsx`
        *   **Technical Details:** Create a new React component that displays the six phases from your diagram. This component will manage the state of the currently selected phase.

    2.  **Action: Design Contextual Workspaces.**
        *   **Source File(s):** `frontend/src/views/ProjectDetailView.tsx`
        *   **Technical Details:** Refactor the main content area of the project detail view. It should now conditionally render different sets of components based on the selected phase.
            *   **Phases 1-2:** Show the new `CoPilotChat.tsx` component.
            *   **Phases 3-4:** Show a new component that contains buttons like "Generate Terraform Plan" which trigger the "Implementation" team. This component will also have a code viewer to display the generated IaC.
            *   **Phases 5-6:** Show a new component that prompts the user to upload an MCP report and then displays a dashboard of the key findings (e.g., top 5 cost savings).

*   **Dependency Changes:**
    *   None, this is a frontend-only change.
*   **Verification Steps:**
    *   Clicking through the Phase Selector correctly changes the displayed components in the UI.
    *   The appropriate agent teams are called when buttons in the contextual workspaces are clicked.