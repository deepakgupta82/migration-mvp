# IaC Governance Service - API Contract

**Service Name**: iac-governance-service  
**Port**: 8013  
**Version**: 1.0.0  
**Protocol**: HTTP/REST  
**Base URL**: `http://localhost:8013/api/iac-governance`

---

## Overview

The IaC Governance Service provides enterprise-grade Infrastructure as Code (IaC) governance, policy enforcement, and cost estimation capabilities. It wraps Terraform MCP, CloudFormation MCP, and Bicep MCP servers to provide unified IaC generation, validation, and deployment orchestration with Open Policy Agent (OPA) integration for security and compliance.

### Key Responsibilities
- Multi-cloud IaC template generation (Terraform, CloudFormation, Bicep)
- Policy-as-code enforcement via OPA
- Pre-deployment cost estimation
- IaC validation and security scanning
- GitOps integration (GitHub Actions, Azure DevOps, GitLab CI)
- Drift detection and remediation

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│         IaC Governance Service (Port 8013)                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Terraform    │  │ CloudForm.   │  │ Bicep        │     │
│  │ MCP Adapter  │  │ MCP Adapter  │  │ MCP Adapter  │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                  │                  │              │
│  ┌──────▼──────────────────▼──────────────────▼──────┐     │
│  │       IaC Template Generation Engine             │     │
│  │  - Discovery data mapping                         │     │
│  │  - Best practices injection                       │     │
│  │  - Variable parameterization                      │     │
│  └──────────────────────────────────────────────────┘     │
│                                                              │
│  ┌──────────────────────────────────────────────────┐     │
│  │    Open Policy Agent (OPA) Engine                │     │
│  │  - Security policies (CIS benchmarks)            │     │
│  │  - Compliance policies (SOC2, HIPAA, PCI-DSS)    │     │
│  │  - Cost policies (budget constraints)            │     │
│  │  - Tagging policies                               │     │
│  └──────────────────────────────────────────────────┘     │
│                                                              │
│  ┌──────────────────────────────────────────────────┐     │
│  │    Cost Estimation Engine                         │     │
│  │  - AWS Pricing API integration                    │     │
│  │  - Azure Pricing API integration                  │     │
│  │  - GCP Pricing API integration                    │     │
│  │  - TCO calculation                                │     │
│  └──────────────────────────────────────────────────┘     │
│                                                              │
│  ┌──────────────────────────────────────────────────┐     │
│  │    GitOps Integration Layer                       │     │
│  │  - GitHub Actions workflow generation             │     │
│  │  - Azure DevOps pipeline generation               │     │
│  │  - GitLab CI pipeline generation                  │     │
│  └──────────────────────────────────────────────────┘     │
│                                                              │
│  ┌──────────────────────────────────────────────────┐     │
│  │    State Manager (PostgreSQL)                     │     │
│  │  - IaC templates                                  │     │
│  │  - Policy definitions                             │     │
│  │  - Validation results                             │     │
│  │  - Cost estimates                                 │     │
│  └──────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### IaC Templates Table
```sql
CREATE TABLE iac_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    template_type VARCHAR(50) NOT NULL CHECK (template_type IN ('terraform', 'cloudformation', 'bicep', 'arm')),
    target_csp VARCHAR(20) NOT NULL CHECK (target_csp IN ('aws', 'azure', 'gcp', 'multi-cloud')),
    template_content TEXT NOT NULL,
    variables JSONB DEFAULT '{}',
    outputs JSONB DEFAULT '{}',
    version VARCHAR(50) DEFAULT '1.0.0',
    status VARCHAR(50) NOT NULL CHECK (status IN ('draft', 'validated', 'policy-approved', 'deployed', 'failed')),
    validation_errors JSONB DEFAULT '[]',
    policy_violations JSONB DEFAULT '[]',
    cost_estimate DECIMAL(12, 2),
    created_by VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_iac_templates_project ON iac_templates(project_id);
CREATE INDEX idx_iac_templates_type ON iac_templates(template_type);
CREATE INDEX idx_iac_templates_status ON iac_templates(status);
```

