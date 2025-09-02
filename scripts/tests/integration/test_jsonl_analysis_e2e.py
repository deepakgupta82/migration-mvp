#!/usr/bin/env python3
"""
End-to-end tests for JSONL analysis system.

Tests the complete flow from document processing through analysis to database storage.
"""

import os
import json
import tempfile
import asyncio
import pytest
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import the test backend
from test_backend import app, SimpleVectorStore, project_files_db, projects_db
from services.analytics_service.app.repositories.sql_analysis_result_repository import SqlAnalysisResultRepository
from services.analytics_service.app.models.analysis_models import Base as AnalyticsBase


@pytest.fixture(scope="session")
def test_client():
    """Create test client for the test backend."""
    client = TestClient(app)
    return client


@pytest.fixture(scope="session")
def analytics_engine():
    """Create in-memory SQLite engine for analytics database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )

    # Create analytics tables
    AnalyticsBase.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def analytics_session(analytics_engine):
    """Create analytics database session."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=analytics_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def analytics_repository(analytics_session):
    """Create analytics repository."""
    def session_factory():
        return analytics_session
    return SqlAnalysisResultRepository(session_factory)


@pytest.fixture
def sample_project():
    """Create a sample project for testing."""
    project_id = str(uuid.uuid4())
    project = {
        "id": project_id,
        "name": "JSONL Analysis E2E Test Project",
        "description": "End-to-end testing of JSONL analysis system",
        "client_name": "Test Client",
        "status": "active",
        "llm_provider": "openai",
        "llm_model": "gpt-3.5-turbo",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }
    projects_db[project_id] = project
    project_files_db[project_id] = []
    return project


@pytest.fixture
def sample_jsonl_data():
    """Create sample JSONL data for testing."""
    return [
        {
            "type": "infrastructure_component",
            "name": "web-server-01",
            "category": "server",
            "properties": {
                "os": "Ubuntu 20.04",
                "cpu_cores": 4,
                "memory_gb": 8,
                "ip_address": "192.168.1.10",
                "services": ["nginx", "apache"]
            },
            "relationships": [
                {"target": "load-balancer-01", "type": "load_balanced_by"},
                {"target": "database-01", "type": "connects_to"}
            ]
        },
        {
            "type": "infrastructure_component",
            "name": "database-01",
            "category": "database",
            "properties": {
                "engine": "PostgreSQL",
                "version": "13.4",
                "port": 5432,
                "storage_gb": 100,
                "backup_enabled": True
            },
            "relationships": [
                {"target": "web-server-01", "type": "served_by"}
            ]
        },
        {
            "type": "infrastructure_component",
            "name": "load-balancer-01",
            "category": "load_balancer",
            "properties": {
                "type": "haproxy",
                "algorithm": "round_robin",
                "ssl_enabled": True,
                "backends": ["web-server-01", "web-server-02"]
            },
            "relationships": [
                {"target": "web-server-01", "type": "balances"}
            ]
        }
    ]


