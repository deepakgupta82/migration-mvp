# Analytics Service

## Service Overview

The Analytics Service is an advanced analytics and insights service that operates on port 8014. It provides comprehensive data analysis, reporting, and business intelligence capabilities for the Nagarro Ascent platform, including document analysis results storage and retrieval.

### Key Features

- **Document Analysis**: Advanced document processing analytics
- **Business Intelligence**: Comprehensive reporting and dashboards
- **Data Aggregation**: Multi-source data analysis and correlation
- **Real-time Analytics**: Live data processing and insights
- **Custom Reports**: Configurable reporting and visualization
- **Performance Monitoring**: System and user analytics
- **Trend Analysis**: Historical data analysis and forecasting

## Functionality

### Core Capabilities

1. **Document Analysis Processing**
   - Analysis result storage and versioning
   - Batch processing and result aggregation
   - Quality metrics and validation
   - Analysis pipeline monitoring

2. **Business Analytics**
   - User behavior analysis
   - System performance metrics
   - Usage patterns and trends
   - ROI and efficiency analysis

3. **Reporting Engine**
   - Custom report generation
   - Scheduled report delivery
   - Multi-format export (PDF, Excel, JSON)
   - Dashboard creation and sharing

4. **Real-time Monitoring**
   - Live metrics streaming
   - Alert generation and notification
   - Performance threshold monitoring
   - Anomaly detection

### Dependencies

- **PostgreSQL**: Analytics data storage
- **Redis**: Real-time data caching
- **WebSocket Service**: Real-time data streaming
- **Stats Service**: Platform statistics integration

## APIs/Endpoints

### Document Analysis
- `POST /api/documents/analysis/results/version` - Create analysis version
- `GET /api/documents/analysis/results/version/{version_id}/batches` - List version batches
- `POST /api/documents/analysis/results/batch` - Create analysis batch
- `GET /api/documents/analysis/results/batch/{batch_id}` - Get batch details
- `GET /api/documents/analysis/results/batch/{batch_id}/results` - List batch results
- `POST /api/analysis` - Create analysis result
- `PUT /api/analysis/{result_id}` - Update analysis result
- `DELETE /api/analysis/{result_id}` - Delete analysis result

### Analytics Operations
- `GET /api/analytics/dashboard` - Get analytics dashboard
- `POST /api/analytics/reports` - Generate custom reports
- `GET /api/analytics/metrics/{metric_name}` - Get specific metrics
- `POST /api/analytics/alerts` - Configure alerts

## Data Models

### Analysis Version Structure
```json
{
  "version_id": "ver_123",
  "description": "Q4 2024 Document Analysis",
  "created_at": "2024-01-01T00:00:00.000000",
  "updated_at": "2024-01-01T00:00:00.000000"
}
```

### Analysis Batch Structure
```json
{
  "batch_id": "batch_456",
  "version_id": "ver_123",
  "status": "completed",
  "created_at": "2024-01-01T00:00:00.000000",
  "updated_at": "2024-01-01T12:00:00.000000",
  "results": [...]
}
```

### Analysis Result Structure
```json
{
  "result_id": "res_789",
  "batch_id": "batch_456",
  "content": "Analysis result content...",
  "metadata": {
    "document_id": "doc_101",
    "analysis_type": "sentiment",
    "confidence": 0.95
  },
  "status": "completed",
  "created_at": "2024-01-01T12:00:00.000000",
  "updated_at": "2024-01-01T12:05:00.000000"
}
```

## Key Components

### Analytics Engine

**Core analytics processing**

- **Responsibilities**:
  - Data aggregation and analysis
  - Report generation and scheduling
  - Real-time metrics calculation
  - Alert processing and notification

### Document Analysis Processor

**Document analysis result management**

- **Responsibilities**:
  - Analysis result storage and versioning
  - Batch processing coordination
  - Result validation and quality control
  - Historical analysis tracking

## Data Flow

### Document Analysis Flow

1. **Analysis Request**: Document analysis initiated
2. **Batch Creation**: Analysis batch created and tracked
3. **Processing**: Documents analyzed and results generated
4. **Storage**: Results stored with versioning
5. **Aggregation**: Results aggregated and summarized
6. **Reporting**: Analysis reports generated and delivered

### Analytics Processing Flow

1. **Data Collection**: Raw data collected from various sources
2. **Processing**: Data cleaned, transformed, and analyzed
3. **Aggregation**: Metrics calculated and aggregated
4. **Storage**: Processed data stored for querying
5. **Visualization**: Data prepared for dashboard consumption

## Complete Working Details

### Configuration

**Environment Variables**:
- `ANALYTICS_RETENTION_DAYS`: Data retention period
- `ANALYTICS_BATCH_SIZE`: Processing batch size
- `ANALYTICS_CACHE_TTL`: Cache TTL for analytics data

### Analysis Types

- **Sentiment Analysis**: Document sentiment scoring
- **Entity Recognition**: Named entity extraction
- **Topic Modeling**: Document topic identification
- **Quality Assessment**: Document quality metrics

### Performance Characteristics

- **Processing Speed**: Batch processing with configurable sizes
- **Query Performance**: Optimized for real-time dashboards
- **Storage Efficiency**: Compressed storage with indexing
- **Scalability**: Horizontal scaling for large datasets

### Error Handling

- **Processing Failures**: Batch retry and error recovery
- **Data Corruption**: Validation and integrity checks
- **Resource Limits**: Automatic scaling and resource management
- **Query Timeouts**: Query optimization and timeout handling

### Monitoring and Observability

- **Processing Metrics**: Batch success rates and processing times
- **Data Quality**: Analysis result quality and accuracy metrics
- **System Performance**: Resource usage and performance monitoring
- **User Analytics**: Usage patterns and adoption metrics

### Security Considerations

- **Data Privacy**: Sensitive data handling and anonymization
- **Access Control**: Role-based access to analytics data
- **Audit Logging**: All analytics operations logged
- **Data Encryption**: Data encryption at rest and in transit

### Scaling Considerations

- **Data Partitioning**: Time-based and project-based partitioning
- **Query Optimization**: Indexing and caching strategies
- **Load Balancing**: Request distribution across instances
- **Storage Scaling**: Database clustering and sharding