### Policy Definitions Table
```sql
CREATE TABLE policy_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    policy_type VARCHAR(50) NOT NULL CHECK (policy_type IN ('security', 'compliance', 'cost', 'tagging', 'naming')),
    framework VARCHAR(100), -- 'CIS', 'SOC2', 'HIPAA', 'PCI-DSS', 'Custom'
    opa_rego_code TEXT NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),
    enabled BOOLEAN DEFAULT TRUE,
    target_csps VARCHAR(100)[], -- ['aws', 'azure', 'gcp']
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_policy_definitions_type ON policy_definitions(policy_type);
CREATE INDEX idx_policy_definitions_enabled ON policy_definitions(enabled);
```

### Validation Results Table
```sql
CREATE TABLE validation_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID NOT NULL REFERENCES iac_templates(id) ON DELETE CASCADE,
    validation_type VARCHAR(50) NOT NULL CHECK (validation_type IN ('syntax', 'policy', 'security', 'cost')),
    status VARCHAR(50) NOT NULL CHECK (status IN ('passed', 'failed', 'warning')),
    issues JSONB DEFAULT '[]',
    recommendations JSONB DEFAULT '[]',
    validated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_validation_results_template ON validation_results(template_id);
CREATE INDEX idx_validation_results_status ON validation_results(status);
```

### Cost Estimates Table
```sql
CREATE TABLE cost_estimates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID NOT NULL REFERENCES iac_templates(id) ON DELETE CASCADE,
    csp VARCHAR(20) NOT NULL,
    region VARCHAR(100) NOT NULL,
    resource_breakdown JSONB DEFAULT '{}', -- { "ec2": 1200, "rds": 800, ... }
    monthly_cost DECIMAL(12, 2) NOT NULL,
    annual_cost DECIMAL(12, 2) NOT NULL,
    confidence_level VARCHAR(20) CHECK (confidence_level IN ('high', 'medium', 'low')),
    cost_drivers JSONB DEFAULT '[]', -- Top 5 most expensive resources
    optimization_suggestions JSONB DEFAULT '[]',
    estimated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_cost_estimates_template ON cost_estimates(template_id);
```

---

## REST API Endpoints

### Template Management

#### 1. Generate IaC Template
**POST** `/api/iac-governance/projects/{project_id}/templates/generate`

**Request Body**:
```json
{
  "name": "Production Infrastructure",
  "description": "Terraform template for production environment",
  "template_type": "terraform",
  "target_csp": "aws",
  "discovery_source": {
    "type": "graph_query",
    "graph_query": "MATCH (vm:VirtualMachine) WHERE vm.environment = 'production' RETURN vm"
  },
  "options": {
    "enable_auto_scaling": true,
    "enable_high_availability": true,
    "enable_encryption": true,
    "enable_monitoring": true
  }
}
```

**Response**: `201 Created`
```json
{
  "id": "880e8400-e29b-41d4-a716-446655440003",
  "project_id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Production Infrastructure",
  "template_type": "terraform",
  "target_csp": "aws",
  "status": "draft",
  "template_content": "terraform {\n  required_version = \">= 1.0\"\n  required_providers {\n    aws = {\n      source  = \"hashicorp/aws\"\n      version = \"~> 5.0\"\n    }\n  }\n}\n\nresource \"aws_instance\" \"web_server\" {\n  ami           = var.ami_id\n  instance_type = \"t3.medium\"\n  ...",
  "variables": {
    "ami_id": {
      "type": "string",
      "description": "AMI ID for web server instances"
    },
    "region": {
      "type": "string",
      "default": "us-east-1"
    }
  },
  "created_at": "2025-01-09T15:00:00Z"
}
```

**Internal Logic**:
1. Query discovery data from Neo4j using provided graph query
2. Map discovered resources to IaC constructs
3. Invoke Terraform MCP adapter: `terraform_generate_module`
4. Inject best practices (encryption, monitoring, tagging)
5. Parameterize values as variables
6. Store template in database with `draft` status

#### 2. List IaC Templates
**GET** `/api/iac-governance/projects/{project_id}/templates`

**Query Parameters**:
- `template_type` (optional): Filter by type
- `status` (optional): Filter by status
- `target_csp` (optional): Filter by CSP

