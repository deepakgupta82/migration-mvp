# Document Processing Service

The Document Processing Service is a core component of Nagarro's Ascent Platform that handles document conversion, processing, and storage operations. It supports multiple document formats and provides both enhanced and traditional processing workflows.

## Features

- **Multi-format Support**: PDF, DOCX, PPTX, TXT, MD, HTML, CSV, and more
- **Dual Processing Workflows**:
  - **Enhanced**: Unstructured.io primary with structured JSONL output
  - **Traditional**: MarkItDown with multiple fallback strategies
- **OCR Support**: Tesseract OCR integration for scanned documents
- **Service Integration**: Automatic vector and graph service integration
- **Real-time Notifications**: WebSocket integration for processing status
- **Spreadsheet Row-wise JSONL**: .xlsx/.xls/.csv parsed row-by-row with stable row ids and rich metadata (sheet_name, row_index, columns, row_data)

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Upload API    │───▶│   Processing    │───▶│   Storage       │
│                 │    │   Engine        │    │   Service       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Vector        │◀───│   Service       │───▶│   Graph         │
│   Service       │    │   Integration   │    │   Service       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Local Development Setup

### Prerequisites

1. **Python 3.11+**
2. **System Dependencies**
3. **Service Dependencies**

### System Dependencies

The document service requires several system-level dependencies for optimal functionality:

#### Windows Setup

**Required Dependencies:**
- **Tesseract OCR** (Essential for PDF processing)
- **Poppler** (PDF rendering)
- **Ghostscript** (PDF utilities)

**Installation Steps:**

1. **Tesseract OCR Installation** (Critical):
   ```powershell
   # Option 1: Direct installer (Recommended)
   # Download from: https://github.com/UB-Mannheim/tesseract/wiki
   # Run installer as Administrator
   # ✓ Check "Add to PATH" during installation
   
   # Option 2: Package managers
   choco install tesseract           # Chocolatey
   scoop install tesseract          # Scoop
   winget install UB-Mannheim.TesseractOCR  # Winget
   ```

2. **Verify Tesseract Installation**:
   ```powershell
   tesseract --version
   # Should output version information
   ```

3. **Python Dependencies**:
   ```powershell
   cd services/document-service
   pip install -r requirements.txt
   ```

#### macOS/Linux Setup

```bash
# macOS
brew install tesseract poppler ghostscript

# Ubuntu/Debian
sudo apt-get update
sudo apt-get install tesseract-ocr poppler-utils ghostscript

# CentOS/RHEL
sudo yum install tesseract poppler-utils ghostscript
```

### Environment Configuration

Create `.env` file in the service directory:

```env
# Service Configuration
PORT=8004
DEBUG_DOCUMENT_CONVERSION_LOGS=false

# Timeouts
DOCUMENT_HTTP_TIMEOUT_SEC=30
CONVERSION_TIMEOUT_SEC=90

# Processing Limits
PDF_MAX_PAGES=50
MAX_CHUNKS=0

# Service URLs
STORAGE_SERVICE_URL=http://localhost:8010
VECTOR_SERVICE_URL=http://localhost:8005
GRAPH_SERVICE_URL=http://localhost:8006

# Enhanced Workflow
USE_ENHANCED_WORKFLOW=true
```

### Running the Service

#### Local Development
```powershell
cd services/document-service
python main.py
```

#### Docker (Production)
```bash
# From project root
docker-compose up document-service
```

### Health Check

Verify the service is running:
```bash
curl http://localhost:8004/health
```

## API Documentation

### Main Endpoints

- **Health Check**: `GET /health`
- **Process All**: `POST /api/documents/{project_id}/process-all`
- **Process Selected**: `POST /api/documents/{project_id}/process-selected`
- **Get Status**: `GET /api/documents/{project_id}/status/{job_id}`
- **Configuration**: `GET /api/documents/config`

### Processing Workflows

#### Enhanced Workflow
- Primary: Unstructured.io partitioning
- Output: Structured JSONL with rich metadata
- Integration: Automatic vector/graph service calls
- Use Case: Advanced document analysis

Spreadsheet-specific behavior (Enhanced and Traditional fallbacks):
- For .xlsx/.xls/.csv inputs, the service emits one JSONL element per row with type `table_row`.
- Each row element includes metadata: `sheet_name`, `row_index` (1-based, header included), `columns` (header names), `row_data` (column->value map).
- Element IDs are stable per row using a SHA1 signature of filename, sheet, row index, and a short row signature. This improves idempotent graph upserts.

#### Traditional Workflow
- Primary: MarkItDown conversion
- Fallbacks: PyMuPDF → pdfminer → pdfplumber
- Output: Markdown format
- Use Case: Basic document conversion

## Troubleshooting

### Common Issues

#### 1. Tesseract Not Found Error
```
ERROR: tesseract is not installed or it's not in your PATH
```

**Solution:**
1. Install Tesseract OCR (see installation steps above)
2. Restart terminal/IDE after installation
3. Verify with `tesseract --version`

#### 2. Document Processing Fails
**Check:**
- File format is supported
- File is not corrupted
- File size is within limits
- Required system dependencies are installed
- For spreadsheets: ensure `openpyxl` (xlsx) and `xlrd` (xls) are installed in the environment, or the service will fall back without row-wise parsing.

#### 3. Service Integration Failures
**Verify:**
- Storage service is running (port 8010)
- Vector service is running (port 8005)
- Graph service is running (port 8006)
- Service URLs in configuration are correct

### Logs and Debugging

#### Enable Debug Logging
```env
DEBUG_DOCUMENT_CONVERSION_LOGS=true
```

#### Log Locations
- **Console**: Structured text output
- **File**: `logs/document-service.log` (JSON format)
- **Debug**: `markitdown_debug/` directory

#### Correlation ID Tracking
All requests include correlation IDs for tracing:
```bash
curl -H "X-Correlation-ID: your-trace-id" http://localhost:8004/api/documents/...
```

## Development

### Adding New Processors

1. Implement processor class in `app/core/`
2. Register in processing workflow
3. Add tests in `tests/`
4. Update configuration options

### Testing

```bash
# Run tests
python -m pytest tests/

# Run specific test
python -m pytest tests/test_document_processor.py -v
```

### Code Quality

```bash
# Linting
flake8 app/
pylint app/

# Type checking
mypy app/
```

## Docker Environment

The service is designed to run in Docker where all dependencies are pre-installed:

```dockerfile
# System dependencies already included
RUN apt-get install -y tesseract-ocr poppler-utils ghostscript
```

For production deployment, use Docker to ensure consistent environment and dependencies.

## Performance Considerations

- **File Size Limits**: Configure `PDF_MAX_PAGES` for large documents
- **Timeout Settings**: Adjust `CONVERSION_TIMEOUT_SEC` based on hardware
- **Memory Usage**: Monitor during batch processing
- **Concurrent Processing**: Service handles async operations

## Security

- **File Validation**: Automatic file type detection and validation
- **Temporary Files**: Secure cleanup after processing
- **Service Authentication**: Bearer token authentication between services
- **CORS Configuration**: Configurable origins for web access

## Monitoring

The service provides comprehensive monitoring:

- **Health Checks**: Docker-compatible health endpoints
- **Structured Logging**: JSON format for log aggregation
- **Processing Metrics**: Success/failure rates, timing data
- **Service Integration Status**: Real-time dependency checking