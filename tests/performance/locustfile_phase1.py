"""
Phase 1 Performance Tests using Locust
Load testing for Cloud Orchestration and IAC Governance services

Run with:
    locust -f tests/performance/locustfile_phase1.py --host=http://localhost:8000

Target: 100 concurrent users, <500ms p95 latency
"""

from locust import HttpUser, task, between, events
import uuid
import random
from typing import Dict, Any

# Test data
PROJECTS = [str(uuid.uuid4()) for _ in range(10)]
POLICY_TEMPLATES = []
MIGRATION_WAVES = []


class Phase1LoadUser(HttpUser):
    """
    Simulates user load across Phase 1 services
    """
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    def on_start(self):
        """Setup: Create initial test data"""
        self.project_id = random.choice(PROJECTS)
        self.correlation_id = str(uuid.uuid4())
        self.headers = {
            "Authorization": "Bearer service-backend-token",
            "X-Correlation-ID": self.correlation_id,
            "Content-Type": "application/json"
        }
    
    @task(3)
    def list_migration_waves(self):
        """List migration waves (high frequency operation)"""
        with self.client.get(
            "/api/cloud-orchestration/api/waves",
            params={"project_id": self.project_id, "limit": 10},
            headers=self.headers,
            catch_response=True,
            name="List Migration Waves"
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
    
    @task(2)
    def get_migration_wave_details(self):
        """Get wave details if waves exist"""
        if MIGRATION_WAVES:
            wave_id = random.choice(MIGRATION_WAVES)
            with self.client.get(
                f"/api/cloud-orchestration/api/waves/{wave_id}",
                headers=self.headers,
                catch_response=True,
                name="Get Wave Details"
            ) as response:
                if response.status_code in [200, 404]:
                    response.success()
                else:
                    response.failure(f"Unexpected status code: {response.status_code}")
    
    @task(1)
    def create_migration_wave(self):
        """Create new migration wave (lower frequency)"""
        wave_data = {
            "project_id": self.project_id,
            "name": f"Load Test Wave {uuid.uuid4().hex[:8]}",
            "description": "Performance test migration wave",
            "target_cloud": random.choice(["aws", "azure", "gcp"]),
            "target_region": random.choice(["us-east-1", "us-west-2", "eu-west-1"]),
            "wave_metadata": {
                "test": True,
                "load_test": True
            }
        }
        
        with self.client.post(
            "/api/cloud-orchestration/api/waves",
            json=wave_data,
            headers=self.headers,
            catch_response=True,
            name="Create Migration Wave"
        ) as response:
            if response.status_code == 201:
                wave = response.json()
                MIGRATION_WAVES.append(wave.get("wave_id"))
                response.success()
            elif response.status_code in [400, 422]:
                # Validation errors are acceptable
                response.success()
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
    
    @task(3)
    def list_policy_templates(self):
        """List policy templates (high frequency operation)"""
        with self.client.get(
            "/api/iac-governance/policies",
            params={"limit": 20},
            headers=self.headers,
            catch_response=True,
            name="List Policy Templates"
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
    
    @task(2)
    def get_policy_details(self):
        """Get policy template details"""
        if POLICY_TEMPLATES:
            template_id = random.choice(POLICY_TEMPLATES)
            with self.client.get(
                f"/api/iac-governance/policies/{template_id}",
                headers=self.headers,
                catch_response=True,
                name="Get Policy Details"
            ) as response:
                if response.status_code in [200, 404]:
                    response.success()
                else:
                    response.failure(f"Unexpected status code: {response.status_code}")
    
    @task(1)
    def create_policy_template(self):
        """Create new policy template (lower frequency)"""
        categories = ["security", "compliance", "cost", "performance", "reliability"]
        severities = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
        
        policy_data = {
            "template_name": f"Load Test Policy {uuid.uuid4().hex[:8]}",
            "policy_category": random.choice(categories),
            "severity": random.choice(severities),
            "engine_type": "opa",
            "policy_code": "package test\ndefault allow = true",
            "supported_frameworks": ["terraform"],
            "cloud_providers": [random.choice(["aws", "azure", "gcp"])],
            "is_active": random.choice([True, False]),
            "description": "Performance test policy template"
        }
        
        with self.client.post(
            "/api/iac-governance/policies",
            json=policy_data,
            headers=self.headers,
            catch_response=True,
            name="Create Policy Template"
        ) as response:
            if response.status_code == 201:
                policy = response.json()
                POLICY_TEMPLATES.append(policy.get("template_id"))
                response.success()
            elif response.status_code in [400, 422]:
                # Validation errors are acceptable
                response.success()
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
    
    @task(2)
    def list_terraform_executions(self):
        """List Terraform executions"""
        with self.client.get(
            "/api/iac-governance/terraform/executions",
            params={"limit": 10},
            headers=self.headers,
            catch_response=True,
            name="List Terraform Executions"
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
    
    @task(1)
    def check_service_health(self):
        """Check Phase 1 service health"""
        services = [
            ("/api/cloud-orchestration/health", "Cloud Orchestration Health"),
            ("/api/iac-governance/health", "IAC Governance Health"),
        ]
        
        service_url, service_name = random.choice(services)
        with self.client.get(
            service_url,
            headers=self.headers,
            catch_response=True,
            name=service_name
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Service unhealthy: {response.status_code}")


class HeavyLoadUser(HttpUser):
    """
    Simulates heavy users performing complex operations
    """
    wait_time = between(2, 5)
    
    def on_start(self):
        """Setup"""
        self.project_id = random.choice(PROJECTS)
        self.correlation_id = str(uuid.uuid4())
        self.headers = {
            "Authorization": "Bearer service-backend-token",
            "X-Correlation-ID": self.correlation_id,
            "Content-Type": "application/json"
        }
    
    @task(1)
    def create_wave_with_resources(self):
        """Create migration wave and add multiple resources"""
        # Create wave
        wave_data = {
            "project_id": self.project_id,
            "name": f"Heavy Load Wave {uuid.uuid4().hex[:8]}",
            "description": "Performance test - heavy load",
            "target_cloud": "aws",
            "target_region": "us-east-1"
        }
        
        with self.client.post(
            "/api/cloud-orchestration/api/waves",
            json=wave_data,
            headers=self.headers,
            catch_response=True,
            name="Create Wave (Heavy)"
        ) as response:
            if response.status_code != 201:
                response.failure(f"Wave creation failed: {response.status_code}")
                return
            
            wave_id = response.json().get("wave_id")
            response.success()
            
            # Add multiple resources
            for i in range(5):
                resource_data = {
                    "resource_type": random.choice(["server", "database", "storage"]),
                    "source_identifier": f"resource-{uuid.uuid4().hex[:8]}",
                    "source_config": {
                        "name": f"test-resource-{i}",
                        "type": "test"
                    },
                    "target_config": {
                        "region": "us-east-1"
                    }
                }
                
                with self.client.post(
                    f"/api/cloud-orchestration/api/waves/{wave_id}/resources",
                    json=resource_data,
                    headers=self.headers,
                    catch_response=True,
                    name="Add Resource (Heavy)"
                ) as res_response:
                    if res_response.status_code in [201, 400, 422]:
                        res_response.success()
                    else:
                        res_response.failure(f"Resource add failed: {res_response.status_code}")
    
    @task(1)
    def validate_wave(self):
        """Validate migration wave"""
        if MIGRATION_WAVES:
            wave_id = random.choice(MIGRATION_WAVES)
            with self.client.post(
                f"/api/cloud-orchestration/api/waves/{wave_id}/validate",
                headers=self.headers,
                catch_response=True,
                name="Validate Wave (Heavy)"
            ) as response:
                if response.status_code in [200, 404, 400]:
                    response.success()
                else:
                    response.failure(f"Wave validation failed: {response.status_code}")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Setup before test starts"""
    print("=== Starting Phase 1 Load Test ===")
    print(f"Target: {environment.host}")
    print(f"Test Projects: {len(PROJECTS)}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Cleanup after test stops"""
    print("=== Phase 1 Load Test Complete ===")
    print(f"Total Waves Created: {len(MIGRATION_WAVES)}")
    print(f"Total Policies Created: {len(POLICY_TEMPLATES)}")


# Performance targets
"""
Target Metrics:
- 100 concurrent users
- Response time p95 < 500ms
- Response time p99 < 1000ms
- Error rate < 1%
- Throughput > 1000 req/s

Run Commands:
  # Web UI mode
  locust -f tests/performance/locustfile_phase1.py --host=http://localhost:8000

  # Headless mode
  locust -f tests/performance/locustfile_phase1.py --host=http://localhost:8000 \\
         --users 100 --spawn-rate 10 --run-time 5m --headless

  # With HTML report
  locust -f tests/performance/locustfile_phase1.py --host=http://localhost:8000 \\
         --users 100 --spawn-rate 10 --run-time 5m --headless \\
         --html=phase1_load_test_report.html
"""