**Response**: `200 OK`
```json
{
  "templates": [
    {
      "id": "880e8400-e29b-41d4-a716-446655440003",
      "name": "Production Infrastructure",
      "template_type": "terraform",
      "target_csp": "aws",
      "status": "policy-approved",
      "cost_estimate": 4200.00,
      "created_at": "2025-01-09T15:00:00Z"
    }
  ],
  "total": 1
}
```

#### 3. Get Template Details
**GET** `/api/iac-governance/projects/{project_id}/templates/{template_id}`

**Response**: `200 OK`
```json
{
  "id": "880e8400-e29b-41d4-a716-446655440003",
  "project_id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Production Infrastructure",
  "template_type": "terraform",
  "target_csp": "aws",
  "template_content": "terraform { ... }",
  "variables": { ... },
  "outputs": { ... },
  "status": "policy-approved",
  "validation_summary": {
    "syntax": "passed",
    "security": "passed",
    "policy": "passed",
    "cost": "warning"
  },
  "cost_estimate": {
    "monthly": 4200.00,
    "annual": 50400.00,
    "top_cost_drivers": [
      { "resource": "aws_rds_cluster", "monthly_cost": 1800.00 },
      { "resource": "aws_instance", "monthly_cost": 1200.00 }
    ]
  }
}
```

#### 4. Update Template
**PUT** `/api/iac-governance/projects/{project_id}/templates/{template_id}`

**Request Body**:
```json
{
  "template_content": "terraform { ... updated content ... }",
  "variables": { ... }
}
```

**Response**: `200 OK`
```json
{
  "id": "880e8400-e29b-41d4-a716-446655440003",
  "status": "draft",
  "updated_at": "2025-01-09T16:00:00Z",
  "message": "Template updated. Re-validation required."
}
```

#### 5. Delete Template
**DELETE** `/api/iac-governance/projects/{project_id}/templates/{template_id}`

**Response**: `204 No Content`

---

### Policy Management

#### 6. Create Policy Definition
**POST** `/api/iac-governance/policies`

**Request Body**:
```json
{
  "name": "Require Encryption at Rest",
  "description": "All storage resources must have encryption enabled",
  "policy_type": "security",
  "framework": "CIS",
  "severity": "critical",
  "target_csps": ["aws", "azure", "gcp"],
  "opa_rego_code": "package terraform.security\n\ndeny[msg] {\n  resource := input.resource_changes[_]\n  resource.type == \"aws_ebs_volume\"\n  not resource.change.after.encrypted\n  msg := sprintf(\"EBS volume '%s' must have encryption enabled\", [resource.address])\n}"
}
```

**Response**: `201 Created`
```json
{
  "id": "990e8400-e29b-41d4-a716-446655440004",
  "name": "Require Encryption at Rest",
  "policy_type": "security",
  "severity": "critical",
  "enabled": true,
  "created_at": "2025-01-09T15:30:00Z"
}
```

#### 7. List Policies
**GET** `/api/iac-governance/policies`

**Query Parameters**:
- `policy_type` (optional): Filter by type
- `framework` (optional): Filter by framework
- `enabled` (optional): Filter by enabled status

**Response**: `200 OK`
```json
{
  "policies": [
    {
      "id": "990e8400-e29b-41d4-a716-446655440004",
      "name": "Require Encryption at Rest",
      "policy_type": "security",
      "framework": "CIS",
      "severity": "critical",
      "enabled": true
    }
  ],
  "total": 1
}
```

#### 8. Enable/Disable Policy
**PATCH** `/api/iac-governance/policies/{policy_id}`

**Request Body**:
```json
{
  "enabled": false
}
```

**Response**: `200 OK`
```json
{
  "id": "990e8400-e29b-41d4-a716-446655440004",
  "enabled": false,
  "updated_at": "2025-01-09T16:30:00Z"
}
```

---

### Validation & Enforcement

#### 9. Validate Template
**POST** `/api/iac-governance/projects/{project_id}/templates/{template_id}/validate`

**Request Body**:
```json
{
  "validation_types": ["syntax", "security", "policy", "cost"],
  "policy_filters": {
    "framework": "CIS",
    "severity_threshold": "high"
  }
}
```

