"""Tests for project analysis router endpoints."""

import pytest
import json
import uuid
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ..routers.project_analysis_router import router
from ..core.service_client import ServiceClient
from ..core.event_bus import EventBus


@pytest.fixture
def test_client():
    """Create test client for router."""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def mock_service_client():
    """Mock service client."""
    with patch('app.routers.project_analysis_router.get_service_client') as mock:
        client = AsyncMock(spec=ServiceClient)
        mock.return_value = client
        yield client


@pytest.fixture
def mock_event_bus():
    """Mock event bus."""
    with patch('app.routers.project_analysis_router.get_event_bus') as mock:
        bus = AsyncMock(spec=EventBus)
        mock.return_value = bus
        yield bus


@pytest.fixture
def mock_project_service():
    """Mock project service."""
    with patch('app.routers.project_analysis_router.get_project_service') as mock:
        service = Mock()
        mock.return_value = service
        yield service


@pytest.fixture
def mock_storage():
    """Mock storage service."""
    with patch('app.routers.project_analysis_router.get_storage') as mock:
        storage = Mock()
        mock.return_value = storage
        yield storage


@pytest.fixture
def mock_process_ws():
    """Mock WebSocket manager."""
    with patch('app.routers.project_analysis_router.get_process_ws_manager') as mock:
        ws = AsyncMock()
        mock.return_value = ws
        yield ws


@pytest.fixture
def sample_project():
    """Sample project data."""
    return {
        "id": str(uuid.uuid4()),
        "name": "Test Project",
        "description": "Test project for analysis",
        "status": "active"
    }


@pytest.fixture
def sample_analysis_result():
    """Sample analysis result data."""
    return {
        "id": str(uuid.uuid4()),
        "batch_id": str(uuid.uuid4()),
        "result_data": {
            "analysis_type": "infrastructure",
            "components": ["server1", "database1"],
            "findings": ["High availability needed", "Security updates required"]
        },
        "line_number": 1,
        "status": "completed",
        "created_at": "2025-01-01T00:00:00Z"
    }


