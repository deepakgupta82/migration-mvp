# Reporting Service Documentation

## Service Overview

The Reporting Service is a specialized microservice for generating professional documents from markdown content. It converts markdown reports into high-quality PDF and DOCX formats using Pandoc and LaTeX, then stores the generated documents in MinIO object storage.

**Port:** 8001
**Technology:** FastAPI (Python), Pandoc, LaTeX (MiKTeX)
**Storage:** MinIO Object Storage
**Database:** PostgreSQL (for project metadata)

## Functionality

The Reporting Service provides advanced document generation capabilities:

- **Markdown to PDF Conversion:** Uses Pandoc with LaTeX engine to generate professional PDF documents
- **Markdown to DOCX Conversion:** Generates Microsoft Word documents with proper formatting
- **Document Storage:** Stores generated reports in MinIO with public URLs
- **Project Integration:** Updates project records with report URLs
- **Template Support:** Uses custom DOCX templates for consistent branding
- **LaTeX Sanitization:** Handles special characters and formatting for LaTeX compatibility
- **Professional Formatting:** Adds headers, footers, and metadata to generated documents

## APIs/Endpoints

### Document Generation
- `POST /generate_report` - Generate professional report in PDF or DOCX format
- `POST /convert/pdf` - Convert markdown to PDF (direct response)
- `POST /convert/docx` - Convert markdown to DOCX (direct response)

### Report Management
- `GET /reports/{project_id}` - Get report URL for a project

### Health & Monitoring
- `GET /health` - Health check with database and MinIO connectivity

## Data Models/Schemas

### Request Models
```python
class ReportGenerationRequest(BaseModel):
    project_id: str
    format: Literal["docx", "pdf"] = "pdf"
    markdown_content: str

class ConversionRequest(BaseModel):
    markdown_content: str
    project_id: str
    filename: str
```

### Response Models
```python
class ReportResponse(BaseModel):
    success: bool
    report_url: Optional[str] = None
    minio_url: Optional[str] = None
    message: str
```

## Key Components

### Document Generation Engine
- **Pandoc Integration:** Uses pypandoc for format conversion
- **LaTeX Processing:** MiKTeX/TeX Live for PDF generation with pdflatex
- **Template System:** Custom DOCX templates for consistent formatting
- **Content Sanitization:** LaTeX special character escaping

### Storage Integration
- **MinIO Client:** Object storage for generated documents
- **Bucket Management:** Automatic bucket creation (reports, diagrams)
- **Public URLs:** Generates accessible URLs for document downloads

### Project Integration
- **Database Updates:** Updates project records with report URLs
- **Correlation ID Propagation:** Maintains request tracing across services
- **Error Handling:** Graceful fallbacks for storage failures

## Data Flow

### Report Generation Process
1. **Content Preparation:** Sanitize markdown content for LaTeX compatibility
2. **Format Selection:** Choose PDF (LaTeX) or DOCX (Pandoc) conversion
3. **Document Generation:** Use Pandoc to convert markdown to target format
4. **Local Storage:** Save generated file temporarily
5. **MinIO Upload:** Upload document to object storage
6. **URL Generation:** Create public access URL
7. **Project Update:** Update project database with report URL
8. **Response:** Return success status and document URL

### Content Formatting
1. **Header Addition:** Add professional headers with project metadata
2. **Structure Enhancement:** Include executive summary and generation details
3. **Metadata Injection:** Add timestamps, project IDs, and generation info
4. **LaTeX Variables:** Set document properties (margins, fonts, paper size)

## Complete Working Details

### Dependencies
- **Pandoc:** Required for document conversion
- **MiKTeX/TeX Live:** LaTeX distribution for PDF generation
- **MinIO:** Object storage for document persistence
- **PostgreSQL:** Project metadata storage

### Configuration
- **Environment Variables:**
  - `DATABASE_URL`: PostgreSQL connection string
  - `PROJECT_SERVICE_URL`: Project service endpoint
  - `MINIO_ENDPOINT`: MinIO server URL
  - `MINIO_ACCESS_KEY/SECRET_KEY`: MinIO credentials

### Startup Process
1. **Bucket Creation:** Ensure MinIO buckets exist
2. **Dependency Checks:** Verify Pandoc and LaTeX availability
3. **Service Registration:** Ready for document generation requests

### Error Handling
- **Conversion Failures:** Detailed error messages for debugging
- **Storage Issues:** Fallback to local file URLs if MinIO fails
- **Project Updates:** Non-blocking updates with warning logs
- **Dependency Missing:** Graceful degradation with informative messages

### Performance Considerations
- **Synchronous Generation:** Reports generated immediately for user feedback
- **Temporary Files:** Clean up local files after MinIO upload
- **Memory Management:** Stream processing for large documents
- **Timeout Handling:** Reasonable timeouts for conversion operations

### Security
- **Input Sanitization:** LaTeX injection prevention
- **Access Control:** Project ownership verification
- **URL Security:** Public URLs for generated documents
- **Correlation Tracing:** Request ID propagation for debugging

The Reporting Service transforms AI-generated markdown content into professional, presentation-ready documents suitable for client delivery and project documentation.