**Response**: `200 OK`
```json
{
  "template_id": "880e8400-e29b-41d4-a716-446655440003",
  "validation_summary": {
    "syntax": {
      "status": "passed",
      "issues": []
    },
    "security": {
      "status": "failed",
      "issues": [
        {
          "severity": "critical",
          "resource": "aws_s3_bucket.data_lake",
          "message": "S3 bucket does not have encryption enabled",
          "recommendation": "Add server_side_encryption_configuration block"
        }
      ]
    },
    "policy": {
      "status": "passed",
      "violations": []
    },
    "cost": {
      "status": "warning",
      "message": "Estimated monthly cost ($4200) exceeds recommended budget ($3000)",
      "recommendations": [
        "Consider using t3.small instead of t3.medium for non-production instances",
        "Enable RDS Reserved Instances for 30% savings"
      ]
    }
  },
  "overall_status": "failed",
  "validated_at": "2025-01-09T16:45:00Z"
}
```

**Internal Logic**:
1. **Syntax Validation**: Invoke Terraform MCP `terraform_validate`
2. **Security Scanning**: Run OPA policies against template
3. **Policy Enforcement**: Check compliance policies (tagging, naming, etc.)
4. **Cost Validation**: Compare estimated cost against budget constraints

#### 10. Get Validation History
**GET** `/api/iac-governance/projects/{project_id}/templates/{template_id}/validations`

**Response**: `200 OK`
```json
{
  "validations": [
    {
      "id": "aa0e8400-e29b-41d4-a716-446655440005",
      "validation_type": "security",
      "status": "failed",
      "issues_count": 3,
      "validated_at": "2025-01-09T16:45:00Z"
    }
  ],
  "total": 1
}
```

---

### Cost Estimation

#### 11. Estimate Cost
**POST** `/api/iac-governance/projects/{project_id}/templates/{template_id}/estimate-cost`

**Request Body**:
```json
{
  "region": "us-east-1",
  "usage_assumptions": {
    "instance_hours_per_month": 730,
    "data_transfer_gb_per_month": 500,
    "rds_iops": 3000
  }
}
```

**Response**: `200 OK`
```json
{
  "template_id": "880e8400-e29b-41d4-a716-446655440003",
  "region": "us-east-1",
  "cost_breakdown": {
    "compute": {
      "aws_instance": {
        "count": 3,
        "instance_type": "t3.medium",
        "monthly_cost": 1200.00
      }
    },
    "database": {
      "aws_rds_cluster": {
        "engine": "postgres",
        "instance_class": "db.r5.large",
        "monthly_cost": 1800.00
      }
    },
    "storage": {
      "aws_ebs_volume": {
        "size_gb": 500,
        "monthly_cost": 50.00
      },
      "aws_s3_bucket": {
        "storage_gb": 1000,
        "monthly_cost": 23.00
      }
    },
    "networking": {
      "aws_vpc": { "monthly_cost": 0.00 },
      "aws_nat_gateway": { "monthly_cost": 45.00 },
      "data_transfer": { "monthly_cost": 45.00 }
    }
  },
  "total_monthly_cost": 4200.00,
  "total_annual_cost": 50400.00,
  "confidence_level": "high",
  "top_cost_drivers": [
    { "resource": "aws_rds_cluster", "percentage": 42.9, "monthly_cost": 1800.00 },
    { "resource": "aws_instance", "percentage": 28.6, "monthly_cost": 1200.00 },
    { "resource": "aws_ebs_volume", "percentage": 1.2, "monthly_cost": 50.00 }
  ],
  "optimization_suggestions": [
    {
      "resource": "aws_instance",
      "current_cost": 1200.00,
      "optimized_cost": 840.00,
      "savings": 360.00,
      "recommendation": "Use t3.small (2 vCPU, 2GB RAM) instead of t3.medium for dev instances"
    },
    {
      "resource": "aws_rds_cluster",
      "current_cost": 1800.00,
      "optimized_cost": 1260.00,
      "savings": 540.00,
      "recommendation": "Purchase 1-year Reserved Instance for 30% savings"
    }
  ],
  "estimated_at": "2025-01-09T17:00:00Z"
}
```

