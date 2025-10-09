# FinOps Optimization Service - API Contract

**Service Name**: finops-optimization-service  
**Port**: 8018  
**Version**: 1.0.0  
**Protocol**: HTTP/REST + WebSocket  
**Base URL**: `http://localhost:8018/api/finops`

---

## Overview

The FinOps Optimization Service provides continuous cost optimization, anomaly detection, right-sizing recommendations, and chargeback/showback capabilities for multi-cloud environments. It integrates with AWS Cost Explorer MCP, Azure Cost Management MCP, and GCP Cloud Billing API to provide unified financial operations across CSPs.

### Key Responsibilities
- Multi-cloud cost visibility and reporting
- Spend anomaly detection using ML algorithms
- Right-sizing recommendations (compute, storage, database)
- Reserved Instance/Savings Plan recommendations
- Cost allocation and chargeback
- Budget tracking and alerting
- TCO (Total Cost of Ownership) analysis

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│        FinOps Optimization Service (Port 8018)              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ AWS Cost     │  │ Azure Cost   │  │ GCP Billing  │     │
│  │ Explorer MCP │  │ Mgmt MCP     │  │ API          │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                  │                  │              │
│  ┌──────▼──────────────────▼──────────────────▼──────┐     │
│  │         Cost Data Aggregation Layer              │     │
│  │  - Unified cost model                             │     │
│  │  - Multi-cloud normalization                      │     │
│  │  - Historical data warehouse                      │     │
│  └──────────────────────────────────────────────────┘     │
│                                                              │
│  ┌──────────────────────────────────────────────────┐     │
│  │    Anomaly Detection Engine (ML)                  │     │
│  │  - Time-series forecasting                        │     │
│  │  - Outlier detection                              │     │
│  │  - Trend analysis                                 │     │
│  │  - Alert generation                               │     │
│  └──────────────────────────────────────────────────┘     │
│                                                              │
│  ┌──────────────────────────────────────────────────┐     │
│  │    Right-Sizing Recommendation Engine             │     │
│  │  - Compute utilization analysis                   │     │
│  │  - Storage optimization                           │     │
│  │  - Database right-sizing                          │     │
│  │  - RI/Savings Plan advisor                        │     │
│  └──────────────────────────────────────────────────┘     │
│                                                              │
│  ┌──────────────────────────────────────────────────┐     │
│  │    Cost Allocation & Chargeback                   │     │
│  │  - Tag-based allocation                           │     │
│  │  - Business unit mapping                          │     │
│  │  - Showback reports                               │     │
│  └──────────────────────────────────────────────────┘     │
│                                                              │
│  ┌──────────────────────────────────────────────────┐     │
│  │    State Manager (PostgreSQL + TimescaleDB)       │     │
│  │  - Cost time-series data                          │     │
│  │  - Budget definitions                             │     │
│  │  - Optimization recommendations                   │     │
│  │  - Anomaly alerts                                 │     │
│  └──────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### Cost Data Table (TimescaleDB Hypertable)
```sql
CREATE TABLE cost_data (
    timestamp TIMESTAMP NOT NULL,
    project_id UUID NOT NULL,
    csp VARCHAR(20) NOT NULL CHECK (csp IN ('aws', 'azure', 'gcp')),
    account_id VARCHAR(255) NOT NULL,
    service_name VARCHAR(255) NOT NULL,
    resource_id VARCHAR(500),
    region VARCHAR(100),
    usage_type VARCHAR(255),
    cost DECIMAL(12, 4) NOT NULL,
    currency VARCHAR(10) DEFAULT 'USD',
    tags JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}'
);

-- Convert to TimescaleDB hypertable for time-series optimization
SELECT create_hypertable('cost_data', 'timestamp');

CREATE INDEX idx_cost_data_project ON cost_data(project_id, timestamp DESC);
CREATE INDEX idx_cost_data_service ON cost_data(service_name, timestamp DESC);
CREATE INDEX idx_cost_data_tags ON cost_data USING GIN(tags);
```

