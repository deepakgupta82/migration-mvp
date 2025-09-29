# Document Service Documentation

## Service Overview

The Document Service is a specialized microservice for handling document upload, processing, and storage operations. It converts various document formats to markdown using MarkItDown, performs OCR on images/PDFs using Tesseract, and stores processed content in MinIO object storage.

**Port:** 8003
**Technology:** FastAPI (Python), MarkItDown, Tesseract OCR
**Storage:** MinIO Object Storage
**Processing:** OCR, format conversion, text extraction

## Functionality

The Document Service provides comprehensive document processing capabilities:

- **Document Upload:** Handles file uploads from clients
- **Format Conversion:** Converts documents to markdown using MarkItDown
- **OCR Processing:** Extracts text from images and PDFs using Tesseract
- **Content Storage:** Stores processed documents in MinIO
- **Metadata Management:** Tracks document processing status and metadata
- **Batch Processing:** Handles multiple document processing requests
- **Error Recovery:** Robust error handling and retry mechanisms

## APIs/Endpoints

### Document Processing
- `POST /api/documents/{project_id}/upload` - Upload documents for processing
- `POST /api/documents/{project_id}/process-selected` - Process selected documents
- `GET /api/documents/{project_id}/status` - Get processing status
- `GET /api/documents/{project_id}/files` - List processed documents

### Health & Monitoring
- `GET /health` - Health check with dependency status
- `GET /livez` - Liveness probe
- `GET /healthz` - Readiness probe

## Data Models/Schemas

### Request Models
```python
class DocumentUploadRequest(BaseModel):
    files: List[UploadFile]
    metadata: Optional[Dict[str, Any]] = None

class DocumentProcessRequest(BaseModel):
    file_names: List[str]
    reprocess: bool = False
    options: Optional[Dict[str, Any]] = None
```

### Response Models
```python
class DocumentStatus(BaseModel):
    project_id: str
    file_name: str
    status: str  # pending, processing, completed, failed
    progress: float
    error_message: Optional[str] = None
    processed_at: Optional[datetime] = None

class DocumentList(BaseModel):
    project_id: str
    documents: List[DocumentStatus]
    total_count: int
```

## Key Components

### Document Processing Engine
- **MarkItDown Integration:** Converts various formats (PDF, DOCX, HTML, etc.) to markdown
- **Tesseract OCR:** Extracts text from images and scanned documents
- **PyMuPDF Integration:** Advanced PDF processing capabilities
- **Content Extraction:** Intelligent text and metadata extraction

### Storage Management
- **MinIO Client:** Object storage for document persistence
- **Bucket Organization:** Structured storage with project-based organization
- **File Versioning:** Support for document version management
- **Access Control:** Secure document access and sharing

### Processing Pipeline
- **Queue Management:** Asynchronous processing with status tracking
- **Batch Operations:** Efficient processing of multiple documents
- **Error Recovery:** Automatic retry and failure handling
- **Progress Monitoring:** Real-time processing status updates

## Data Flow

### Document Upload Process
1. **File Reception:** Accept uploaded files via HTTP multipart
2. **Validation:** Check file types, sizes, and project permissions
3. **Storage:** Save raw files to MinIO uploads bucket
4. **Metadata Creation:** Record file information in database
5. **Processing Queue:** Add to processing queue for conversion

### Document Processing Pipeline
1. **Format Detection:** Identify document type and processing requirements
2. **Content Extraction:** Use appropriate tool (MarkItDown, OCR, etc.)
3. **Text Processing:** Clean and normalize extracted text
4. **Metadata Generation:** Extract document properties and structure
5. **Storage:** Save processed content to MinIO processed bucket
6. **Database Update:** Update processing status and metadata
7. **Notification:** Trigger events for downstream services

### OCR Processing
1. **Image Extraction:** Extract images from PDFs if needed
2. **Tesseract Configuration:** Set up OCR with appropriate language models
3. **Text Recognition:** Process images to extract text content
4. **Text Assembly:** Combine OCR results with document structure
5. **Quality Validation:** Check OCR accuracy and confidence levels

## Complete Working Details

### Dependencies
- **MarkItDown:** Document format conversion library
- **Tesseract OCR:** Optical character recognition engine
- **PyMuPDF (fitz):** Advanced PDF processing
- **MinIO Client:** Object storage operations
- **Redis:** Processing queue management (optional)

### Configuration
- **Tesseract Path:** Windows-specific OCR engine configuration
- **MinIO Settings:** Object storage connection parameters
- **Processing Options:** OCR languages, conversion settings
- **Queue Configuration:** Processing concurrency and timeouts

### Startup Process
1. **Dependency Validation:** Check Tesseract, MarkItDown, and MinIO availability
2. **Path Configuration:** Set up OCR engine paths for Windows
3. **Directory Creation:** Ensure logs and temp directories exist
4. **Table Model Optimization:** Initialize document processing models

### Error Handling
- **Processing Failures:** Detailed error logging and status updates
- **Storage Issues:** Fallback mechanisms for MinIO failures
- **OCR Errors:** Graceful degradation when OCR is unavailable
- **Timeout Management:** Configurable processing timeouts

### Performance Optimizations
- **Asynchronous Processing:** Non-blocking document operations
- **Memory Management:** Efficient handling of large documents
- **Caching:** Processed content caching for repeated access
- **Batch Processing:** Optimized for multiple document operations

### Security
- **File Validation:** Content type and size restrictions
- **Access Control:** Project-based document permissions
- **Input Sanitization:** Safe file handling and processing
- **Audit Logging:** Comprehensive processing activity logs

### Integration Points
- **Backend Gateway:** Primary API for document operations
- **Project Service:** Document metadata and project association
- **Vector Service:** Processed content indexing for search
- **Graph Service:** Document relationship extraction
- **AI Agent Service:** Document analysis and insights

The Document Service transforms raw documents into structured, searchable content that powers the platform's knowledge base and AI capabilities.