**Internal Logic**:
1. Parse IaC template to extract resource definitions
2. For each resource:
   - Query CSP pricing API (AWS Pricing, Azure Pricing, GCP Pricing)
   - Apply usage assumptions
   - Calculate monthly cost
3. Aggregate costs by category (compute, storage, networking, etc.)
4. Identify top 5 cost drivers
5. Generate optimization suggestions using right-sizing logic

#### 12. Compare Cost Scenarios
**POST** `/api/iac-governance/projects/{project_id}/templates/compare-costs`

**Request Body**:
```json
{
  "scenarios": [
    {
      "name": "AWS us-east-1",
      "template_id": "880e8400-e29b-41d4-a716-446655440003",
      "region": "us-east-1"
    },
    {
      "name": "AWS eu-west-1",
      "template_id": "880e8400-e29b-41d4-a716-446655440003",
      "region": "eu-west-1"
    },
    {
      "name": "Azure East US",
      "template_id": "bb0e8400-e29b-41d4-a716-446655440006",
      "region": "eastus"
    }
  ]
}
```

**Response**: `200 OK`
```json
{
  "scenarios": [
    {
      "name": "AWS us-east-1",
      "monthly_cost": 4200.00,
      "annual_cost": 50400.00
    },
    {
      "name": "AWS eu-west-1",
      "monthly_cost": 4500.00,
      "annual_cost": 54000.00
    },
    {
      "name": "Azure East US",
      "monthly_cost": 3900.00,
      "annual_cost": 46800.00
    }
  ],
  "recommendation": "Azure East US offers 7.1% cost savings compared to AWS us-east-1"
}
```

---

### GitOps Integration

#### 13. Generate CI/CD Pipeline
**POST** `/api/iac-governance/projects/{project_id}/templates/{template_id}/generate-pipeline`

**Request Body**:
```json
{
  "pipeline_type": "github-actions",
  "git_repository": "https://github.com/acme-corp/infrastructure",
  "branch": "main",
  "environment": "production",
  "auto_approve": false,
  "require_cost_approval": true
}
```

**Response**: `200 OK`
```json
{
  "pipeline_type": "github-actions",
  "workflow_file": ".github/workflows/terraform-deploy.yml",
  "workflow_content": "name: Terraform Deploy\n\non:\n  push:\n    branches: [main]\n  pull_request:\n    branches: [main]\n\njobs:\n  terraform:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v3\n      - name: Setup Terraform\n        uses: hashicorp/setup-terraform@v2\n      - name: Terraform Init\n        run: terraform init\n      - name: Terraform Plan\n        run: terraform plan -out=tfplan\n      - name: Policy Check\n        run: |\n          curl -X POST http://iac-governance:8013/api/iac-governance/validate \\\n            -H 'Content-Type: application/json' \\\n            -d '{\"template_id\": \"${{ env.TEMPLATE_ID }}\"}'\n      - name: Cost Estimation\n        run: |\n          curl -X POST http://iac-governance:8013/api/iac-governance/estimate-cost\n      - name: Terraform Apply\n        if: github.ref == 'refs/heads/main'\n        run: terraform apply -auto-approve tfplan\n",
  "setup_instructions": [
    "1. Create GitHub repository secret: AWS_ACCESS_KEY_ID",
    "2. Create GitHub repository secret: AWS_SECRET_ACCESS_KEY",
    "3. Commit .github/workflows/terraform-deploy.yml to repository",
    "4. Push to main branch to trigger deployment"
  ]
}
```

#### 14. Generate Azure DevOps Pipeline
**POST** `/api/iac-governance/projects/{project_id}/templates/{template_id}/generate-pipeline`

**Request Body**:
```json
{
  "pipeline_type": "azure-devops",
  "service_connection": "azure-production",
  "environment": "production"
}
```