### Budgets Table
```sql
CREATE TABLE budgets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    budget_type VARCHAR(50) NOT NULL CHECK (budget_type IN ('monthly', 'quarterly', 'annual', 'custom')),
    amount DECIMAL(12, 2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'USD',
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    alert_thresholds JSONB DEFAULT '{"warning": 80, "critical": 95}', -- Percentage thresholds
    filters JSONB DEFAULT '{}', -- { "csp": "aws", "service": "ec2", "tags": {...} }
    current_spend DECIMAL(12, 2) DEFAULT 0,
    forecast_spend DECIMAL(12, 2),
    status VARCHAR(50) NOT NULL CHECK (status IN ('active', 'exceeded', 'completed')),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_budgets_project ON budgets(project_id);
CREATE INDEX idx_budgets_status ON budgets(status);
```

### Optimization Recommendations Table
```sql
CREATE TABLE optimization_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    recommendation_type VARCHAR(100) NOT NULL CHECK (recommendation_type IN (
        'right-sizing', 'reserved-instance', 'savings-plan', 'storage-optimization', 
        'idle-resource', 'underutilized-resource', 'reserved-capacity'
    )),
    csp VARCHAR(20) NOT NULL,
    resource_id VARCHAR(500) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    current_configuration JSONB DEFAULT '{}',
    recommended_configuration JSONB DEFAULT '{}',
    current_monthly_cost DECIMAL(12, 2) NOT NULL,
    estimated_monthly_cost DECIMAL(12, 2) NOT NULL,
    monthly_savings DECIMAL(12, 2) NOT NULL,
    annual_savings DECIMAL(12, 2) NOT NULL,
    confidence_score DECIMAL(3, 2) CHECK (confidence_score BETWEEN 0 AND 1),
    implementation_effort VARCHAR(20) CHECK (implementation_effort IN ('low', 'medium', 'high')),
    risk_level VARCHAR(20) CHECK (risk_level IN ('low', 'medium', 'high')),
    status VARCHAR(50) NOT NULL CHECK (status IN ('pending', 'approved', 'rejected', 'implemented', 'expired')),
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_recommendations_project ON optimization_recommendations(project_id);
CREATE INDEX idx_recommendations_type ON optimization_recommendations(recommendation_type);
CREATE INDEX idx_recommendations_status ON optimization_recommendations(status);
```

### Anomaly Alerts Table
```sql
CREATE TABLE anomaly_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    alert_type VARCHAR(50) NOT NULL CHECK (alert_type IN ('spike', 'trend', 'forecast-breach', 'budget-breach')),
    csp VARCHAR(20) NOT NULL,
    service_name VARCHAR(255),
    resource_id VARCHAR(500),
    detected_at TIMESTAMP NOT NULL,
    baseline_cost DECIMAL(12, 2) NOT NULL,
    actual_cost DECIMAL(12, 2) NOT NULL,
    deviation_percentage DECIMAL(5, 2) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    message TEXT NOT NULL,
    root_cause_analysis JSONB DEFAULT '{}',
    status VARCHAR(50) NOT NULL CHECK (status IN ('open', 'acknowledged', 'resolved', 'false-positive')),
    acknowledged_by VARCHAR(255),
    acknowledged_at TIMESTAMP,
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_anomaly_alerts_project ON anomaly_alerts(project_id);
CREATE INDEX idx_anomaly_alerts_status ON anomaly_alerts(status);
CREATE INDEX idx_anomaly_alerts_detected ON anomaly_alerts(detected_at DESC);
```

### Cost Allocation Rules Table
```sql
CREATE TABLE cost_allocation_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    rule_type VARCHAR(50) NOT NULL CHECK (rule_type IN ('tag-based', 'service-based', 'account-based', 'custom')),
    allocation_logic JSONB NOT NULL, -- { "tag_key": "BusinessUnit", "mappings": {...} }
    business_units JSONB DEFAULT '[]', -- List of business units
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_allocation_rules_project ON cost_allocation_rules(project_id);
```

