FROM python:3.13-slim-bullseye

ENV DEBIAN_FRONTEND=noninteractive
ENV EXIFTOOL_PATH=/usr/bin/exiftool
ENV FFMPEG_PATH=/usr/bin/ffmpeg
ENV MARKITDOWN_ENABLE_PLUGINS=True

# Runtime dependencies for MarkItDown
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    exiftool && \
    rm -rf /var/lib/apt/lists/*

# Install the MCP server from PyPI
RUN pip install --no-cache-dir markitdown-mcp

WORKDIR /workdir

EXPOSE 5001

ENTRYPOINT ["markitdown-mcp"]
CMD ["--http", "--host", "0.0.0.0", "--port", "5001"]
