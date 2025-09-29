# Storage Service

## Service Overview

The Storage Service is a centralized object storage microservice that operates on port 8010. It provides unified access to MinIO/S3-compatible storage systems, handling file uploads, downloads, and management operations for the Nagarro Ascent platform.

### Key Features

- **Multi-provider Support**: MinIO, S3, and filesystem storage
- **Project-based Organization**: Hierarchical storage structure
- **File Operations**: Upload, download, list, delete operations
- **Metadata Management**: Rich file metadata and tagging
- **Background Cleanup**: Automatic temporary file cleanup
- **Storage Analytics**: Usage statistics and monitoring
- **Security**: Access control and permission management

## Functionality

### Core Capabilities

1. **File Storage Operations**
   - File upload with multipart support
   - File download with streaming
   - File listing and search
   - File deletion and cleanup
   - Batch operations support

2. **Storage Management**
   - Project-based file organization
   - Automatic directory creation
   - Storage quota management
   - File versioning support

3. **Metadata Handling**
   - File metadata extraction and storage
   - Custom metadata support
   - File tagging and categorization
   - Search and filtering capabilities

4. **Storage Analytics**
   - Usage statistics and reporting
   - Storage utilization monitoring
   - Performance metrics tracking
   - Cost analysis and optimization

### Dependencies

- **MinIO/S3**: Object storage backend
- **PostgreSQL**: Metadata and configuration storage
- **Redis**: Caching and session management

## APIs/Endpoints

### File Operations
- `POST /api/storage/projects/{project_id}/upload` - Upload files
- `GET /api/storage/projects/{project_id}/files/{filename}` - Download files
- `GET /api/storage/projects/{project_id}/files` - List project files
- `DELETE /api/storage/projects/{project_id}/files/{filename}` - Delete files

### Metadata Operations
- `GET /api/storage/projects/{project_id}/metadata/{filename}` - Get file metadata
- `PUT /api/storage/projects/{project_id}/metadata/{filename}` - Update metadata
- `POST /api/storage/projects/{project_id}/search` - Search files by metadata

### Administrative Operations
- `GET /api/storage/projects/{project_id}/stats` - Get storage statistics
- `POST /api/storage/cleanup` - Trigger cleanup operations
- `GET /api/storage/health` - Service health check

## Data Models

### File Upload Request
```json
{
  "file": "multipart/form-data",
  "metadata": {
    "description": "Document description",
    "tags": ["important", "confidential"],
    "custom_field": "value"
  }
}
```

### File Metadata Structure
```json
{
  "filename": "document.pdf",
  "size": 1024000,
  "content_type": "application/pdf",
  "uploaded_at": "2024-01-01T12:00:00.000000",
  "uploaded_by": "user_123",
  "project_id": "project_456",
  "metadata": {
    "description": "Project documentation",
    "tags": ["documentation", "project"],
    "page_count": 25,
    "language": "en"
  },
  "storage_path": "projects/project_456/documents/document.pdf"
}
```

### Storage Statistics Structure
```json
{
  "project_id": "project_456",
  "total_files": 150,
  "total_size_bytes": 524288000,
  "total_size_human": "500 MB",
  "file_types": {
    "pdf": 45,
    "docx": 30,
    "txt": 25,
    "jpg": 50
  },
  "storage_used_percent": 75.5,
  "last_updated": "2024-01-01T12:00:00.000000"
}
```

## Key Components

### StorageProcessor (`app/core/storage_processor.py`)

**Core storage operations engine**

- **Responsibilities**:
  - Storage backend abstraction
  - File upload/download operations
  - Metadata management
  - Storage provider switching

### Storage Router (`app/routers/storage.py`)

**FastAPI router for storage operations**

- **Responsibilities**:
  - HTTP endpoint definitions
  - File upload handling
  - Response formatting
  - Error handling

## Data Flow

### File Upload Flow

1. **Upload Request**: File received via multipart upload
2. **Validation**: File type and size validation
3. **Storage**: File stored in appropriate backend
4. **Metadata Extraction**: File metadata extracted and stored
5. **Database Update**: File record created in database
6. **Response**: Upload confirmation returned

### File Download Flow

1. **Download Request**: File download requested
2. **Authorization**: Access permissions checked
3. **Retrieval**: File retrieved from storage backend
4. **Streaming**: File streamed to client
5. **Metadata Update**: Access statistics updated

## Complete Working Details

### Configuration

**Environment Variables**:
- `STORAGE_PROVIDER`: Storage backend (minio/s3/filesystem)
- `STORAGE_BUCKET`: Default bucket name
- `STORAGE_MAX_FILE_SIZE`: Maximum file size in bytes
- `STORAGE_CLEANUP_INTERVAL`: Cleanup interval in hours

### Supported Storage Providers

- **MinIO**: Self-hosted S3-compatible storage
- **AWS S3**: Amazon S3 cloud storage
- **Filesystem**: Local filesystem storage

### Performance Characteristics

- **Upload Speed**: Dependent on file size and network
- **Concurrent Operations**: High concurrency support
- **Storage Efficiency**: Optimized storage utilization
- **Metadata Performance**: Fast metadata queries

### Error Handling

- **Storage Failures**: Automatic retry with fallback
- **File Corruption**: Integrity checks and validation
- **Permission Errors**: Detailed access control messages
- **Quota Exceeded**: Graceful quota management

### Monitoring and Observability

- **Storage Metrics**: Usage statistics and trends
- **Performance Monitoring**: Upload/download speeds
- **Error Tracking**: Failure rates and types
- **Health Checks**: Storage backend connectivity

### Security Considerations

- **Access Control**: Project-scoped file access
- **File Validation**: Malware scanning and type validation
- **Encryption**: Data encryption at rest and in transit
- **Audit Logging**: All file operations logged

### Scaling Considerations

- **Horizontal Scaling**: Stateless design supports scaling
- **Storage Distribution**: Multi-bucket and multi-provider support
- **Load Balancing**: Request distribution across instances
- **Caching**: Metadata and file caching for performance