---

## REST API Endpoints

### Cost Visibility

#### 1. Get Cost Summary
**GET** `/api/finops/projects/{project_id}/costs/summary`

**Query Parameters**:
- `start_date` (required): Start date (ISO 8601)
- `end_date` (required): End date (ISO 8601)
- `granularity` (optional): `daily`, `weekly`, `monthly` (default: `daily`)
- `group_by` (optional): `csp`, `service`, `region`, `tag` (default: `csp`)

**Response**: `200 OK`
```json
{
  "project_id": "123e4567-e89b-12d3-a456-426614174000",
  "period": {
    "start_date": "2025-01-01",
    "end_date": "2025-01-09"
  },
  "total_cost": 15600.00,
  "currency": "USD",
  "cost_by_csp": [
    {
      "csp": "aws",
      "cost": 9200.00,
      "percentage": 59.0
    },
    {
      "csp": "azure",
      "cost": 4800.00,
      "percentage": 30.8
    },
    {
      "csp": "gcp",
      "cost": 1600.00,
      "percentage": 10.3
    }
  ],
  "cost_by_service": [
    {
      "service": "EC2",
      "csp": "aws",
      "cost": 3600.00
    },
    {
      "service": "RDS",
      "csp": "aws",
      "cost": 2400.00
    },
    {
      "service": "Virtual Machines",
      "csp": "azure",
      "cost": 2200.00
    }
  ],
  "trend": "increasing",
  "trend_percentage": 12.5
}
```

#### 2. Get Cost Trends
**GET** `/api/finops/projects/{project_id}/costs/trends`

**Query Parameters**:
- `start_date` (required): Start date
- `end_date` (required): End date
- `granularity` (required): `daily`, `weekly`, `monthly`
- `csp` (optional): Filter by CSP
- `service` (optional): Filter by service

**Response**: `200 OK`
```json
{
  "project_id": "123e4567-e89b-12d3-a456-426614174000",
  "granularity": "daily",
  "data_points": [
    {
      "date": "2025-01-01",
      "cost": 1800.00,
      "forecast": null
    },
    {
      "date": "2025-01-02",
      "cost": 1750.00,
      "forecast": null
    },
    {
      "date": "2025-01-03",
      "cost": 1900.00,
      "forecast": null
    },
    {
      "date": "2025-01-04",
      "cost": 1850.00,
      "forecast": null
    },
    {
      "date": "2025-01-05",
      "cost": 2000.00,
      "forecast": null
    },
    {
      "date": "2025-01-06",
      "cost": null,
      "forecast": 1950.00
    },
    {
      "date": "2025-01-07",
      "cost": null,
      "forecast": 2050.00
    }
  ],
  "forecast_confidence": "high"
}
```

#### 3. Get Cost Breakdown
**GET** `/api/finops/projects/{project_id}/costs/breakdown`

**Query Parameters**:
- `start_date` (required)
- `end_date` (required)
- `dimension` (required): `service`, `region`, `tag`, `resource`

**Response**: `200 OK`
```json
{
  "dimension": "service",
  "breakdown": [
    {
      "name": "EC2",
      "csp": "aws",
      "cost": 3600.00,
      "percentage": 23.1,
      "resources": [
        {
          "resource_id": "i-0abc123def456789",
          "cost": 800.00,
          "usage_hours": 720
        }
      ]
    }
  ]
}
```

---

### Budget Management

#### 4. Create Budget
**POST** `/api/finops/projects/{project_id}/budgets`

**Request Body**:
```json
{
  "name": "Q1 2025 AWS Production Budget",
  "description": "Budget for AWS production environment",
  "budget_type": "quarterly",
  "amount": 30000.00,
  "currency": "USD",
  "start_date": "2025-01-01",
  "end_date": "2025-03-31",
  "alert_thresholds": {
    "warning": 80,
    "critical": 95
  },
  "filters": {
    "csp": "aws",
    "tags": {
      "Environment": "production"
    }
  }
}
```

