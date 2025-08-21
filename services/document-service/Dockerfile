FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies required by MarkItDown and PDF tooling
# - poppler-utils: pdftoppm/pdftocairo for PDF rendering
# - tesseract-ocr: OCR support for scanned PDFs (optional)
# - ghostscript: PDF processing utilities
# - libreoffice: DOC/DOCX to PDF/HTML conversions (optional)
# - pandoc: document conversions used by some pipelines (optional)
# - ffmpeg: media handling (optional for audio/video)
# - libmagic1: file type detection
# - libglib2.0-0, libsm6, libxrender1, libxext6: X libs needed by some renderers
# - curl: for Docker HEALTHCHECK
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    gcc \
    poppler-utils \
    tesseract-ocr \
    ghostscript \
    libreoffice \
    pandoc \
    ffmpeg \
    libmagic1 \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Expose port
EXPOSE 8004

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8004/health || exit 1

# Run the application
CMD ["python", "main.py"]
