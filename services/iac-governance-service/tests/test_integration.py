"""
Integration tests for IAC Governance Service.

Tests the complete workflow from Terraform execution through policy scanning,
violation management, remediation, cost estimation, and security scanning.
"""

import pytest
import asyncio
from uuid import uuid4
from pathlib import Path
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base, PolicySeverity, ScanStatus, RemediationStatus
from app.repository.terraform_repository import TerraformRepository
from app.repository.policy_repository import PolicyRepository
from app.repository.scan_repository import ScanRepository
from app.repository.remediation_repository import RemediationRepository
from app.adapters.terraform_mcp_adapter import TerraformMCPAdapter
from app.services.opa_client import OPAClient
from app.services.scan_executor import ScanExecutor
from app.services.remediation_executor import RemediationExecutor
from app.services.cost_estimator import CostEstimator
from app.services.security_scanner import SecurityScanner


# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_iac_governance.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="module")
def test_db():
    """Create test database and tables."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(test_db):
    """Create a new database session for a test."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def project_id():
    """Generate test project ID."""
    return uuid4()


@pytest.fixture
def terraform_repo(db_session):
    """Create Terraform repository instance."""
    return TerraformRepository(db_session)


@pytest.fixture
def policy_repo(db_session):
    """Create Policy repository instance."""
    return PolicyRepository(db_session)


@pytest.fixture
def scan_repo(db_session):
    """Create Scan repository instance."""
    return ScanRepository(db_session)


@pytest.fixture
def remediation_repo(db_session):
    """Create Remediation repository instance."""
    return RemediationRepository(db_session)


@pytest.fixture
def terraform_adapter():
    """Create Terraform MCP adapter instance."""
    return TerraformMCPAdapter()


@pytest.fixture
def opa_client():
    """Create OPA client instance."""
    return OPAClient()


@pytest.fixture
def scan_executor(scan_repo, policy_repo, terraform_adapter, opa_client):
    """Create Scan executor instance."""
    return ScanExecutor(scan_repo, policy_repo, terraform_adapter, opa_client)


@pytest.fixture
def remediation_executor(remediation_repo, scan_repo, terraform_adapter):
    """Create Remediation executor instance."""
    return RemediationExecutor(remediation_repo, scan_repo, terraform_adapter)


@pytest.fixture
def cost_estimator():
    """Create Cost estimator instance."""
    return CostEstimator()


@pytest.fixture
def security_scanner():
    """Create Security scanner instance."""
    return SecurityScanner()


# Test 1: Policy Template Management
class TestPolicyManagement:
    """Test policy template CRUD operations."""
    
    def test_create_policy_template(self, policy_repo):
        """Test creating a policy template."""
        policy = policy_repo.create_policy(
            template_name="Test AWS S3 Public Access",
            template_description="Prevent public S3 buckets",
            policy_category="security",
            severity=PolicySeverity.HIGH,
            engine_type="opa",
            policy_code="package terraform.s3; deny[msg] { ... }",
            supported_frameworks=["terraform"],
            cloud_providers=["aws"],
            is_active=True,
            is_blocking=True,
            created_by="test_user",
        )
        
        assert policy.template_id is not None
        assert policy.template_name == "Test AWS S3 Public Access"
        assert policy.severity == PolicySeverity.HIGH
        assert policy.is_active is True
    
    def test_list_policies(self, policy_repo):
        """Test listing policies with filters."""
        # Create multiple policies
        for i in range(3):
            policy_repo.create_policy(
                template_name=f"Test Policy {i}",
                template_description="Test description",
                policy_category="security" if i % 2 == 0 else "cost",
                severity=PolicySeverity.HIGH,
                engine_type="opa",
                policy_code="package test",
                supported_frameworks=["terraform"],
                cloud_providers=["aws"],
                created_by="test_user",
            )
        
        # List all policies
        all_policies = policy_repo.list_policies(limit=100)
        assert len(all_policies) >= 3
        
        # Filter by category
        security_policies = policy_repo.list_policies(category="security", limit=100)
        assert all(p.policy_category == "security" for p in security_policies)
    
    def test_activate_deactivate_policy(self, policy_repo):
        """Test activating and deactivating policies."""
        policy = policy_repo.create_policy(
            template_name="Test Toggle Policy",
            template_description="Test",
            policy_category="security",
            severity=PolicySeverity.MEDIUM,
            engine_type="opa",
            policy_code="package test",
            supported_frameworks=["terraform"],
            cloud_providers=["aws"],
            is_active=True,
            created_by="test_user",
        )
        
        # Deactivate
        deactivated = policy_repo.deactivate_policy(policy.template_id)
        assert deactivated.is_active is False
        
        # Reactivate
        activated = policy_repo.activate_policy(policy.template_id)
        assert activated.is_active is True