**Response**: `201 Created`
```json
{
  "id": "cc0e8400-e29b-41d4-a716-446655440007",
  "project_id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Q1 2025 AWS Production Budget",
  "budget_type": "quarterly",
  "amount": 30000.00,
  "current_spend": 0.00,
  "forecast_spend": null,
  "status": "active",
  "created_at": "2025-01-09T18:00:00Z"
}
```

#### 5. List Budgets
**GET** `/api/finops/projects/{project_id}/budgets`

**Query Parameters**:
- `status` (optional): Filter by status

**Response**: `200 OK`
```json
{
  "budgets": [
    {
      "id": "cc0e8400-e29b-41d4-a716-446655440007",
      "name": "Q1 2025 AWS Production Budget",
      "amount": 30000.00,
      "current_spend": 9200.00,
      "spend_percentage": 30.7,
      "forecast_spend": 27600.00,
      "forecast_percentage": 92.0,
      "status": "active",
      "days_remaining": 82
    }
  ],
  "total": 1
}
```

#### 6. Get Budget Details
**GET** `/api/finops/projects/{project_id}/budgets/{budget_id}`

**Response**: `200 OK`
```json
{
  "id": "cc0e8400-e29b-41d4-a716-446655440007",
  "project_id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Q1 2025 AWS Production Budget",
  "amount": 30000.00,
  "current_spend": 9200.00,
  "spend_percentage": 30.7,
  "forecast_spend": 27600.00,
  "forecast_percentage": 92.0,
  "alert_history": [
    {
      "threshold": "warning",
      "triggered_at": "2025-01-05T10:00:00Z",
      "spend_at_trigger": 24000.00
    }
  ],
  "spending_by_day": [
    { "date": "2025-01-01", "cost": 300.00 },
    { "date": "2025-01-02", "cost": 320.00 }
  ]
}
```

---

### Anomaly Detection

#### 7. Get Anomaly Alerts
**GET** `/api/finops/projects/{project_id}/anomalies`

**Query Parameters**:
- `status` (optional): Filter by status
- `severity` (optional): Filter by severity
- `start_date` (optional): Start date
- `end_date` (optional): End date

**Response**: `200 OK`
```json
{
  "anomalies": [
    {
      "id": "dd0e8400-e29b-41d4-a716-446655440008",
      "alert_type": "spike",
      "csp": "aws",
      "service_name": "EC2",
      "detected_at": "2025-01-08T14:00:00Z",
      "baseline_cost": 800.00,
      "actual_cost": 2400.00,
      "deviation_percentage": 200.0,
      "severity": "critical",
      "message": "EC2 costs spiked by 200% compared to baseline",
      "status": "open"
    }
  ],
  "total": 1
}
```

#### 8. Acknowledge Anomaly
**PATCH** `/api/finops/projects/{project_id}/anomalies/{anomaly_id}`

**Request Body**:
```json
{
  "status": "acknowledged",
  "acknowledged_by": "john.doe@example.com",
  "notes": "Investigating increased EC2 usage due to batch processing job"
}
```

**Response**: `200 OK`
```json
{
  "id": "dd0e8400-e29b-41d4-a716-446655440008",
  "status": "acknowledged",
  "acknowledged_by": "john.doe@example.com",
  "acknowledged_at": "2025-01-09T18:30:00Z"
}
```

#### 9. Run Anomaly Detection
**POST** `/api/finops/projects/{project_id}/anomalies/detect`

**Request Body**:
```json
{
  "detection_window": "last_7_days",
  "sensitivity": "medium",
  "filters": {
    "csp": "aws"
  }
}
```

**Response**: `202 Accepted`
```json
{
  "message": "Anomaly detection job started",
  "job_id": "ee0e8400-e29b-41d4-a716-446655440009",
  "estimated_completion": "2025-01-09T18:45:00Z"
}
```

---

### Optimization Recommendations

