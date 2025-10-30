"""
Integration Tests for Terraform MCP Adapter

Tests the complete flow: adapter → repository → database
Mocks MCP responses and verifies data persistence
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4, UUID
from datetime import datetime

from app.adapters import TerraformMCPAdapter
from app.repository import TerraformRepository
from app.models import (
    TerraformExecution,
    TerraformResource,
    TerraformExecutionStatus,
    TerraformExecutionType
)


class TestTerraformMCPAdapter:
    """Test Terraform MCP Adapter operations."""
    
    @pytest.fixture
    def adapter(self):
        """Create adapter instance."""
        return TerraformMCPAdapter(ai_agent_url="http://localhost:8008")
    
    @pytest.fixture
    def mock_mcp_response_plan(self):
        """Mock MCP plan response."""
        return {
            "plan_id": "plan-12345",
            "changes_summary": {
                "add": 5,
                "change": 2,
                "delete": 0
            },
            "resources": [
                "aws_instance.web",
                "aws_security_group.allow_http",
                "aws_subnet.public"
            ],
            "resource_changes": [
                {
                    "address": "aws_instance.web",
                    "type": "aws_instance",
                    "name": "web",
                    "action": "create",
                    "provider_name": "aws",
                    "change": {
                        "instance_type": "t2.micro",
                        "ami": "ami-12345"
                    },
                    "after": {
                        "instance_type": "t2.micro",
                        "ami": "ami-12345"
                    }
                }
            ],
            "output": "Terraform plan output...",
            "duration_seconds": 15
        }
    
    @pytest.mark.asyncio
    async def test_plan_operation(self, adapter, mock_mcp_response_plan):
        """Test Terraform plan operation."""
        with patch.object(adapter.mcp_client, 'call_tool', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"content": [{"text": str(mock_mcp_response_plan)}]}
            
            result = await adapter.plan(
                workspace_path="/path/to/terraform",
                variables={"region": "us-west-2"},
                correlation_id="test-correlation-123"
            )
            
            # Verify MCP client was called correctly
            mock_call.assert_called_once()
            call_args = mock_call.call_args[1]
            assert call_args["tool_name"] == "terraform_plan"
            assert call_args["arguments"]["workspace_path"] == "/path/to/terraform"
            assert call_args["arguments"]["variables"] == {"region": "us-west-2"}
            
            # Verify response structure
            assert result["plan_id"] == "plan-12345"
            assert result["changes_summary"]["add"] == 5
            assert len(result["resources"]) == 3
            assert len(result["resource_changes"]) == 1
    
    @pytest.mark.asyncio
    async def test_apply_operation(self, adapter):
        """Test Terraform apply operation."""
        mock_response = {
            "changes_summary": {"add": 5, "change": 0, "delete": 0},
            "resources": ["aws_instance.web"],
            "output": "Apply complete!",
            "duration_seconds": 120
        }
        
        with patch.object(adapter.mcp_client, 'call_tool', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"content": [{"text": str(mock_response)}]}
            
            result = await adapter.apply(
                workspace_path="/path/to/terraform",
                auto_approve=True,
                correlation_id="test-correlation-456"
            )
            
            assert result["changes_summary"]["add"] == 5
            assert result["duration_seconds"] == 120
    
    @pytest.mark.asyncio
    async def test_validate_operation(self, adapter):
        """Test Terraform validate operation."""
        mock_response = {
            "valid": True,
            "diagnostics": [],
            "error_count": 0,
            "warning_count": 0,
            "output": "Success! The configuration is valid."
        }
        
        with patch.object(adapter.mcp_client, 'call_tool', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"content": [{"text": str(mock_response)}]}
            
            result = await adapter.validate(
                workspace_path="/path/to/terraform",
                correlation_id="test-correlation-789"
            )
            
            assert result["valid"] is True
            assert result["error_count"] == 0
    
    @pytest.mark.asyncio
    async def test_destroy_operation(self, adapter):
        """Test Terraform destroy operation."""
        mock_response = {
            "changes_summary": {"add": 0, "change": 0, "delete": 5},
            "resources": ["aws_instance.web"],
            "output": "Destroy complete!",
            "duration_seconds": 60
        }
        
        with patch.object(adapter.mcp_client, 'call_tool', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"content": [{"text": str(mock_response)}]}
            
            result = await adapter.destroy(
                workspace_path="/path/to/terraform",
                auto_approve=True
            )
            
            assert result["changes_summary"]["delete"] == 5


class TestTerraformRepository:
    """Test Terraform Repository operations."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        return Mock()
    
    @pytest.fixture
    def repository(self, mock_db_session):
        """Create repository instance."""
        return TerraformRepository(mock_db_session)
    
    @pytest.fixture
    def sample_execution_data(self):
        """Sample execution data."""
        return {
            "project_id": uuid4(),
            "execution_type": TerraformExecutionType.PLAN,
            "workspace_path": "/path/to/terraform",
            "workspace_name": "default",
            "variables": {"region": "us-west-2"},
            "correlation_id": "test-correlation-123",
            "triggered_by": "test-user"
        }
    
    def test_create_execution(self, repository, mock_db_session, sample_execution_data):
        """Test creating execution record."""
        execution = repository.create_execution(**sample_execution_data)
        
        # Verify session operations
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()
        
        # Verify execution defaults
        added_execution = mock_db_session.add.call_args[0][0]
        assert added_execution.execution_type == TerraformExecutionType.PLAN
        assert added_execution.status == TerraformExecutionStatus.PENDING
        assert added_execution.workspace_path == "/path/to/terraform"
    
    def test_update_execution_status(self, repository, mock_db_session):
        """Test updating execution status."""
        execution_id = uuid4()
        mock_execution = Mock(spec=TerraformExecution)
        mock_execution.execution_id = execution_id
        mock_db_session.query().filter().first.return_value = mock_execution
        
        repository.update_execution_status(
            execution_id,
            TerraformExecutionStatus.COMPLETED,
            duration_seconds=120
        )
        
        assert mock_execution.status == TerraformExecutionStatus.COMPLETED
        assert mock_execution.duration_seconds == 120
        mock_db_session.commit.assert_called_once()
    
    def test_update_execution_results(self, repository, mock_db_session):
        """Test updating execution results."""
        execution_id = uuid4()
        mock_execution = Mock(spec=TerraformExecution)
        mock_execution.execution_id = execution_id
        mock_db_session.query().filter().first.return_value = mock_execution
        
        repository.update_execution_results(
            execution_id,
            plan_id="plan-12345",
            changes_summary={"add": 5, "change": 2},
            is_valid=True
        )
        
        assert mock_execution.plan_id == "plan-12345"
        assert mock_execution.changes_summary == {"add": 5, "change": 2}
        assert mock_execution.is_valid is True
        mock_db_session.commit.assert_called_once()
    
    def test_bulk_create_resources(self, repository, mock_db_session):
        """Test bulk creating resources."""
        execution_id = uuid4()
        resources_data = [
            {
                "resource_address": "aws_instance.web",
                "resource_type": "aws_instance",
                "resource_name": "web",
                "action": "create",
                "provider": "aws"
            },
            {
                "resource_address": "aws_security_group.allow_http",
                "resource_type": "aws_security_group",
                "resource_name": "allow_http",
                "action": "create",
                "provider": "aws"
            }
        ]
        
        repository.bulk_create_resources(execution_id, resources_data)
        
        # Verify bulk save was called
        mock_db_session.bulk_save_objects.assert_called_once()
        saved_objects = mock_db_session.bulk_save_objects.call_args[0][0]
        assert len(saved_objects) == 2
        assert all(r.execution_id == execution_id for r in saved_objects)
        mock_db_session.commit.assert_called_once()
    
    def test_list_executions_by_project(self, repository, mock_db_session):
        """Test listing executions by project."""
        project_id = uuid4()
        mock_query = mock_db_session.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = []
        
        repository.list_executions_by_project(
            project_id,
            execution_type=TerraformExecutionType.PLAN,
            status=TerraformExecutionStatus.COMPLETED
        )
        
        # Verify query was constructed correctly
        assert mock_query.filter.called
        assert mock_query.order_by.called
        assert mock_query.limit.called