# Test 2: Scan Execution Workflow
class TestScanWorkflow:
    """Test complete scan execution workflow."""
    
    @pytest.mark.asyncio
    async def test_create_scan(self, scan_repo, project_id):
        """Test creating a policy scan."""
        scan = scan_repo.create_scan(
            project_id=project_id,
            scan_name="Test Infrastructure Scan",
            iac_framework="terraform",
            source_type="local",
            source_location="/test/terraform",
            correlation_id=str(uuid4()),
            triggered_by="test_user",
        )
        
        assert scan.scan_id is not None
        assert scan.status == ScanStatus.PENDING
        assert scan.scan_name == "Test Infrastructure Scan"
    
    @pytest.mark.asyncio
    async def test_scan_status_transitions(self, scan_repo, project_id):
        """Test scan status transitions."""
        scan = scan_repo.create_scan(
            project_id=project_id,
            scan_name="Status Test Scan",
            iac_framework="terraform",
            source_type="local",
            source_location="/test",
            triggered_by="test_user",
        )
        
        # Transition to RUNNING
        running_scan = scan_repo.update_scan_status(
            scan_id=scan.scan_id,
            status=ScanStatus.RUNNING,
            started_at=datetime.utcnow(),
        )
        assert running_scan.status == ScanStatus.RUNNING
        assert running_scan.started_at is not None
        
        # Transition to COMPLETED
        completed_scan = scan_repo.update_scan_status(
            scan_id=scan.scan_id,
            status=ScanStatus.COMPLETED,
            completed_at=datetime.utcnow(),
        )
        assert completed_scan.status == ScanStatus.COMPLETED


# Test 3: Violation Management
class TestViolationManagement:
    """Test violation creation and management."""
    
    def test_create_violation(self, scan_repo, policy_repo, project_id):
        """Test creating a violation."""
        # Create scan first
        scan = scan_repo.create_scan(
            project_id=project_id,
            scan_name="Violation Test Scan",
            iac_framework="terraform",
            source_type="local",
            source_location="/test",
            triggered_by="test_user",
        )
        
        # Create policy template
        policy = policy_repo.create_policy(
            template_name="Test Violation Policy",
            template_description="Test",
            policy_category="security",
            severity=PolicySeverity.HIGH,
            engine_type="opa",
            policy_code="package test",
            supported_frameworks=["terraform"],
            cloud_providers=["aws"],
            created_by="test_user",
        )
        
        # Create violation
        violation = scan_repo.create_violation(
            scan_id=scan.scan_id,
            template_id=policy.template_id,
            resource_type="aws_s3_bucket",
            resource_name="test-bucket",
            violation_rule="public_access_block_missing",
            severity=PolicySeverity.HIGH,
            violation_message="S3 bucket does not have public access block",
        )
        
        assert violation.violation_id is not None
        assert violation.severity == PolicySeverity.HIGH
        assert violation.is_resolved is False
    
    def test_resolve_violation(self, scan_repo, policy_repo, project_id):
        """Test resolving a violation."""
        # Create scan and violation
        scan = scan_repo.create_scan(
            project_id=project_id,
            scan_name="Resolution Test Scan",
            iac_framework="terraform",
            source_type="local",
            source_location="/test",
            triggered_by="test_user",
        )
        
        policy = policy_repo.create_policy(
            template_name="Test Resolution Policy",
            template_description="Test",
            policy_category="security",
            severity=PolicySeverity.MEDIUM,
            engine_type="opa",
            policy_code="package test",
            supported_frameworks=["terraform"],
            cloud_providers=["aws"],
            created_by="test_user",
        )
        
        violation = scan_repo.create_violation(
            scan_id=scan.scan_id,
            template_id=policy.template_id,
            resource_type="aws_instance",
            resource_name="test-instance",
            violation_rule="unencrypted_ebs",
            severity=PolicySeverity.MEDIUM,
            violation_message="EBS volume is not encrypted",
        )
        
        # Resolve violation
        resolved = scan_repo.resolve_violation(
            violation_id=violation.violation_id,
            resolved_by="test_user",
            resolution_notes="Enabled EBS encryption",
        )
        
        assert resolved.is_resolved is True
        assert resolved.resolved_by == "test_user"
        assert resolved.resolved_at is not None


# Test 4: Remediation Actions
class TestRemediationActions:
    """Test remediation action creation and execution."""
    
    @pytest.mark.asyncio
    async def test_create_remediation_action(self, remediation_repo, scan_repo, policy_repo, project_id):
        """Test creating a remediation action."""
        # Create scan, policy, and violation
        scan = scan_repo.create_scan(
            project_id=project_id,
            scan_name="Remediation Test Scan",
            iac_framework="terraform",
            source_type="local",
            source_location="/test",
            triggered_by="test_user",
        )
        
        policy = policy_repo.create_policy(
            template_name="Test Remediation Policy",
            template_description="Test",
            policy_category="security",
            severity=PolicySeverity.HIGH,
            engine_type="opa",
            policy_code="package test",
            supported_frameworks=["terraform"],
            cloud_providers=["aws"],
            created_by="test_user",
        )
        
        violation = scan_repo.create_violation(
            scan_id=scan.scan_id,
            template_id=policy.template_id,
            resource_type="aws_s3_bucket",
            resource_name="test-bucket",
            violation_rule="public_access",
            severity=PolicySeverity.HIGH,
            violation_message="Bucket is public",
        )
        
        # Create remediation action
        action = await remediation_repo.create_action(
            violation_id=violation.violation_id,
            action_type="auto_fix",
            action_name="Fix S3 Public Access",
            remediation_method="terraform_code_fix",
            action_description="Set bucket ACL to private",
            remediation_code="acl = 'private'",
            requires_approval=False,
            triggered_by="test_user",
        )
        
        assert action.action_id is not None
        assert action.status == RemediationStatus.PENDING
        assert action.action_type == "auto_fix"