#### 10. Get Optimization Recommendations
**GET** `/api/finops/projects/{project_id}/recommendations`

**Query Parameters**:
- `recommendation_type` (optional): Filter by type
- `csp` (optional): Filter by CSP
- `status` (optional): Filter by status
- `min_savings` (optional): Minimum monthly savings threshold

**Response**: `200 OK`
```json
{
  "recommendations": [
    {
      "id": "ff0e8400-e29b-41d4-a716-446655440010",
      "recommendation_type": "right-sizing",
      "csp": "aws",
      "resource_id": "i-0abc123def456789",
      "resource_type": "ec2_instance",
      "current_configuration": {
        "instance_type": "m5.xlarge",
        "vcpu": 4,
        "memory_gb": 16
      },
      "recommended_configuration": {
        "instance_type": "m5.large",
        "vcpu": 2,
        "memory_gb": 8
      },
      "current_monthly_cost": 140.00,
      "estimated_monthly_cost": 70.00,
      "monthly_savings": 70.00,
      "annual_savings": 840.00,
      "confidence_score": 0.92,
      "implementation_effort": "low",
      "risk_level": "low",
      "status": "pending"
    }
  ],
  "total": 1,
  "total_potential_monthly_savings": 70.00,
  "total_potential_annual_savings": 840.00
}
```

#### 11. Get Recommendation Details
**GET** `/api/finops/projects/{project_id}/recommendations/{recommendation_id}`

**Response**: `200 OK`
```json
{
  "id": "ff0e8400-e29b-41d4-a716-446655440010",
  "recommendation_type": "right-sizing",
  "resource_id": "i-0abc123def456789",
  "utilization_data": {
    "cpu_avg": 15.2,
    "cpu_max": 35.0,
    "memory_avg": 25.5,
    "memory_max": 42.0,
    "observation_period_days": 30
  },
  "rationale": "Instance is significantly over-provisioned. CPU utilization averages 15% and memory 25% over the past 30 days.",
  "implementation_steps": [
    "1. Create AMI snapshot of current instance",
    "2. Stop instance i-0abc123def456789",
    "3. Change instance type to m5.large",
    "4. Start instance and verify application functionality",
    "5. Monitor performance for 24 hours"
  ]
}
```

#### 12. Update Recommendation Status
**PATCH** `/api/finops/projects/{project_id}/recommendations/{recommendation_id}`

**Request Body**:
```json
{
  "status": "approved",
  "notes": "Approved for implementation during next maintenance window"
}
```

**Response**: `200 OK`
```json
{
  "id": "ff0e8400-e29b-41d4-a716-446655440010",
  "status": "approved",
  "updated_at": "2025-01-09T19:00:00Z"
}
```

#### 13. Generate Recommendations
**POST** `/api/finops/projects/{project_id}/recommendations/generate`

**Request Body**:
```json
{
  "recommendation_types": ["right-sizing", "reserved-instance", "idle-resource"],
  "csps": ["aws", "azure"],
  "lookback_period_days": 30
}
```

**Response**: `202 Accepted`
```json
{
  "message": "Recommendation generation job started",
  "job_id": "000e8400-e29b-41d4-a716-446655440011",
  "estimated_completion": "2025-01-09T19:15:00Z"
}
```

---

### Cost Allocation & Chargeback

#### 14. Get Cost Allocation Report
**GET** `/api/finops/projects/{project_id}/allocation/report`

**Query Parameters**:
- `start_date` (required)
- `end_date` (required)
- `allocation_dimension` (required): `business_unit`, `team`, `environment`

**Response**: `200 OK`
```json
{
  "allocation_dimension": "business_unit",
  "allocations": [
    {
      "business_unit": "Engineering",
      "total_cost": 8200.00,
      "percentage": 52.6,
      "cost_by_service": [
        { "service": "EC2", "cost": 3600.00 },
        { "service": "RDS", "cost": 2400.00 }
      ]
    },
    {
      "business_unit": "Data Analytics",
      "total_cost": 4800.00,
      "percentage": 30.8,
      "cost_by_service": [
        { "service": "EMR", "cost": 2200.00 },
        { "service": "S3", "cost": 1400.00 }
      ]
    },
    {
      "business_unit": "Unallocated",
      "total_cost": 2600.00,
      "percentage": 16.7
    }
  ],
  "total_cost": 15600.00
}
```

