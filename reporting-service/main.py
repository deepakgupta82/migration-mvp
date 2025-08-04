"""
Reporting Service - Advanced Document & Diagram Generation
Converts Markdown reports to professional DOCX and PDF formats
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Literal
import os
import logging
import tempfile
import uuid
from datetime import datetime

# Setup logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import pypandoc
    PANDOC_AVAILABLE = True
    # Test if pandoc is actually available
    try:
        pypandoc.get_pandoc_version()
    except OSError:
        PANDOC_AVAILABLE = False
        logger.warning("Pandoc is not installed or not in PATH. PDF/DOCX generation will be limited.")
except ImportError:
    PANDOC_AVAILABLE = False
    logger.warning("pypandoc is not installed. PDF/DOCX generation will be limited.")
from minio import Minio
from minio.error import S3Error
import sqlalchemy
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import io
import requests

# Logger already configured above

app = FastAPI(title="Reporting Service", description="Advanced Document & Diagram Generation Service")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://projectuser:projectpass@localhost:5432/projectdb")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Project service configuration
PROJECT_SERVICE_URL = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002")

# MinIO configuration
MINIO_ENDPOINT = os.getenv("OBJECT_STORAGE_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("OBJECT_STORAGE_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("OBJECT_STORAGE_SECRET_KEY", "minioadmin")

# Initialize MinIO client
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False  # Set to True for HTTPS
)

# Ensure buckets exist
def ensure_buckets():
    """Ensure required MinIO buckets exist"""
    buckets = ["reports", "diagrams"]
    for bucket in buckets:
        try:
            if not minio_client.bucket_exists(bucket):
                minio_client.make_bucket(bucket)
                logger.info(f"Created bucket: {bucket}")
        except S3Error as e:
            logger.error(f"Error creating bucket {bucket}: {e}")

# Request models
class ReportGenerationRequest(BaseModel):
    project_id: str
    format: Literal["docx", "pdf"] = "pdf"
    markdown_content: str

class ReportResponse(BaseModel):
    success: bool
    report_url: Optional[str] = None
    minio_url: Optional[str] = None
    message: str

@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    ensure_buckets()
    logger.info("Reporting service started successfully")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        # Test MinIO connection
        minio_client.list_buckets()

        return {
            "status": "healthy",
            "database": "connected",
            "object_storage": "connected",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

@app.post("/generate_report", response_model=ReportResponse)
async def generate_report(request: ReportGenerationRequest):
    """Generate professional report in DOCX or PDF format"""
    try:
        logger.info(f"Generating {request.format} report for project {request.project_id}")

        # Generate report synchronously to return MinIO URL
        minio_url = await _generate_report_task(
            request.project_id,
            request.format,
            request.markdown_content
        )

        return ReportResponse(
            success=True,
            minio_url=minio_url,
            message=f"Report generated successfully for project {request.project_id}"
        )

    except Exception as e:
        logger.error(f"Error generating report: {str(e)}")
        return ReportResponse(
            success=False,
            message=f"Failed to generate report: {str(e)}"
        )

async def _generate_report_task(project_id: str, format: str, markdown_content: str) -> str:
    """Generate and upload report, return MinIO URL"""
    try:
        logger.info(f"Starting report generation for project {project_id}")

        # Prepare markdown content with professional formatting
        formatted_content = _format_markdown_content(markdown_content, project_id)

        # Generate document based on format
        if format == "docx":
            file_content = _generate_docx(formatted_content)
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:  # pdf
            file_content = _generate_pdf(formatted_content)
            content_type = "application/pdf"

        # Save locally first
        local_reports_dir = os.path.join("reports", project_id)
        os.makedirs(local_reports_dir, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        local_filename = f"report_{timestamp}.{format}"
        local_file_path = os.path.join(local_reports_dir, local_filename)

        with open(local_file_path, 'wb') as f:
            f.write(file_content)

        logger.info(f"Report saved locally to: {local_file_path}")

        # Upload to MinIO
        object_name = f"{project_id}/report_{timestamp}.{format}"
        file_stream = io.BytesIO(file_content)

        try:
            minio_client.put_object(
                "reports",
                object_name,
                file_stream,
                length=len(file_content),
                content_type=content_type
            )

            # Generate public URL
            report_url = f"http://{MINIO_ENDPOINT}/reports/{object_name}"
            logger.info(f"Report uploaded to MinIO: {report_url}")
            return report_url
        except Exception as minio_error:
            logger.warning(f"Failed to upload to MinIO: {str(minio_error)}")
            # Use local file URL as fallback
            report_url = f"/reports/{project_id}/{local_filename}"
            return report_url

        # Update project database with report URL
        await _update_project_report_url(project_id, report_url, format)

        logger.info(f"Report generated successfully for project {project_id}: {report_url}")
        return report_url

    except Exception as e:
        logger.error(f"Error in report generation: {str(e)}")
        raise

def _format_markdown_content(content: str, project_id: str) -> str:
    """Format markdown content with professional headers and structure"""
    timestamp = datetime.utcnow().strftime("%B %d, %Y")

    formatted_content = f"""---