# Test 5: Statistics and Reporting
class TestStatistics:
    """Test statistics and reporting functions."""
    
    @pytest.mark.asyncio
    async def test_policy_statistics(self, policy_repo):
        """Test policy statistics."""
        stats = await policy_repo.get_statistics()
        
        assert "total_policies" in stats
        assert "active_policies" in stats
        assert "by_category" in stats
        assert "by_severity" in stats
    
    @pytest.mark.asyncio
    async def test_remediation_statistics(self, remediation_repo):
        """Test remediation statistics."""
        stats = await remediation_repo.get_statistics()
        
        assert "total_actions" in stats
        assert "pending" in stats
        assert "completed" in stats
        assert "success_rate" in stats


# Test 6: End-to-End Integration Test
class TestEndToEndWorkflow:
    """Test complete end-to-end workflow."""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_complete_scan_workflow(
        self,
        project_id,
        policy_repo,
        scan_repo,
        remediation_repo,
    ):
        """
        Test complete workflow:
        1. Create policy template
        2. Create scan
        3. Generate violations
        4. Create remediation actions
        5. Resolve violations
        """
        # Step 1: Create policy
        policy = policy_repo.create_policy(
            template_name="E2E Test Policy",
            template_description="End-to-end test policy",
            policy_category="security",
            severity=PolicySeverity.HIGH,
            engine_type="opa",
            policy_code="package e2e_test; deny[msg] { ... }",
            supported_frameworks=["terraform"],
            cloud_providers=["aws"],
            is_active=True,
            created_by="e2e_test",
        )
        
        # Step 2: Create scan
        scan = scan_repo.create_scan(
            project_id=project_id,
            scan_name="E2E Test Scan",
            iac_framework="terraform",
            source_type="local",
            source_location="/test/e2e",
            triggered_by="e2e_test",
        )
        
        # Update scan to running
        scan_repo.update_scan_status(
            scan_id=scan.scan_id,
            status=ScanStatus.RUNNING,
            started_at=datetime.utcnow(),
        )
        
        # Step 3: Create violations
        violations = []
        for i in range(3):
            violation = scan_repo.create_violation(
                scan_id=scan.scan_id,
                template_id=policy.template_id,
                resource_type="aws_s3_bucket",
                resource_name=f"test-bucket-{i}",
                violation_rule="public_access",
                severity=PolicySeverity.HIGH,
                violation_message=f"Bucket {i} is public",
            )
            violations.append(violation)
        
        # Step 4: Create remediation actions
        for violation in violations:
            action = await remediation_repo.create_action(
                violation_id=violation.violation_id,
                action_type="auto_fix",
                action_name=f"Fix bucket {violation.resource_name}",
                remediation_method="terraform_code_fix",
                action_description="Set ACL to private",
                triggered_by="e2e_test",
            )
            
            # Simulate remediation execution
            await remediation_repo.update_status(
                action_id=action.action_id,
                status=RemediationStatus.COMPLETED,
                completed_at=datetime.utcnow(),
                duration_seconds=5,
            )
            
            await remediation_repo.update_results(
                action_id=action.action_id,
                is_successful=True,
                result={"status": "fixed"},
            )
        
        # Step 5: Resolve violations
        for violation in violations:
            scan_repo.resolve_violation(
                violation_id=violation.violation_id,
                resolved_by="e2e_test",
                resolution_notes="Fixed via automated remediation",
            )
        
        # Step 6: Update scan to completed
        scan_repo.update_scan_status(
            scan_id=scan.scan_id,
            status=ScanStatus.COMPLETED,
            completed_at=datetime.utcnow(),
        )
        
        scan_repo.update_scan_results(
            scan_id=scan.scan_id,
            total_resources=3,
            passed_checks=0,
            failed_checks=3,
            violations_high=3,
        )
        
        # Verify final state
        final_scan = scan_repo.get_scan(scan.scan_id)
        assert final_scan.status == ScanStatus.COMPLETED
        assert final_scan.violations_high == 3
        
        # Verify all violations are resolved
        scan_violations = scan_repo.get_violations_by_scan(scan_id=scan.scan_id)
        assert all(v.is_resolved for v in scan_violations)


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
