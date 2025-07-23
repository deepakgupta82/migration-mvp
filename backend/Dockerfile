# =====================================================================================
# Stage 1: The "Builder" Stage
# This stage installs all dependencies, including heavy ones, to create a
# complete virtual environment.
# =====================================================================================
FROM python:3.11-slim as builder

# Set environment variables to prevent unnecessary cache and interactive prompts
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install essential build tools that might be needed by some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create a virtual environment. This is key to isolating packages.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy ONLY the requirements file first to leverage Docker layer caching
COPY requirements.txt .

# Install the dependencies into the virtual environment
# We use --no-cache-dir to reduce layer size from pip's cache
RUN pip install --no-cache-dir -r requirements.txt


# =====================================================================================
# Stage 2: The "Final" Stage
# This stage is the clean, lightweight image that will actually be deployed.
# We copy only the necessary files from the "builder" stage.
# =====================================================================================
FROM python:3.11-slim as final

# Set environment variables for production
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Copy the virtual environment from the builder stage. This contains all our
# installed packages but NONE of the build tools or pip cache from the previous stage.
COPY --from=builder /opt/venv /opt/venv

# Copy the application source code
COPY app /app

# Set the PATH to include the virtual environment's bin directory so the
# installed packages are found when we run the application.
ENV PATH="/opt/venv/bin:$PATH"

# Expose the port the app runs on
EXPOSE 8000

# The command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]