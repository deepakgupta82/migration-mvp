# Cloud Tools Service

## Service Overview

The Cloud Tools Service is a cloud integration and assessment service that operates on port 8012. It provides native cloud tool integrations for AWS, Azure, and GCP, enabling resource discovery, cost analysis, migration assessment, and real-time cloud environment monitoring.

### Key Features

- **Multi-Cloud Support**: AWS, Azure, GCP integrations
- **Resource Discovery**: Automated cloud resource inventory
- **Cost Analysis**: Cloud cost optimization and reporting
- **Migration Assessment**: Migration complexity analysis
- **Real-time Monitoring**: Live cloud environment monitoring
- **Assessment Reports**: Comprehensive migration reports
- **WebSocket Notifications**: Real-time assessment updates

## Functionality

### Core Capabilities

1. **Cloud Resource Discovery**
   - Automated resource scanning across cloud providers
   - Resource metadata collection and analysis
   - Dependency mapping and relationship identification
   - Resource tagging and categorization

2. **Cost Analysis and Optimization**
   - Cost monitoring and reporting
   - Optimization recommendations
   - Reserved instance analysis
   - Cost allocation and chargeback

3. **Migration Assessment**
   - Migration complexity scoring
   - Dependency analysis
   - Risk assessment and mitigation strategies
   - Timeline and effort estimation

4. **Real-time Monitoring**
   - Cloud resource status monitoring
   - Performance metrics collection
   - Alert generation and notification
   - Health check automation

### Dependencies

- **Cloud Provider APIs**: AWS SDK, Azure SDK, GCP SDK
- **WebSocket Service**: Real-time notification delivery
- **Storage Service**: Assessment report storage
- **Stats Service**: Usage statistics tracking

## APIs/Endpoints

### Cloud Credentials Management
- `POST /projects/{project_id}/credentials` - Add cloud credentials
- `PUT /projects/{project_id}/credentials` - Update credentials
- `DELETE /projects/{project_id}/credentials` - Remove credentials

### Assessment Operations
- `POST /projects/{project_id}/assessments` - Start cloud assessment
- `GET /projects/{project_id}/assessments` - List project assessments
- `GET /assessments/{assessment_id}` - Get assessment details

### Resource Operations
- `GET /projects/{project_id}/resources` - Get discovered resources
- `GET /projects/{project_id}/resources/summary` - Get resource summary

### Cost Analysis
- `GET /projects/{project_id}/costs` - Get cost analysis
- `POST /projects/{project_id}/cost-optimization` - Generate optimization recommendations

## Data Models

### Cloud Credentials Structure
```json
{
  "provider": "aws",
  "access_key": "AKIA...",
  "secret_key": "secret...",
  "region": "us-east-1",
  "account_id": "123456789012"
}
```

### Assessment Report Structure
```json
{
  "assessment_id": "assessment_123",
  "project_id": "project_456",
  "provider": "aws",
  "status": "completed",
  "resources_discovered": 150,
  "total_monthly_cost": 2500.00,
  "migration_complexity_score": 7.5,
  "recommendations": [
    "Consider container migration for compute resources",
    "Implement storage tiering strategy"
  ],
  "created_at": "2024-01-01T10:00:00.000000",
  "completed_at": "2024-01-01T10:30:00.000000"
}
```

### Cloud Resource Structure
```json
{
  "resource_id": "i-1234567890abcdef0",
  "name": "web-server-prod",
  "resource_type": "compute",
  "provider": "aws",
  "region": "us-east-1",
  "tags": {
    "Environment": "production",
    "Application": "web"
  },
  "properties": {
    "instance_type": "t3.medium",
    "state": "running"
  },
  "cost_monthly": 45.60,
  "migration_complexity": "medium",
  "migration_recommendations": [
    "Consider container migration",
    "Evaluate serverless options"
  ],
  "last_assessed": "2024-01-01T10:00:00.000000"
}
```

## Key Components

### CloudToolsManager (`main.py`)

**Core cloud integration engine**

- **Responsibilities**:
  - Cloud provider API interactions
  - Resource discovery and assessment
  - Cost analysis and optimization
  - Assessment report generation

### Assessment Processing

**Background assessment execution**

- **Responsibilities**:
  - Asynchronous assessment execution
  - Progress tracking and updates
  - Error handling and recovery
  - Result aggregation and reporting

## Data Flow

### Cloud Assessment Flow

1. **Credential Setup**: Cloud credentials configured for project
2. **Assessment Initiation**: Assessment started via API
3. **Resource Discovery**: Cloud resources scanned and inventoried
4. **Cost Analysis**: Resource costs calculated and analyzed
5. **Complexity Assessment**: Migration complexity evaluated
6. **Report Generation**: Comprehensive assessment report created
7. **Notification**: Results delivered via WebSocket

### Resource Monitoring Flow

1. **Monitoring Setup**: Monitoring parameters configured
2. **Data Collection**: Cloud metrics collected periodically
3. **Analysis**: Performance and cost analysis performed
4. **Alert Generation**: Threshold-based alerts triggered
5. **Notification**: Real-time updates sent to clients

## Complete Working Details

### Configuration

**Environment Variables**:
- `CLOUD_ASSESSMENT_TIMEOUT`: Assessment timeout in seconds
- `CLOUD_MAX_RESOURCES`: Maximum resources per assessment
- `CLOUD_COST_CACHE_TTL`: Cost data cache TTL

### Supported Cloud Providers

- **AWS**: EC2, S3, RDS, Lambda, etc.
- **Azure**: VMs, Storage, SQL Database, Functions, etc.
- **GCP**: Compute Engine, Cloud Storage, Cloud SQL, Cloud Functions, etc.

### Performance Characteristics

- **Assessment Time**: 2-10 minutes depending on resource count
- **Concurrent Assessments**: Limited by cloud API rate limits
- **Data Freshness**: Real-time data with caching
- **Scalability**: Horizontal scaling for multiple assessments

### Error Handling

- **API Failures**: Retry logic with exponential backoff
- **Authentication Errors**: Clear error messages and recovery steps
- **Rate Limiting**: Respectful API rate limit handling
- **Partial Failures**: Continue assessment with available data

### Monitoring and Observability

- **Assessment Metrics**: Success rates, execution times
- **Resource Statistics**: Discovered resources and costs
- **API Usage**: Cloud provider API call tracking
- **Error Analytics**: Failure patterns and resolutions

### Security Considerations

- **Credential Management**: Secure credential storage and handling
- **Access Scoping**: Minimal required permissions
- **Data Privacy**: Sensitive data handling and masking
- **Audit Logging**: All cloud operations logged

### Scaling Considerations

- **API Rate Limits**: Respectful concurrent request management
- **Caching**: Assessment result caching for performance
- **Parallel Processing**: Concurrent resource discovery
- **Load Distribution**: Assessment distribution across instances