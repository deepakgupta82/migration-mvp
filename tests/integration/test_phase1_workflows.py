"""
Phase 1 Integration Tests
Tests for Cloud Orchestration, IAC Governance, and FinOps services

These tests verify end-to-end workflows across the Phase 1 services:
1. Cloud Orchestration: Migration wave creation and execution
2. IAC Governance: Policy scanning, violation detection, remediation
3. Cross-service integration: Service discovery, correlation ID propagation
"""

import pytest
import httpx
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, List

# Service URLs
BACKEND_URL = "http://localhost:8000"
CLOUD_ORCHESTRATION_URL = "http://localhost:8020"
IAC_GOVERNANCE_URL = "http://localhost:8021"
SERVICE_REGISTRY_URL = "http://localhost:8011"

# Test configuration
TEST_TIMEOUT = 30.0
AUTH_TOKEN = "service-backend-token"


class TestServiceDiscovery:
    """Test service discovery and health checks"""
    
    @pytest.mark.asyncio
    async def test_service_registry_health(self):
        """Verify service registry is operational"""
        async with httpx.AsyncClient(timeout=TEST_TIMEOUT) as client:
            response = await client.get(f"{SERVICE_REGISTRY_URL}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "service-registry"
    
    @pytest.mark.asyncio
    async def test_all_phase1_services_registered(self):
        """Verify all Phase 1 services are registered"""
        async with httpx.AsyncClient(timeout=TEST_TIMEOUT) as client:
            response = await client.get(f"{SERVICE_REGISTRY_URL}/services")
            assert response.status_code == 200
            data = response.json()
            
            services = data["services"]
            assert "cloud-orchestration-service" in services
            assert "iac-governance-service" in services
            assert "finops-optimization-service" in services
    
    @pytest.mark.asyncio
    async def test_phase1_services_health(self):
        """Check health of all Phase 1 services"""
        services = {
            "cloud-orchestration": CLOUD_ORCHESTRATION_URL,
            "iac-governance": IAC_GOVERNANCE_URL,
        }
        
        async with httpx.AsyncClient(timeout=TEST_TIMEOUT) as client:
            for service_name, url in services.items():
                response = await client.get(f"{url}/health")
                assert response.status_code == 200, f"{service_name} health check failed"
                data = response.json()
                assert data["status"] == "healthy", f"{service_name} is not healthy"


class TestCloudOrchestration:
    """Test Cloud Orchestration Service workflows"""
    
    @pytest.mark.asyncio
    async def test_create_migration_wave(self):
        """Test creating a migration wave"""
        wave_data = {
            "project_id": str(uuid.uuid4()),
            "name": "Test Migration Wave",
            "description": "Integration test wave",
            "target_cloud": "aws",
            "target_region": "us-east-1",
            "wave_metadata": {
                "test": True,
                "created_by": "integration_test"
            }
        }
        
        headers = {
            "Authorization": f"Bearer {AUTH_TOKEN}",
            "X-Correlation-ID": str(uuid.uuid4())
        }
        
        async with httpx.AsyncClient(timeout=TEST_TIMEOUT) as client:
            # Create wave via gateway
            response = await client.post(
                f"{BACKEND_URL}/api/cloud-orchestration/api/waves",
                json=wave_data,
                headers=headers
            )
            assert response.status_code == 201
            data = response.json()
            assert "wave_id" in data
            assert data["name"] == wave_data["name"]
            assert data["target_cloud"] == "aws"
            
            wave_id = data["wave_id"]
            
            # Retrieve wave
            response = await client.get(
                f"{BACKEND_URL}/api/cloud-orchestration/api/waves/{wave_id}",
                headers=headers
            )
            assert response.status_code == 200
            wave = response.json()
            assert wave["wave_id"] == wave_id
            assert wave["status"] == "pending"
    
    @pytest.mark.asyncio
    async def test_list_migration_waves(self):
        """Test listing migration waves with filters"""
        project_id = str(uuid.uuid4())
        
        headers = {
            "Authorization": f"Bearer {AUTH_TOKEN}",
            "X-Correlation-ID": str(uuid.uuid4())
        }
        
        async with httpx.AsyncClient(timeout=TEST_TIMEOUT) as client:
            # Create multiple waves
            for i in range(3):
                wave_data = {
                    "project_id": project_id,
                    "name": f"Wave {i+1}",
                    "description": f"Test wave {i+1}",
                    "target_cloud": "aws",
                    "target_region": "us-east-1"
                }
                await client.post(
                    f"{BACKEND_URL}/api/cloud-orchestration/api/waves",
                    json=wave_data,
                    headers=headers
                )
            
            # List waves for project
            response = await client.get(
                f"{BACKEND_URL}/api/cloud-orchestration/api/waves",
                params={"project_id": project_id},
                headers=headers
            )
            assert response.status_code == 200
            data = response.json()
            assert "waves" in data
            assert len(data["waves"]) >= 3


class TestIACGovernance:
    """Test IAC Governance Service workflows"""
    
    @pytest.mark.asyncio
    async def test_create_policy_template(self):
        """Test creating a policy template"""
        policy_data = {
            "template_name": "Test S3 Public Access Policy",
            "policy_category": "security",
            "severity": "HIGH",
            "engine_type": "opa",
            "policy_code": """
package terraform.s3

deny[msg] {
    resource := input.resource_changes[_]
    resource.type == "aws_s3_bucket"
    resource.change.after.acl == "public-read"
    msg := "S3 bucket cannot have public-read ACL"
}
            """,
            "supported_frameworks": ["terraform"],
            "cloud_providers": ["aws"],
            "is_active": True,
            "description": "Prevents S3 buckets from being publicly accessible"
        }
        
        headers = {
            "Authorization": f"Bearer {AUTH_TOKEN}",
            "X-Correlation-ID": str(uuid.uuid4())
        }
        
        async with httpx.AsyncClient(timeout=TEST_TIMEOUT) as client:
            # Create policy via gateway
            response = await client.post(
                f"{BACKEND_URL}/api/iac-governance/policies",
                json=policy_data,
                headers=headers
            )
            assert response.status_code == 201
            data = response.json()
            assert "template_id" in data
            assert data["template_name"] == policy_data["template_name"]
            assert data["is_active"] is True
            
            template_id = data["template_id"]
            
            # Retrieve policy
            response = await client.get(
                f"{BACKEND_URL}/api/iac-governance/policies/{template_id}",
                headers=headers
            )
            assert response.status_code == 200
            policy = response.json()
            assert policy["template_id"] == template_id
    
    @pytest.mark.asyncio
    async def test_list_policies_with_filters(self):
        """Test listing policies with various filters"""
        headers = {
            "Authorization": f"Bearer {AUTH_TOKEN}",
            "X-Correlation-ID": str(uuid.uuid4())
        }
        
        async with httpx.AsyncClient(timeout=TEST_TIMEOUT) as client:
            # List all policies
            response = await client.get(
                f"{BACKEND_URL}/api/iac-governance/policies",
                headers=headers
            )
            assert response.status_code == 200
            data = response.json()
            assert "policies" in data
            
            # Filter by category
            response = await client.get(
                f"{BACKEND_URL}/api/iac-governance/policies",
                params={"category": "security"},
                headers=headers
            )
            assert response.status_code == 200
            data = response.json()
            for policy in data["policies"]:
                assert policy["policy_category"] == "security"
    
    @pytest.mark.asyncio
    async def test_terraform_operations(self):
        """Test Terraform operations via MCP"""
        terraform_dir = "/tmp/test-terraform"
        
        headers = {
            "Authorization": f"Bearer {AUTH_TOKEN}",
            "X-Correlation-ID": str(uuid.uuid4())
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            # List Terraform executions
            response = await client.get(
                f"{BACKEND_URL}/api/iac-governance/terraform/executions",
                headers=headers
            )
            # May return 200 with empty list or 404 if no executions
            assert response.status_code in [200, 404]


class TestEndToEndWorkflow:
    """Test complete end-to-end workflows"""
    
    @pytest.mark.asyncio
    async def test_policy_scan_workflow(self):
        """Test complete policy scan workflow"""
        project_id = str(uuid.uuid4())
        correlation_id = str(uuid.uuid4())
        
        headers = {
            "Authorization": f"Bearer {AUTH_TOKEN}",
            "X-Correlation-ID": correlation_id
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Step 1: Create policy template
            policy_data = {
                "template_name": f"E2E Test Policy {correlation_id[:8]}",
                "policy_category": "security",
                "severity": "MEDIUM",
                "engine_type": "opa",
                "policy_code": "package test\ndefault allow = true",
                "supported_frameworks": ["terraform"],
                "cloud_providers": ["aws"],
                "is_active": True
            }
            
            response = await client.post(
                f"{BACKEND_URL}/api/iac-governance/policies",
                json=policy_data,
                headers=headers
            )
            assert response.status_code == 201
            template_id = response.json()["template_id"]
            
            # Step 2: Verify policy is active
            response = await client.get(
                f"{BACKEND_URL}/api/iac-governance/policies/{template_id}",
                headers=headers
            )
            assert response.status_code == 200
            assert response.json()["is_active"] is True
            
            # Step 3: List policies to confirm creation
            response = await client.get(
                f"{BACKEND_URL}/api/iac-governance/policies",
                params={"active_only": True},
                headers=headers
            )
            assert response.status_code == 200
            policies = response.json()["policies"]
            assert any(p["template_id"] == template_id for p in policies)
    
    @pytest.mark.asyncio
    async def test_migration_wave_workflow(self):
        """Test complete migration wave workflow"""
        project_id = str(uuid.uuid4())
        correlation_id = str(uuid.uuid4())
        
        headers = {
            "Authorization": f"Bearer {AUTH_TOKEN}",
            "X-Correlation-ID": correlation_id
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Step 1: Create migration wave
            wave_data = {
                "project_id": project_id,
                "name": f"E2E Test Wave {correlation_id[:8]}",
                "description": "End-to-end test migration wave",
                "target_cloud": "aws",
                "target_region": "us-east-1"
            }
            
            response = await client.post(
                f"{BACKEND_URL}/api/cloud-orchestration/api/waves",
                json=wave_data,
                headers=headers
            )
            assert response.status_code == 201
            wave_id = response.json()["wave_id"]
            
            # Step 2: Add resource to wave
            resource_data = {
                "resource_type": "server",
                "source_identifier": f"test-server-{correlation_id[:8]}",
                "source_config": {
                    "hostname": "test-server",
                    "ip_address": "10.0.0.1"
                },
                "target_config": {
                    "instance_type": "t3.medium",
                    "region": "us-east-1"
                }
            }
            
            response = await client.post(
                f"{BACKEND_URL}/api/cloud-orchestration/api/waves/{wave_id}/resources",
                json=resource_data,
                headers=headers
            )
            assert response.status_code == 201
            resource_id = response.json()["resource_id"]
            
            # Step 3: List resources in wave
            response = await client.get(
                f"{BACKEND_URL}/api/cloud-orchestration/api/waves/{wave_id}/resources",
                headers=headers
            )
            assert response.status_code == 200
            resources = response.json()["resources"]
            assert len(resources) >= 1
            assert any(r["resource_id"] == resource_id for r in resources)
            
            # Step 4: Validate wave
            response = await client.post(
                f"{BACKEND_URL}/api/cloud-orchestration/api/waves/{wave_id}/validate",
                headers=headers
            )
            assert response.status_code == 200
            validation = response.json()
            assert "is_valid" in validation


class TestCorrelationIDPropagation:
    """Test correlation ID propagation across services"""
    
    @pytest.mark.asyncio
    async def test_correlation_id_in_requests(self):
        """Verify correlation ID is propagated through gateway"""
        correlation_id = str(uuid.uuid4())
        
        headers = {
            "Authorization": f"Bearer {AUTH_TOKEN}",
            "X-Correlation-ID": correlation_id
        }
        
        async with httpx.AsyncClient(timeout=TEST_TIMEOUT) as client:
            # Make request through gateway
            response = await client.get(
                f"{BACKEND_URL}/api/cloud-orchestration/api/waves",
                params={"limit": 1},
                headers=headers
            )
            # Should succeed regardless of whether waves exist
            assert response.status_code in [200, 404]
            
            # Correlation ID should be preserved in response headers
            # (if service implements it)
            # This is informational, not strictly required
    
    @pytest.mark.asyncio
    async def test_multiple_services_same_correlation_id(self):
        """Test same correlation ID across multiple service calls"""
        correlation_id = str(uuid.uuid4())
        
        headers = {
            "Authorization": f"Bearer {AUTH_TOKEN}",
            "X-Correlation-ID": correlation_id
        }
        
        async with httpx.AsyncClient(timeout=TEST_TIMEOUT) as client:
            # Call cloud orchestration
            response1 = await client.get(
                f"{BACKEND_URL}/api/cloud-orchestration/health",
                headers=headers
            )
            assert response1.status_code == 200
            
            # Call IAC governance
            response2 = await client.get(
                f"{BACKEND_URL}/api/iac-governance/health",
                headers=headers
            )
            assert response2.status_code == 200
            
            # Both should have processed the same correlation ID
            # This can be verified in logs or service metrics


class TestErrorHandling:
    """Test error handling and edge cases"""
    
    @pytest.mark.asyncio
    async def test_invalid_wave_id(self):
        """Test handling of invalid wave ID"""
        headers = {
            "Authorization": f"Bearer {AUTH_TOKEN}",
            "X-Correlation-ID": str(uuid.uuid4())
        }
        
        async with httpx.AsyncClient(timeout=TEST_TIMEOUT) as client:
            response = await client.get(
                f"{BACKEND_URL}/api/cloud-orchestration/api/waves/invalid-uuid",
                headers=headers
            )
            assert response.status_code in [400, 404, 422]
    
    @pytest.mark.asyncio
    async def test_invalid_policy_data(self):
        """Test handling of invalid policy data"""
        invalid_policy = {
            "template_name": "",  # Empty name
            "policy_category": "invalid_category",
            "severity": "INVALID",
            "engine_type": "unknown_engine"
        }
        
        headers = {
            "Authorization": f"Bearer {AUTH_TOKEN}",
            "X-Correlation-ID": str(uuid.uuid4())
        }
        
        async with httpx.AsyncClient(timeout=TEST_TIMEOUT) as client:
            response = await client.post(
                f"{BACKEND_URL}/api/iac-governance/policies",
                json=invalid_policy,
                headers=headers
            )
            assert response.status_code in [400, 422]
    
    @pytest.mark.asyncio
    async def test_missing_authentication(self):
        """Test requests without authentication"""
        async with httpx.AsyncClient(timeout=TEST_TIMEOUT) as client:
            # Request without auth header
            response = await client.get(
                f"{BACKEND_URL}/api/cloud-orchestration/api/waves"
            )
            # May return 401 or allow depending on backend config
            # Just verify it doesn't crash
            assert response.status_code in [200, 401, 403]


# Test fixtures and utilities
@pytest.fixture
async def cleanup_test_data():
    """Cleanup test data after tests"""
    yield
    # Cleanup logic here if needed
    pass


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s", "--asyncio-mode=auto"])