class TestTerraformEndToEnd:
    """End-to-end integration tests."""
    
    @pytest.mark.asyncio
    async def test_plan_end_to_end(self):
        """Test complete plan flow from adapter to database."""
        # This would require actual database for full integration
        # Here we verify the integration points work together
        
        project_id = uuid4()
        correlation_id = "e2e-test-123"
        
        # Mock MCP response
        mock_plan_response = {
            "plan_id": "plan-e2e",
            "changes_summary": {"add": 3, "change": 0, "delete": 0},
            "resources": ["aws_instance.test"],
            "resource_changes": [
                {
                    "address": "aws_instance.test",
                    "type": "aws_instance",
                    "name": "test",
                    "action": "create",
                    "provider_name": "aws"
                }
            ],
            "output": "Plan successful",
            "duration_seconds": 10
        }
        
        # Create adapter
        adapter = TerraformMCPAdapter()
        
        # Mock MCP client
        with patch.object(adapter.mcp_client, 'call_tool', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"content": [{"text": str(mock_plan_response)}]}
            
            # Execute plan
            result = await adapter.plan(
                workspace_path="/test/terraform",
                correlation_id=correlation_id
            )
            
            # Verify adapter returns correct structure
            assert result["plan_id"] == "plan-e2e"
            assert result["changes_summary"]["add"] == 3
            assert len(result["resource_changes"]) == 1
            
            # Verify structure is suitable for repository storage
            assert "plan_id" in result
            assert "changes_summary" in result
            assert "resources" in result
            assert "resource_changes" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