**Response**: `200 OK`
```json
{
  "pipeline_type": "azure-devops",
  "pipeline_file": "azure-pipelines.yml",
  "pipeline_content": "trigger:\n  branches:\n    include:\n      - main\n\npool:\n  vmImage: 'ubuntu-latest'\n\nstages:\n  - stage: Validate\n    jobs:\n      - job: PolicyCheck\n        steps:\n          - task: Bash@3\n            inputs:\n              script: |\n                curl -X POST http://iac-governance:8013/api/iac-governance/validate\n  - stage: Deploy\n    jobs:\n      - deployment: Terraform\n        environment: production\n        strategy:\n          runOnce:\n            deploy:\n              steps:\n                - task: TerraformInstaller@0\n                - task: TerraformTaskV2@2\n                  inputs:\n                    command: 'init'\n                - task: TerraformTaskV2@2\n                  inputs:\n                    command: 'apply'\n"
}
```

---

### Drift Detection

#### 15. Detect Infrastructure Drift
**POST** `/api/iac-governance/projects/{project_id}/templates/{template_id}/detect-drift`

**Request Body**:
```json
{
  "state_file_url": "s3://terraform-state-bucket/production.tfstate",
  "credentials": {
    "aws_access_key_id": "...",
    "aws_secret_access_key": "..."
  }
}
```

**Response**: `200 OK`
```json
{
  "template_id": "880e8400-e29b-41d4-a716-446655440003",
  "drift_detected": true,
  "drifted_resources": [
    {
      "resource_type": "aws_instance",
      "resource_name": "web_server_1",
      "drift_type": "modification",
      "expected_value": {
        "instance_type": "t3.medium",
        "tags": { "Environment": "production" }
      },
      "actual_value": {
        "instance_type": "t3.large",
        "tags": { "Environment": "production", "Owner": "john.doe" }
      },
      "differences": [
        "instance_type changed from t3.medium to t3.large",
        "Tag 'Owner' added manually"
      ]
    }
  ],
  "remediation_options": [
    {
      "option": "revert_to_template",
      "description": "Update instance_type back to t3.medium and remove Owner tag",
      "terraform_command": "terraform apply -target=aws_instance.web_server_1"
    },
    {
      "option": "update_template",
      "description": "Update template to match current state",
      "recommendation": "Add Owner tag to template if intentional change"
    }
  ],
  "detected_at": "2025-01-09T18:00:00Z"
}
```

**Internal Logic**:
1. Download Terraform state file from S3/Azure Blob/GCS
2. Invoke Terraform MCP `terraform_show` to get current state
3. Query actual CSP resources using AWS/Azure/GCP APIs
4. Compare template definition vs actual state
5. Identify drifted resources
6. Generate remediation options

---

## MCP Adapter Interfaces

### Terraform MCP Adapter

```python
class TerraformMCPAdapter:
    """Adapter for Terraform MCP Server integration."""
    
    def __init__(self, mcp_server_url: str):
        self.mcp_server_url = mcp_server_url
    
    async def generate_module(
        self,
        resources: list[dict],
        module_name: str,
        provider: str
    ) -> str:
        """
        Generate Terraform module from resource definitions.
        
        MCP Tool: terraform_generate_module
        """
        pass
    
    async def validate(
        self,
        template_content: str
    ) -> dict:
        """
        Validate Terraform syntax.
        
        MCP Tool: terraform_validate
        """
        pass
    
    async def plan(
        self,
        template_content: str,
        variables: dict
    ) -> dict:
        """
        Run Terraform plan.
        
        MCP Tool: terraform_plan
        """
        pass
```

### OPA Engine Interface

```python
class OPAEngine:
    """Open Policy Agent integration for policy enforcement."""
    
    def __init__(self, opa_server_url: str):
        self.opa_server_url = opa_server_url
    
    async def evaluate_policies(
        self,
        template_content: str,
        policies: list[str]
    ) -> dict:
        """
        Evaluate IaC template against OPA policies.
        
        Returns:
        {
            "violations": [
                {
                    "policy_id": "...",
                    "severity": "critical",
                    "message": "...",
                    "resource": "..."
                }
            ],
            "passed": true/false
        }
        """
        pass
```

---

## Error Handling