title: "Cloud Migration Assessment Report"
subtitle: "Project ID: {project_id}"
author: "Nagarro AgentiMigrate Platform"
date: "{timestamp}"
geometry: margin=1in
fontsize: 11pt
---

# Executive Summary

This comprehensive cloud migration assessment has been generated by the Nagarro AgentiMigrate platform using advanced AI analysis and industry best practices.

---

{content}

---

## Report Generation Details

- **Generated By**: Nagarro AgentiMigrate Platform
- **Generation Date**: {timestamp}
- **Project ID**: {project_id}
- **Report Format**: Professional Assessment Document

*This report was automatically generated using AI-powered analysis of your infrastructure documentation and represents our expert recommendations for cloud migration strategy.*
"""
    return formatted_content

def _generate_docx(content: str) -> bytes:
    """Generate DOCX document from markdown content"""
    try:
        if not PANDOC_AVAILABLE:
            raise Exception("Pandoc is not available. Please install pandoc to generate DOCX documents.")

        # Use template if available, otherwise use default styling
        template_path = "./template.docx" if os.path.exists("./template.docx") else None

        extra_args = []
        if template_path:
            extra_args.append(f"--reference-doc={template_path}")

        # Convert markdown to DOCX
        docx_content = pypandoc.convert_text(
            content,
            'docx',
            format='md',
            extra_args=extra_args
        )

        return docx_content

    except Exception as e:
        logger.error(f"Error generating DOCX: {str(e)}")
        raise

def _generate_pdf(content: str) -> bytes:
    """Generate PDF document from markdown content using LaTeX"""
    try:
        if not PANDOC_AVAILABLE:
            raise Exception("Pandoc is not available. Please install pandoc to generate PDF documents.")

        # Create temporary file for PDF output
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
            temp_pdf_path = temp_pdf.name

        try:
            # Set PATH to include MiKTeX for this process
            import os
            miktex_path = r"C:\Users\deepakgupta13\AppData\Local\Programs\MiKTeX\miktex\bin\x64"
            if miktex_path not in os.environ.get('PATH', ''):
                os.environ['PATH'] = os.environ.get('PATH', '') + ';' + miktex_path

            # Convert markdown to PDF using LaTeX engine with output file
            pypandoc.convert_text(
                content,
                'pdf',
                format='md',
                outputfile=temp_pdf_path,
                extra_args=[
                    '--pdf-engine=pdflatex',
                    '--variable=geometry:margin=1in',
                    '--variable=fontsize:11pt',
                    '--variable=documentclass:article',
                    '--variable=papersize:letter'
                ]
            )

            # Read the generated PDF file
            with open(temp_pdf_path, 'rb') as f:
                pdf_content = f.read()

            return pdf_content

        finally:
            # Clean up temporary file
            if os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)

    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}")
        raise

async def _update_project_report_url(project_id: str, report_url: str, format: str):
    """Update project database with generated report URL"""
    try:
        # Call project service API to update the project

        # Determine which field to update based on format
        update_data = {}
        if format == "pdf":
            update_data["report_artifact_url"] = report_url
        else:  # docx or other formats
            update_data["report_url"] = report_url

        response = requests.put(
            f"{PROJECT_SERVICE_URL}/projects/{project_id}",
            json=update_data,
            timeout=30
        )

        if response.status_code == 200:
            logger.info(f"Updated project {project_id} with {format} report URL: {report_url}")
        else:
            logger.error(f"Failed to update project {project_id}: {response.text}")

    except Exception as e:
        logger.error(f"Error updating project report URL: {str(e)}")

@app.get("/reports/{project_id}")
async def get_project_report_url(project_id: str):
    """Get the report URL for a specific project"""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT report_url FROM projects WHERE id = :project_id"),
                {"project_id": project_id}
            )
            row = result.fetchone()

            if row and row[0]:
                return {"project_id": project_id, "report_url": row[0]}
            else:
                raise HTTPException(status_code=404, detail="Report not found for this project")

    except Exception as e:
        logger.error(f"Error fetching report URL: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