#### 15. Create Allocation Rule
**POST** `/api/finops/projects/{project_id}/allocation/rules`

**Request Body**:
```json
{
  "name": "Tag-based Business Unit Allocation",
  "description": "Allocate costs based on BusinessUnit tag",
  "rule_type": "tag-based",
  "allocation_logic": {
    "tag_key": "BusinessUnit",
    "mappings": {
      "eng": "Engineering",
      "data": "Data Analytics",
      "ops": "Operations"
    },
    "unallocated_behavior": "separate_bucket"
  },
  "business_units": ["Engineering", "Data Analytics", "Operations"]
}
```

**Response**: `201 Created`
```json
{
  "id": "110e8400-e29b-41d4-a716-446655440012",
  "name": "Tag-based Business Unit Allocation",
  "rule_type": "tag-based",
  "enabled": true,
  "created_at": "2025-01-09T19:30:00Z"
}
```

---

### TCO Analysis

#### 16. Get TCO Comparison
**POST** `/api/finops/projects/{project_id}/tco/compare`

**Request Body**:
```json
{
  "scenarios": [
    {
      "name": "Current On-Premises",
      "infrastructure_type": "on-premises",
      "hardware_costs": 50000.00,
      "software_licenses": 15000.00,
      "datacenter_costs": 8000.00,
      "personnel_costs": 120000.00,
      "period_years": 3
    },
    {
      "name": "AWS Cloud Migration",
      "infrastructure_type": "aws",
      "monthly_compute": 4200.00,
      "monthly_storage": 800.00,
      "monthly_networking": 600.00,
      "migration_costs": 25000.00,
      "period_years": 3
    }
  ]
}
```

**Response**: `200 OK`
```json
{
  "scenarios": [
    {
      "name": "Current On-Premises",
      "total_3yr_cost": 579000.00,
      "breakdown": {
        "hardware": 50000.00,
        "software": 45000.00,
        "datacenter": 24000.00,
        "personnel": 360000.00,
        "depreciation": 100000.00
      }
    },
    {
      "name": "AWS Cloud Migration",
      "total_3yr_cost": 431200.00,
      "breakdown": {
        "migration": 25000.00,
        "compute": 151200.00,
        "storage": 28800.00,
        "networking": 21600.00,
        "support": 50000.00,
        "personnel": 154600.00
      }
    }
  ],
  "recommendation": "AWS Cloud Migration offers 25.5% TCO savings ($147,800) over 3 years",
  "payback_period_months": 18
}
```

---

## WebSocket Events

### Connection
**URL**: `ws://localhost:8018/ws/finops/projects/{project_id}`

**Authentication**: JWT token in query parameter `?token=<jwt_token>`

### Event Types

#### 1. Budget Alert
```json
{
  "event_type": "budget.alert",
  "timestamp": "2025-01-09T20:00:00Z",
  "data": {
    "budget_id": "cc0e8400-e29b-41d4-a716-446655440007",
    "budget_name": "Q1 2025 AWS Production Budget",
    "threshold": "warning",
    "threshold_percentage": 80,
    "current_spend": 24000.00,
    "budget_amount": 30000.00
  }
}
```

#### 2. Anomaly Detected
```json
{
  "event_type": "anomaly.detected",
  "timestamp": "2025-01-09T20:05:00Z",
  "data": {
    "anomaly_id": "dd0e8400-e29b-41d4-a716-446655440008",
    "alert_type": "spike",
    "severity": "critical",
    "service_name": "EC2",
    "deviation_percentage": 200.0,
    "message": "EC2 costs spiked by 200%"
  }
}
```