class TestProjectAnalysisRouter:
    """Test cases for project analysis router endpoints."""

    def test_get_project_graph_success(self, test_client, mock_service_client, sample_project):
        """Test successful project graph retrieval."""
        project_id = sample_project["id"]
        mock_graph_data = {
            "nodes": [
                {"id": "server1", "name": "Server 1", "type": "server"},
                {"id": "db1", "name": "Database 1", "type": "database"}
            ],
            "relationships": [
                {"source": "server1", "target": "db1", "type": "connects_to"}
            ]
        }

        mock_service_client.get_project_graph.return_value = mock_graph_data

        response = test_client.get(f"/api/projects/{project_id}/graph")

        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) == 1

    def test_get_project_graph_with_infrastructure_filter(self, test_client, mock_service_client, sample_project):
        """Test project graph with infrastructure type filtering."""
        project_id = sample_project["id"]
        mock_graph_data = {
            "nodes": [
                {"id": "server1", "name": "Server 1", "type": "server", "labels": ["server"]},
                {"id": "app1", "name": "Application 1", "type": "application", "labels": ["application"]},
                {"id": "user1", "name": "User 1", "type": "user", "labels": ["user"]}
            ],
            "relationships": [
                {"source": "user1", "target": "app1", "type": "uses"},
                {"source": "app1", "target": "server1", "type": "runs_on"}
            ]
        }

        mock_service_client.get_project_graph.return_value = mock_graph_data

        response = test_client.get(f"/api/projects/{project_id}/graph?type=infrastructure")

        assert response.status_code == 200
        data = response.json()
        # Should only return infrastructure-related nodes (server, application)
        assert len(data["nodes"]) == 2
        assert all(node["type"] in ["server", "application"] for node in data["nodes"])

    def test_get_project_graph_service_error(self, test_client, mock_service_client, sample_project):
        """Test project graph retrieval with service error."""
        project_id = sample_project["id"]
        mock_service_client.get_project_graph.side_effect = Exception("Service unavailable")

        response = test_client.get(f"/api/projects/{project_id}/graph")

        assert response.status_code == 500
        assert "Error fetching graph" in response.json()["detail"]

    def test_clear_project_data_success(self, test_client, mock_service_client, mock_event_bus, sample_project):
        """Test successful project data clearing."""
        project_id = sample_project["id"]

        mock_service_client.get_project.return_value = sample_project
        mock_service_client.delete_collection.return_value = {"document_count": 5}
        mock_service_client.delete_project_graph.return_value = {"nodes_deleted": 3}

        response = test_client.post(f"/api/projects/{project_id}/clear-data")

        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == project_id
        assert data["weaviate_embeddings"] == 5
        assert data["neo4j_nodes"] == 3
        mock_event_bus.publish.assert_called_once()

    def test_clear_project_data_project_not_found(self, test_client, mock_service_client, sample_project):
        """Test clearing data for non-existent project."""
        project_id = sample_project["id"]
        mock_service_client.get_project.return_value = None

        response = test_client.post(f"/api/projects/{project_id}/clear-data")

        assert response.status_code == 404
        assert "Project not found" in response.json()["detail"]

    def test_query_project_knowledge_success(self, test_client, mock_service_client, sample_project):
        """Test successful project knowledge querying."""
        project_id = sample_project["id"]
        question = "What servers are in the infrastructure?"

        mock_service_client.get_project.return_value = sample_project
        mock_service_client.vector_search.return_value = {
            "results": [
                {"content": "Server1 is a web server", "metadata": {"filename": "infra.json"}},
                {"content": "Server2 is a database server", "metadata": {"filename": "infra.json"}}
            ]
        }

        response = test_client.post(
            f"/api/projects/{project_id}/query",
            json={"question": question}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == project_id
        assert data["question"] == question
        assert "answer" in data
        assert "sources" in data

    def test_query_project_knowledge_no_results(self, test_client, mock_service_client, sample_project):
        """Test project knowledge query with no results."""
        project_id = sample_project["id"]
        question = "What is the meaning of life?"

        mock_service_client.get_project.return_value = sample_project
        mock_service_client.vector_search.return_value = {"results": []}

        response = test_client.post(
            f"/api/projects/{project_id}/query",
            json={"question": question}
        )

        assert response.status_code == 200
        data = response.json()
        assert "No relevant information found" in data["answer"]

    def test_query_project_knowledge_project_not_found(self, test_client, mock_service_client, sample_project):
        """Test querying knowledge for non-existent project."""
        project_id = sample_project["id"]
        mock_service_client.get_project.return_value = None

        response = test_client.post(
            f"/api/projects/{project_id}/query",
            json={"question": "test question"}
        )

        assert response.status_code == 404
        assert "Project not found" in response.json()["detail"]

    def test_get_project_service_status_success(self, test_client, mock_service_client, sample_project):
        """Test successful service status retrieval."""
        project_id = sample_project["id"]

        mock_service_client.get_project.return_value = sample_project
        mock_service_client.check_all_services_health.return_value = {
            "vector-service": {"status": "healthy"},
            "graph-service": {"status": "healthy"},
            "analytics-service": {"status": "healthy"}
        }
        mock_service_client._make_request.return_value = {
            "status": "ready",
            "document_count": 10
        }
        mock_service_client.get_project_graph.return_value = {
            "nodes": [{"id": "node1"}, {"id": "node2"}]
        }

        response = test_client.get(f"/api/projects/{project_id}/service-status")

        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == project_id
        assert "services" in data
        assert "vector_store" in data
        assert "graph_store" in data
        assert data["vector_store"]["document_count"] == 10
        assert data["graph_store"]["node_count"] == 2

    def test_get_project_stats_success(self, test_client, mock_project_service, mock_storage, sample_project):
        """Test successful project stats retrieval."""
        project_id = sample_project["id"]

        mock_project_service.get_project.return_value = sample_project
        mock_storage.list_files.return_value = ["file1.json", "file2.json"]

        # Mock processing stats file
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', create=True) as mock_file, \
             patch('json.load') as mock_json_load:

            mock_json_load.return_value = {
                "embeddings": 150,
                "graph_nodes": 25,
                "graph_relationships": 40,
                "processing_status": "completed",
                "last_updated": "2025-01-01T00:00:00Z"
            }

            response = test_client.get(f"/api/projects/{project_id}/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == project_id
        assert data["embeddings"] == 150
        assert data["graph_nodes"] == 25
        assert data["files_processed"] == 2
        assert data["processing_status"] == "completed"

    def test_get_project_stats_project_not_found(self, test_client, mock_project_service, sample_project):
        """Test stats retrieval for non-existent project."""
        project_id = sample_project["id"]
        mock_project_service.get_project.return_value = None

        response = test_client.get(f"/api/projects/{project_id}/stats")

        assert response.status_code == 404
        assert "Project not found" in response.json()["detail"]

    def test_process_documents_success(self, test_client, mock_project_service, mock_service_client,
                                     mock_process_ws, sample_project):
        """Test successful document processing."""
        project_id = sample_project["id"]

        mock_project_service.get_project.return_value = sample_project
        mock_service_client.upload_documents.return_value = {
            "uploaded_files": [{"filename": "test.json"}]
        }
        mock_service_client.process_documents.return_value = {
            "status": "processing_started",
            "job_id": str(uuid.uuid4())
        }

        response = test_client.post(f"/api/projects/{project_id}/process-documents")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "job_id" in data
        mock_process_ws.broadcast.assert_called()

    def test_process_documents_project_not_found(self, test_client, mock_project_service, sample_project):
        """Test document processing for non-existent project."""
        project_id = sample_project["id"]
        mock_project_service.get_project.return_value = None

        response = test_client.post(f"/api/projects/{project_id}/process-documents")

        assert response.status_code == 404
        assert "Project not found" in response.json()["detail"]

    def test_generate_document_success(self, test_client, mock_project_service, mock_service_client,
                                     mock_process_ws, sample_project):
        """Test successful document generation."""
        project_id = sample_project["id"]
        request_data = {
            "template_id": "infrastructure_assessment",
            "name": "Test Report",
            "description": "Generated test report"
        }

        mock_project_service.get_project.return_value = sample_project
        mock_service_client.generate_document.return_value = {
            "success": True,
            "markdown_filename": "test_report.md",
            "download_urls": {"markdown": "/download/test_report.md"},
            "content_preview": "Report content preview..."
        }

        response = test_client.post(
            f"/api/projects/{project_id}/generate-document",
            json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["project_id"] == project_id
        assert "markdown_filename" in data
        assert "download_urls" in data
        mock_process_ws.broadcast.assert_called()

    def test_generate_document_project_not_found(self, test_client, mock_project_service, sample_project):
        """Test document generation for non-existent project."""
        project_id = sample_project["id"]
        mock_project_service.get_project.return_value = None

        response = test_client.post(
            f"/api/projects/{project_id}/generate-document",
            json={"name": "Test Report"}
        )

        assert response.status_code == 404
        assert "Project not found" in response.json()["detail"]

    def test_generate_document_generation_failed(self, test_client, mock_project_service, mock_service_client,
                                               mock_process_ws, sample_project):
        """Test document generation failure."""
        project_id = sample_project["id"]

        mock_project_service.get_project.return_value = sample_project
        mock_service_client.generate_document.return_value = {
            "success": False,
            "error": "Template not found"
        }

        response = test_client.post(
            f"/api/projects/{project_id}/generate-document",
            json={"name": "Test Report"}
        )

        assert response.status_code == 500
        assert "Document generation failed" in response.json()["detail"]

    def test_list_project_uploads_success(self, test_client, mock_project_service, mock_storage, sample_project):
        """Test successful project uploads listing."""
        project_id = sample_project["id"]
        mock_files = ["upload1.json", "upload2.json", "upload3.pdf"]

        mock_project_service.get_project.return_value = sample_project
        mock_storage.list_files.return_value = mock_files

        response = test_client.get(f"/api/projects/{project_id}/uploads")

        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == project_id
        assert data["files"] == mock_files
        assert data["count"] == 3

    def test_list_project_uploads_project_not_found(self, test_client, mock_project_service, sample_project):
        """Test uploads listing for non-existent project."""
        project_id = sample_project["id"]
        mock_project_service.get_project.return_value = None

        response = test_client.get(f"/api/projects/{project_id}/uploads")

        assert response.status_code == 404
        assert "Project not found" in response.json()["detail"]


class TestProjectAnalysisRouterErrorHandling:
    """Test error handling in project analysis router."""

    def test_graph_service_unavailable(self, test_client, mock_service_client, sample_project):
        """Test handling of graph service unavailability."""
        project_id = sample_project["id"]
        mock_service_client.get_project_graph.side_effect = Exception("Connection timeout")

        response = test_client.get(f"/api/projects/{project_id}/graph")

        assert response.status_code == 500
        assert "Error fetching graph" in response.json()["detail"]

    def test_vector_search_fallback(self, test_client, mock_service_client, sample_project):
        """Test vector search fallback mechanisms."""
        project_id = sample_project["id"]

        mock_service_client.get_project.return_value = sample_project
        mock_service_client.vector_search.side_effect = Exception("Primary search failed")
        mock_service_client.hybrid_search.return_value = {
            "results": [{"content": "Fallback result", "metadata": {"filename": "test.json"}}]
        }

        response = test_client.post(
            f"/api/projects/{project_id}/query",
            json={"question": "test question"}
        )

        assert response.status_code == 200
        # Should have used fallback search
        mock_service_client.hybrid_search.assert_called_once()

    def test_vector_search_complete_failure(self, test_client, mock_service_client, sample_project):
        """Test complete vector search failure."""
        project_id = sample_project["id"]

        mock_service_client.get_project.return_value = sample_project
        mock_service_client.vector_search.side_effect = Exception("Primary search failed")
        mock_service_client.hybrid_search.side_effect = Exception("Fallback search failed")

        response = test_client.post(
            f"/api/projects/{project_id}/query",
            json={"question": "test question"}
        )

        assert response.status_code == 500
        assert "Vector search service unavailable" in response.json()["detail"]

    def test_websocket_broadcast_failure(self, test_client, mock_project_service, mock_service_client,
                                       mock_process_ws, sample_project):
        """Test handling of WebSocket broadcast failures."""
        project_id = sample_project["id"]

        mock_project_service.get_project.return_value = sample_project
        mock_service_client.upload_documents.return_value = {"uploaded_files": []}
        mock_service_client.process_documents.return_value = {"status": "success"}
        mock_process_ws.broadcast.side_effect = Exception("WebSocket error")

        # Should not fail the main operation due to WebSocket error
        response = test_client.post(f"/api/projects/{project_id}/process-documents")

        assert response.status_code == 200
        # WebSocket error should be logged but not affect response

    def test_file_processing_with_mixed_content_types(self, test_client, mock_project_service, mock_service_client):
        """Test file processing with different content types."""
        project_id = str(uuid.uuid4())

        mock_project_service.get_project.return_value = {"id": project_id}
        mock_service_client.upload_documents.return_value = {
            "uploaded_files": [
                {"filename": "data.json", "content_type": "application/json"},
                {"filename": "config.yaml", "content_type": "application/yaml"},
                {"filename": "readme.md", "content_type": "text/markdown"}
            ]
        }
        mock_service_client.process_documents.return_value = {"status": "success"}

        # Test with JSON body specifying files
        response = test_client.post(
            f"/api/projects/{project_id}/process-documents",
            json={"file_names": ["data.json", "config.yaml"]}
        )

        assert response.status_code == 200
        mock_service_client.process_documents.assert_called_once()
        call_args = mock_service_client.process_documents.call_args
        assert "data.json" in call_args[1]["file_list"]
        assert "config.yaml" in call_args[1]["file_list"]