#!/bin/bash

# =====================================================================================
# Nagarro AgentiMigrate Platform - Local Development Setup
# =====================================================================================

set -e  # Exit on any error

echo "🚀 Nagarro AgentiMigrate Platform - Local Setup"
echo "================================================"

# Check if running on Windows (Git Bash, WSL, etc.)
if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] || [[ -n "$WSL_DISTRO_NAME" ]]; then
    echo "🪟 Windows environment detected"
    IS_WINDOWS=true
else
    echo "🐧 Unix-like environment detected"
    IS_WINDOWS=false
fi

# Check prerequisites
echo "🔍 Checking prerequisites..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker Desktop."
    echo "   Download from: https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Check Docker Compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not installed."
    exit 1
fi

# Use docker compose or docker-compose based on availability
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

echo "✅ Docker and Docker Compose are available"

# Enable BuildKit for advanced caching
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

echo "✅ BuildKit enabled for advanced caching features"

# Check if Docker BuildKit is available
if ! docker buildx version >/dev/null 2>&1; then
    echo "⚠️  Docker BuildKit not available, using standard build"
    export DOCKER_BUILDKIT=0
fi

# Check and create .env file
setup_environment() {
    echo "🔧 Setting up environment..."

    if [ ! -f ".env" ]; then
        echo "📝 Creating .env file..."
        cat > .env << EOF
# Nagarro AgentiMigrate Platform Configuration
# OpenAI API Key (Required for AI agents)
OPENAI_API_KEY=your_openai_api_key_here

# Alternative LLM Providers (Optional)
# ANTHROPIC_API_KEY=your_anthropic_key_here
# GOOGLE_API_KEY=your_google_key_here

# LLM Provider Selection (openai, anthropic, google)
LLM_PROVIDER=openai

# Database Configuration
POSTGRES_DB=projectdb
POSTGRES_USER=projectuser
POSTGRES_PASSWORD=projectpass

# MinIO Object Storage
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin

# Neo4j Graph Database
NEO4J_AUTH=neo4j/password

# Service URLs (Internal Docker network)
PROJECT_SERVICE_URL=http://project-service:8000
REPORTING_SERVICE_URL=http://reporting-service:8000
WEAVIATE_URL=http://weaviate:8080
NEO4J_URL=bolt://neo4j:7687
OBJECT_STORAGE_ENDPOINT=minio:9000
EOF
        echo "⚠️  Please edit .env file and add your OpenAI API key!"
        echo "   You can get one from: https://platform.openai.com/api-keys"
    else
        echo "✅ .env file already exists"
    fi
}

# Function to build with retry logic
build_with_retry() {
    local service=$1
    local max_attempts=3
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        echo "🔨 Building $service (attempt $attempt/$max_attempts)..."

        if $DOCKER_COMPOSE build \
            --build-arg BUILDKIT_INLINE_CACHE=1 \
            "$service"; then
            echo "✅ Successfully built $service"
            return 0
        else
            echo "❌ Build failed for $service (attempt $attempt/$max_attempts)"
            attempt=$((attempt + 1))

            if [ $attempt -le $max_attempts ]; then
                echo "⏳ Retrying in 5 seconds..."
                sleep 5
            fi
        fi
    done

    echo "💥 Failed to build $service after $max_attempts attempts"
    return 1
}

# Setup environment first
setup_environment

# Check if OpenAI API key is set
if grep -q "your_openai_api_key_here" .env 2>/dev/null; then
    echo "⚠️  Warning: OpenAI API key not configured in .env file"
    echo "   The platform will not work without a valid API key."
    echo "   Please edit .env and add your OpenAI API key, then run this script again."
    read -p "   Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p minio_data
mkdir -p postgres_data
echo "✅ Directories created"

# Stop any running containers
echo "🛑 Stopping any running containers..."
$DOCKER_COMPOSE down --remove-orphans || true

# Build services in optimal order (dependencies first)
echo "📦 Building services in dependency order..."

# Build base services first (no dependencies)
echo "🔧 Building base services..."
build_with_retry "megaparse"
build_with_retry "project-service"
build_with_retry "reporting-service"

# Build backend (depends on megaparse)
echo "🔧 Building backend service..."
build_with_retry "backend"

# Build frontend (depends on backend)
echo "🔧 Building frontend service..."
build_with_retry "frontend"

echo "🎉 All services built successfully!"

# Optional: Show build cache usage
echo "📊 Docker build cache usage:"
docker system df

# Optional: Clean up dangling images
echo "🧹 Cleaning up dangling images..."
docker image prune -f

echo "✨ Build process completed successfully!"
echo ""
echo "🚀 Starting the platform..."
$DOCKER_COMPOSE up -d

echo ""
echo "🎉 Nagarro AgentiMigrate Platform is starting up!"
echo "================================================"
echo "🌍 Access URLs:"
echo "   • Frontend (Command Center): http://localhost:3000"
echo "   • Backend API: http://localhost:8000"
echo "   • Project Service: http://localhost:8002"
echo "   • Reporting Service: http://localhost:8003"
echo "   • MegaParse Service: http://localhost:5001"
echo "   • Neo4j Browser: http://localhost:7474"
echo "   • Weaviate: http://localhost:8080"
echo "   • MinIO Console: http://localhost:9001"
echo ""
echo "🔑 Default Credentials:"
echo "   • Neo4j: neo4j / password"
echo "   • MinIO: minioadmin / minioadmin"
echo ""
echo "📈 Build optimizations applied:"
echo "   ✅ Cache mounts for package managers (apt, pip, npm)"
echo "   ✅ Layer optimization with dependency-first copying"
echo "   ✅ Multi-stage builds for smaller final images"
echo "   ✅ BuildKit inline cache for faster rebuilds"
echo "   ✅ Non-root users for security"
echo "   ✅ Health checks for monitoring"
echo ""
echo "🔍 To check service status: $DOCKER_COMPOSE ps"
echo "📜 To view logs: $DOCKER_COMPOSE logs -f [service_name]"
echo "🛑 To stop platform: $DOCKER_COMPOSE down"