#### 3. Recommendation Generated
```json
{
  "event_type": "recommendation.generated",
  "timestamp": "2025-01-09T20:10:00Z",
  "data": {
    "recommendation_id": "ff0e8400-e29b-41d4-a716-446655440010",
    "recommendation_type": "right-sizing",
    "monthly_savings": 70.00,
    "annual_savings": 840.00
  }
}
```

---

## MCP Adapter Interfaces

### AWS Cost Explorer MCP Adapter

```python
class AWSCostExplorerMCPAdapter:
    """Adapter for AWS Cost Explorer MCP integration."""
    
    def __init__(self, mcp_server_url: str, aws_credentials: dict):
        self.mcp_server_url = mcp_server_url
        self.credentials = aws_credentials
    
    async def get_cost_and_usage(
        self,
        start_date: str,
        end_date: str,
        granularity: str,
        group_by: list[str]
    ) -> dict:
        """
        Get AWS cost and usage data.
        
        MCP Tool: aws_cost_explorer_get_cost_and_usage
        """
        pass
    
    async def get_savings_plan_recommendations(
        self,
        lookback_period: str
    ) -> dict:
        """
        Get AWS Savings Plan recommendations.
        
        MCP Tool: aws_cost_explorer_get_savings_plans_purchase_recommendation
        """
        pass
```

### Azure Cost Management MCP Adapter

```python
class AzureCostManagementMCPAdapter:
    """Adapter for Azure Cost Management MCP integration."""
    
    def __init__(self, mcp_server_url: str, azure_credentials: dict):
        self.mcp_server_url = mcp_server_url
        self.credentials = azure_credentials
    
    async def get_costs(
        self,
        subscription_id: str,
        start_date: str,
        end_date: str,
        granularity: str
    ) -> dict:
        """
        Get Azure cost data.
        
        MCP Tool: azure_cost_management_query
        """
        pass
```

---

## Error Handling

### Error Codes
- `BUDGET_NOT_FOUND`: Budget does not exist
- `ANOMALY_NOT_FOUND`: Anomaly alert does not exist
- `RECOMMENDATION_NOT_FOUND`: Recommendation does not exist
- `COST_DATA_UNAVAILABLE`: Cost data not available for requested period
- `MCP_ADAPTER_ERROR`: Cost API MCP error
- `FORECASTING_FAILED`: Unable to generate cost forecast
- `ALLOCATION_RULE_ERROR`: Cost allocation rule error

---

## Configuration

### Environment Variables
```bash
# Service Configuration
FINOPS_PORT=8018
DATABASE_URL=postgresql://user:password@localhost:5432/ascent_db

# AWS Cost Explorer MCP
AWS_COST_EXPLORER_MCP_URL=http://localhost:5106
AWS_ACCESS_KEY_ID=<aws_key>
AWS_SECRET_ACCESS_KEY=<aws_secret>

# Azure Cost Management MCP
AZURE_COST_MGMT_MCP_URL=http://localhost:5107
AZURE_TENANT_ID=<tenant_id>
AZURE_CLIENT_ID=<client_id>
AZURE_CLIENT_SECRET=<client_secret>

# GCP Cloud Billing API
GCP_BILLING_API_URL=https://cloudbilling.googleapis.com/v1
GCP_SERVICE_ACCOUNT_KEY=<base64_key>

# ML Model Configuration
ANOMALY_DETECTION_MODEL=prophet
FORECAST_HORIZON_DAYS=30
CONFIDENCE_INTERVAL=0.95
```

---

## Metrics & Monitoring

### Prometheus Metrics
- `finops_total_cost{csp, service}`: Total cost by CSP/service
- `finops_budgets_total{status}`: Total budgets by status
- `finops_anomalies_total{severity}`: Total anomalies by severity
- `finops_recommendations_total{type}`: Total recommendations by type
- `finops_potential_savings`: Total potential savings from recommendations

---

**Document Version**: 1.0  
**Last Updated**: January 9, 2025  
**Author**: FinOps Optimization Team