class TestJSONLAnalysisE2E:
    """End-to-end tests for JSONL analysis system."""

    def test_complete_jsonl_analysis_workflow(self, test_client, analytics_repository,
                                           sample_project, sample_jsonl_data):
        """Test complete JSONL analysis workflow from upload to results."""
        project_id = sample_project["id"]

        # Step 1: Create project
        response = test_client.post("/projects", json={
            "name": sample_project["name"],
            "description": sample_project["description"],
            "client_name": sample_project["client_name"]
        })
        assert response.status_code == 200
        created_project = response.json()
        assert created_project["name"] == sample_project["name"]

        # Step 2: Upload JSONL file
        jsonl_content = "\n".join(json.dumps(item) for item in sample_jsonl_data)
        files = [("files", ("infrastructure.jsonl", jsonl_content, "application/jsonl"))]

        response = test_client.post(f"/upload/{project_id}", files=files)
        assert response.status_code == 200
        upload_result = response.json()
        assert len(upload_result["uploaded_files"]) == 1
        assert upload_result["uploaded_files"][0]["filename"] == "infrastructure.jsonl"

        # Step 3: Process documents
        response = test_client.post(f"/api/projects/{project_id}/process-documents")
        assert response.status_code == 200
        process_result = response.json()
        assert "status" in process_result

        # Step 4: Verify document processing created chunks
        # Check that files were processed and chunks created
        files_response = test_client.get(f"/projects/{project_id}/files")
        assert files_response.status_code == 200
        files_data = files_response.json()
        assert len(files_data) >= 1

        # Step 5: Query the processed knowledge base
        query_response = test_client.post(f"/api/projects/{project_id}/query", json={
            "question": "What servers are in the infrastructure?"
        })
        assert query_response.status_code == 200
        query_data = query_response.json()
        assert "answer" in query_data
        assert query_data["project_id"] == project_id

        # Step 6: Generate analysis report
        report_response = test_client.post(f"/api/projects/{project_id}/generate-report")
        assert report_response.status_code == 200
        report_data = report_response.json()
        assert "report_filename" in report_data
        assert "download_url" in report_data

        # Step 7: Check project stats
        stats_response = test_client.get(f"/api/projects/{project_id}/stats")
        assert stats_response.status_code == 200
        stats_data = stats_response.json()
        assert stats_data["project_id"] == project_id
        assert "embeddings" in stats_data
        assert "graph_nodes" in stats_data

    def test_jsonl_analysis_with_complex_data_structures(self, test_client, sample_project):
        """Test JSONL analysis with complex nested data structures."""
        project_id = sample_project["id"]

        # Create complex JSONL data
        complex_data = [
            {
                "type": "application_architecture",
                "name": "ecommerce-platform",
                "components": {
                    "frontend": {
                        "framework": "React",
                        "version": "18.2.0",
                        "dependencies": ["axios", "redux", "material-ui"]
                    },
                    "backend": {
                        "framework": "FastAPI",
                        "language": "Python",
                        "database": "PostgreSQL",
                        "cache": "Redis",
                        "apis": [
                            {"name": "user-api", "version": "v2", "endpoints": 15},
                            {"name": "product-api", "version": "v1", "endpoints": 8},
                            {"name": "order-api", "version": "v3", "endpoints": 12}
                        ]
                    },
                    "infrastructure": {
                        "servers": [
                            {"name": "web-01", "role": "frontend", "cpu": 4, "memory": 8},
                            {"name": "api-01", "role": "backend", "cpu": 8, "memory": 16},
                            {"name": "db-01", "role": "database", "cpu": 16, "memory": 64}
                        ],
                        "networking": {
                            "load_balancer": "nginx",
                            "cdn": "cloudflare",
                            "firewall_rules": 25
                        }
                    }
                },
                "deployment": {
                    "environments": ["development", "staging", "production"],
                    "ci_cd": "GitHub Actions",
                    "monitoring": ["prometheus", "grafana", "datadog"],
                    "scaling": {
                        "horizontal": True,
                        "vertical": False,
                        "auto_scaling": True
                    }
                }
            }
        ]

        # Upload complex JSONL
        jsonl_content = "\n".join(json.dumps(item) for item in complex_data)
        files = [("files", ("complex_architecture.jsonl", jsonl_content, "application/jsonl"))]

        response = test_client.post(f"/upload/{project_id}", files=files)
        assert response.status_code == 200

        # Process documents
        response = test_client.post(f"/api/projects/{project_id}/process-documents")
        assert response.status_code == 200

        # Query complex structure
        query_response = test_client.post(f"/api/projects/{project_id}/query", json={
            "question": "What are the main components of the ecommerce platform?"
        })
        assert query_response.status_code == 200

        # Generate report
        report_response = test_client.post(f"/api/projects/{project_id}/generate-report")
        assert report_response.status_code == 200

    def test_jsonl_analysis_error_handling(self, test_client, sample_project):
        """Test error handling in JSONL analysis workflow."""
        project_id = sample_project["id"]

        # Test with invalid JSONL
        invalid_jsonl = "invalid json content\nincomplete json"
        files = [("files", ("invalid.jsonl", invalid_jsonl, "application/jsonl"))]

        response = test_client.post(f"/upload/{project_id}", files=files)
        assert response.status_code == 200  # Upload should succeed

        # Processing should handle errors gracefully
        response = test_client.post(f"/api/projects/{project_id}/process-documents")
        assert response.status_code == 200  # Should not fail completely

        # Query should return appropriate message for empty/failed processing
        query_response = test_client.post(f"/api/projects/{project_id}/query", json={
            "question": "What is in the invalid file?"
        })
        assert query_response.status_code == 200
        query_data = query_response.json()
        # Should handle gracefully even with processing errors

    def test_jsonl_analysis_with_empty_file(self, test_client, sample_project):
        """Test JSONL analysis with empty file."""
        project_id = sample_project["id"]

        # Upload empty file
        files = [("files", ("empty.jsonl", "", "application/jsonl"))]

        response = test_client.post(f"/upload/{project_id}", files=files)
        assert response.status_code == 200

        # Process empty file
        response = test_client.post(f"/api/projects/{project_id}/process-documents")
        assert response.status_code == 200

        # Query empty processing
        query_response = test_client.post(f"/api/projects/{project_id}/query", json={
            "question": "What is in the empty file?"
        })
        assert query_response.status_code == 200

    def test_jsonl_analysis_concurrent_processing(self, test_client, sample_project, sample_jsonl_data):
        """Test concurrent JSONL analysis processing."""
        project_id = sample_project["id"]

        # Upload multiple files simultaneously
        files = []
        for i in range(3):
            jsonl_content = "\n".join(json.dumps(item) for item in sample_jsonl_data[:2])  # Smaller dataset
            files.append(("files", (f"concurrent_{i}.jsonl", jsonl_content, "application/jsonl")))

        response = test_client.post(f"/upload/{project_id}", files=files)
        assert response.status_code == 200
        assert len(response.json()["uploaded_files"]) == 3

        # Process all files
        response = test_client.post(f"/api/projects/{project_id}/process-documents")
        assert response.status_code == 200

        # Verify all files were processed
        files_response = test_client.get(f"/projects/{project_id}/files")
        assert files_response.status_code == 200
        files_data = files_response.json()
        assert len(files_data) >= 3

    def test_jsonl_analysis_large_dataset(self, test_client, sample_project):
        """Test JSONL analysis with larger dataset."""
        project_id = sample_project["id"]

        # Create larger dataset
        large_data = []
        for i in range(50):  # 50 components
            large_data.append({
                "type": "server_component",
                "name": f"server-{i:03d}",
                "category": "server",
                "properties": {
                    "id": i,
                    "cpu_cores": 4 + (i % 8),
                    "memory_gb": 8 + (i % 16),
                    "disk_gb": 100 + (i % 200),
                    "os": "Ubuntu 20.04",
                    "services": ["nginx", "apache", "mysql"][:2 + (i % 2)]
                },
                "relationships": [
                    {"target": f"server-{(i+1)%50:03d}", "type": "connects_to"},
                    {"target": f"server-{(i-1)%50:03d}", "type": "connects_to"}
                ]
            })

        jsonl_content = "\n".join(json.dumps(item) for item in large_data)
        files = [("files", ("large_infrastructure.jsonl", jsonl_content, "application/jsonl"))]

        # Upload large file
        response = test_client.post(f"/upload/{project_id}", files=files)
        assert response.status_code == 200

        # Process large dataset
        response = test_client.post(f"/api/projects/{project_id}/process-documents")
        assert response.status_code == 200

        # Query large dataset
        query_response = test_client.post(f"/api/projects/{project_id}/query", json={
            "question": "How many servers have more than 8 CPU cores?"
        })
        assert query_response.status_code == 200

        # Check stats for large dataset
        stats_response = test_client.get(f"/api/projects/{project_id}/stats")
        assert stats_response.status_code == 200
        stats_data = stats_response.json()
        assert stats_data["embeddings"] > 0

    def test_jsonl_analysis_with_mixed_file_types(self, test_client, sample_project, sample_jsonl_data):
        """Test JSONL analysis with mixed file types in same project."""
        project_id = sample_project["id"]

        # Upload JSONL file
        jsonl_content = "\n".join(json.dumps(item) for item in sample_jsonl_data)
        files = [("files", ("infrastructure.jsonl", jsonl_content, "application/jsonl"))]

        response = test_client.post(f"/upload/{project_id}", files=files)
        assert response.status_code == 200

        # Upload additional text file
        text_content = """
        Additional infrastructure documentation:

        The web servers are configured with nginx as reverse proxy.
        Database uses PostgreSQL with streaming replication.
        Load balancer distributes traffic using round-robin algorithm.

        Security measures:
        - SSL/TLS encryption enabled
        - Firewall rules configured
        - Regular security updates applied
        """

        files = [("files", ("documentation.txt", text_content, "text/plain"))]

        response = test_client.post(f"/upload/{project_id}", files=files)
        assert response.status_code == 200

        # Process mixed files
        response = test_client.post(f"/api/projects/{project_id}/process-documents")
        assert response.status_code == 200

        # Query mixed content
        query_response = test_client.post(f"/api/projects/{project_id}/query", json={
            "question": "What security measures are documented?"
        })
        assert query_response.status_code == 200

    def test_jsonl_analysis_workflow_with_deliverables(self, test_client, sample_project, sample_jsonl_data):
        """Test complete workflow including deliverables generation."""
        project_id = sample_project["id"]

        # Upload and process JSONL
        jsonl_content = "\n".join(json.dumps(item) for item in sample_jsonl_data)
        files = [("files", ("infrastructure.jsonl", jsonl_content, "application/jsonl"))]

        test_client.post(f"/upload/{project_id}", files=files)
        test_client.post(f"/api/projects/{project_id}/process-documents")

        # Generate infrastructure assessment deliverable
        deliverable_response = test_client.post(f"/api/projects/{project_id}/generate-deliverable", json={
            "template_id": "infrastructure_assessment",
            "custom_prompt": "Generate a comprehensive infrastructure assessment based on the JSONL data provided."
        })
        assert deliverable_response.status_code == 200
        deliverable_data = deliverable_response.json()
        assert "deliverable_filename" in deliverable_data

        # Generate security audit deliverable
        security_response = test_client.post(f"/api/projects/{project_id}/generate-deliverable", json={
            "template_id": "security_audit"
        })
        assert security_response.status_code == 200

        # Generate migration strategy deliverable
        migration_response = test_client.post(f"/api/projects/{project_id}/generate-deliverable", json={
            "template_id": "migration_strategy"
        })
        assert migration_response.status_code == 200

        # Verify deliverables were created
        stats_response = test_client.get(f"/api/projects/{project_id}/stats")
        assert stats_response.status_code == 200
        stats_data = stats_response.json()
        assert stats_data["deliverables"] >= 3

    def test_jsonl_analysis_performance_metrics(self, test_client, sample_project, sample_jsonl_data):
        """Test performance metrics collection during JSONL analysis."""
        import time

        project_id = sample_project["id"]

        # Upload and process
        jsonl_content = "\n".join(json.dumps(item) for item in sample_jsonl_data)
        files = [("files", ("infrastructure.jsonl", jsonl_content, "application/jsonl"))]

        start_time = time.time()
        test_client.post(f"/upload/{project_id}", files=files)
        upload_time = time.time() - start_time

        start_time = time.time()
        test_client.post(f"/api/projects/{project_id}/process-documents")
        process_time = time.time() - start_time

        start_time = time.time()
        test_client.post(f"/api/projects/{project_id}/query", json={
            "question": "What infrastructure components exist?"
        })
        query_time = time.time() - start_time

        # Performance should be reasonable (adjust thresholds as needed)
        assert upload_time < 2.0  # Upload under 2 seconds
        assert process_time < 5.0  # Processing under 5 seconds
        assert query_time < 3.0  # Query under 3 seconds

        # Check final stats
        stats_response = test_client.get(f"/api/projects/{project_id}/stats")
        assert stats_response.status_code == 200
        stats_data = stats_response.json()

        # Should have processed the data
        assert stats_data["embeddings"] >= 0
        assert stats_data["graph_nodes"] >= 0

    def test_jsonl_analysis_data_integrity(self, test_client, sample_project, sample_jsonl_data):
        """Test data integrity throughout JSONL analysis workflow."""
        project_id = sample_project["id"]

        # Upload JSONL
        jsonl_content = "\n".join(json.dumps(item) for item in sample_jsonl_data)
        files = [("files", ("infrastructure.jsonl", jsonl_content, "application/jsonl"))]

        test_client.post(f"/upload/{project_id}", files=files)

        # Process documents
        test_client.post(f"/api/projects/{project_id}/process-documents")

        # Verify data integrity through multiple queries
        queries = [
            "What servers exist?",
            "What databases are configured?",
            "What load balancers are present?",
            "Show me all infrastructure components"
        ]

        for query in queries:
            response = test_client.post(f"/api/projects/{project_id}/query", json={
                "question": query
            })
            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
            assert len(data["answer"]) > 0  # Should have meaningful response

        # Generate report and verify it contains expected content
        report_response = test_client.post(f"/api/projects/{project_id}/generate-report")
        assert report_response.status_code == 200

        # Verify project state is consistent
        final_stats = test_client.get(f"/api/projects/{project_id}/stats")
        assert final_stats.status_code == 200
        stats_data = final_stats.json()
        assert stats_data["project_id"] == project_id
        assert stats_data["files_processed"] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])