### Error Response Format
```json
{
  "error": {
    "code": "POLICY_VIOLATION",
    "message": "Template validation failed due to policy violations",
    "details": {
      "template_id": "880e8400-e29b-41d4-a716-446655440003",
      "violations": [
        {
          "policy": "Require Encryption at Rest",
          "severity": "critical",
          "resource": "aws_s3_bucket.data_lake"
        }
      ]
    },
    "timestamp": "2025-01-09T17:30:00Z"
  }
}
```

### Error Codes
- `TEMPLATE_NOT_FOUND`: IaC template does not exist
- `POLICY_NOT_FOUND`: Policy definition does not exist
- `VALIDATION_FAILED`: Template syntax or validation failed
- `POLICY_VIOLATION`: Template violates one or more policies
- `COST_ESTIMATION_FAILED`: Unable to estimate cost
- `MCP_ADAPTER_ERROR`: Terraform/CloudFormation/Bicep MCP error
- `OPA_ENGINE_ERROR`: OPA policy evaluation failed
- `PRICING_API_ERROR`: CSP pricing API error
- `DRIFT_DETECTION_FAILED`: Unable to detect infrastructure drift

---

## Configuration

### Environment Variables
```bash
# Service Configuration
IAC_GOVERNANCE_PORT=8013
DATABASE_URL=postgresql://user:password@localhost:5432/ascent_db

# Terraform MCP Server
TERRAFORM_MCP_SERVER_URL=http://localhost:5103

# CloudFormation MCP Server
CLOUDFORMATION_MCP_SERVER_URL=http://localhost:5104

# Bicep MCP Server
BICEP_MCP_SERVER_URL=http://localhost:5105

# Open Policy Agent
OPA_SERVER_URL=http://localhost:8181

# AWS Pricing API
AWS_PRICING_REGION=us-east-1

# Azure Pricing API
AZURE_PRICING_ENDPOINT=https://prices.azure.com/api/retail/prices

# GCP Pricing API
GCP_BILLING_PROJECT_ID=<project_id>
```

---

## Testing Plan

### Unit Tests
- Template generation from discovery data
- OPA policy evaluation logic
- Cost calculation algorithms
- MCP adapter connection tests

### Integration Tests
- End-to-end template generation → validation → deployment flow
- Multi-policy enforcement tests
- Cost estimation accuracy tests
- GitOps pipeline generation tests

### Performance Tests
- Large template validation (10,000+ resources)
- Concurrent policy evaluations (100+ templates)
- Cost estimation performance (complex multi-cloud templates)

---

## Deployment

### Docker Compose (Development)
```yaml
services:
  iac-governance:
    build: ./services/iac-governance-service
    ports:
      - "8013:8013"
    environment:
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/ascent_db
      - TERRAFORM_MCP_SERVER_URL=http://terraform-mcp:5103
      - OPA_SERVER_URL=http://opa:8181
    depends_on:
      - postgres
      - terraform-mcp
      - opa
  
  opa:
    image: openpolicyagent/opa:latest
    ports:
      - "8181:8181"
    command: ["run", "--server", "--addr", "0.0.0.0:8181"]
```

### Kubernetes Helm Chart
```yaml
# values.yaml
iacGovernance:
  replicaCount: 2
  image:
    repository: ascent/iac-governance-service
    tag: "1.0.0"
  service:
    port: 8013
  env:
    TERRAFORM_MCP_SERVER_URL: "http://terraform-mcp:5103"
    OPA_SERVER_URL: "http://opa:8181"

opa:
  enabled: true
  image:
    repository: openpolicyagent/opa
    tag: "latest"
```

---

## Metrics & Monitoring

### Prometheus Metrics
- `iac_governance_templates_total{status}`: Total templates by status
- `iac_governance_validations_total{status}`: Validation count by status
- `iac_governance_policy_violations_total{severity}`: Policy violations by severity
- `iac_governance_cost_estimates_total`: Total cost estimates generated
- `iac_governance_template_generation_duration_seconds`: Template generation time

### Logging
- Structured JSON logs (INFO, WARNING, ERROR)
- Correlation ID tracking
- Policy evaluation audit logs
- Cost estimation detail logs

---

**Document Version**: 1.0  
**Last Updated**: January 9, 2025  
**Author**: IaC Governance Team
