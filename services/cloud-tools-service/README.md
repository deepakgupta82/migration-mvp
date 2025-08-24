# Cloud Tools Integration Service

This service provides native cloud tool integrations and migration assessment capabilities for the Nagarro Ascent Platform.

## Features

- **Multi-Cloud Support**: AWS, Azure, GCP integrations
- **Resource Discovery**: Automatic cloud resource discovery and inventory
- **Cost Analysis**: Monthly cost estimation and optimization recommendations
- **Migration Assessment**: Complexity scoring and migration pathway analysis
- **Real-time Monitoring**: WebSocket-based progress updates
- **Secure Credentials**: Encrypted credential management

## API Endpoints

### Health Check
- `GET /health` - Service health status

### Credential Management
- `POST /projects/{project_id}/credentials` - Add cloud credentials

### Assessment Management
- `POST /projects/{project_id}/assessments` - Start cloud assessment
- `GET /projects/{project_id}/assessments` - Get project assessments
- `GET /assessments/{assessment_id}` - Get specific assessment

### Resource Discovery
- `GET /projects/{project_id}/resources` - Get discovered resources
- `GET /projects/{project_id}/resources/summary` - Get resource summary

## Supported Cloud Providers

### AWS
- EC2 instances
- EBS volumes
- RDS databases
- S3 storage
- Lambda functions
- ECS/EKS containers

### Azure
- Virtual Machines
- Storage Accounts
- SQL Database
- App Services
- Container Instances

### Google Cloud Platform
- Compute Engine
- Cloud Storage
- Cloud SQL
- Cloud Functions
- GKE clusters

## Usage

### Adding Cloud Credentials

```python
import requests

credentials = {
    "provider": "aws",
    "access_key": "your-access-key",
    "secret_key": "your-secret-key",
    "region": "us-east-1"
}

response = requests.post(
    "http://localhost:8012/projects/my-project/credentials",
    json=credentials
)
```

### Starting Assessment

```python
assessment_request = {
    "provider": "aws"
}

response = requests.post(
    "http://localhost:8012/projects/my-project/assessments",
    json=assessment_request
)

assessment_id = response.json()["assessment_id"]
```

### Getting Results

```python
# Get assessment status
assessment = requests.get(f"http://localhost:8012/assessments/{assessment_id}")

# Get discovered resources
resources = requests.get("http://localhost:8012/projects/my-project/resources")
```

## Configuration

Environment Variables:

- `WEBSOCKET_SERVICE_URL`: WebSocket service URL (default: http://localhost:8009)
- `STORAGE_SERVICE_URL`: Storage service URL (default: http://localhost:8004)
- `AWS_REGION`: Default AWS region
- `AZURE_SUBSCRIPTION_ID`: Default Azure subscription
- `GCP_PROJECT_ID`: Default GCP project

## Security

- Credentials are encrypted at rest
- API authentication via service tokens
- Audit logging for all operations
- Role-based access control

## Assessment Output

Each assessment provides:

1. **Resource Inventory**: Complete list of discovered resources
2. **Cost Analysis**: Monthly cost breakdown by service
3. **Complexity Score**: Migration difficulty rating (0-100)
4. **Recommendations**: Specific migration suggestions
5. **Risk Assessment**: Potential migration risks and mitigations

## Integration

The service integrates with:

- **WebSocket Service**: Real-time progress updates
- **Storage Service**: Assessment report storage
- **Service Registry**: Health monitoring and discovery