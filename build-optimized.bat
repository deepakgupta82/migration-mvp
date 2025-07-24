@echo off
REM =====================================================================================
REM Nagarro AgentiMigrate Platform - Windows Local Development Setup
REM =====================================================================================

echo 🚀 Nagarro AgentiMigrate Platform - Windows Setup
echo ================================================

REM Check if Docker is installed
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker is not installed. Please install Docker Desktop.
    echo    Download from: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

REM Check if Docker Compose is available
docker compose version >nul 2>&1
if %errorlevel% equ 0 (
    set DOCKER_COMPOSE=docker compose
) else (
    docker-compose --version >nul 2>&1
    if %errorlevel% equ 0 (
        set DOCKER_COMPOSE=docker-compose
    ) else (
        echo ❌ Docker Compose is not installed.
        pause
        exit /b 1
    )
)

echo ✅ Docker and Docker Compose are available

REM Enable BuildKit
set DOCKER_BUILDKIT=1
set COMPOSE_DOCKER_CLI_BUILD=1
echo ✅ BuildKit enabled for advanced caching

REM Setup environment
echo 🔧 Setting up environment...

if not exist ".env" (
    echo 📝 Creating .env file...
    (
        echo # Nagarro AgentiMigrate Platform Configuration
        echo # OpenAI API Key ^(Required for AI agents^)
        echo OPENAI_API_KEY=your_openai_api_key_here
        echo.
        echo # Alternative LLM Providers ^(Optional^)
        echo # ANTHROPIC_API_KEY=your_anthropic_key_here
        echo # GOOGLE_API_KEY=your_google_key_here
        echo.
        echo # LLM Provider Selection ^(openai, anthropic, google^)
        echo LLM_PROVIDER=openai
        echo.
        echo # Database Configuration
        echo POSTGRES_DB=projectdb
        echo POSTGRES_USER=projectuser
        echo POSTGRES_PASSWORD=projectpass
        echo.
        echo # MinIO Object Storage
        echo MINIO_ROOT_USER=minioadmin
        echo MINIO_ROOT_PASSWORD=minioadmin
        echo.
        echo # Neo4j Graph Database
        echo NEO4J_AUTH=neo4j/password
        echo.
        echo # Service URLs ^(Internal Docker network^)
        echo PROJECT_SERVICE_URL=http://project-service:8000
        echo REPORTING_SERVICE_URL=http://reporting-service:8000
        echo WEAVIATE_URL=http://weaviate:8080
        echo NEO4J_URL=bolt://neo4j:7687
        echo OBJECT_STORAGE_ENDPOINT=minio:9000
    ) > .env
    echo ⚠️  Please edit .env file and add your OpenAI API key!
    echo    You can get one from: https://platform.openai.com/api-keys
) else (
    echo ✅ .env file already exists
)

REM Check if OpenAI API key is configured
findstr /C:"your_openai_api_key_here" .env >nul 2>&1
if %errorlevel% equ 0 (
    echo ⚠️  Warning: OpenAI API key not configured in .env file
    echo    The platform will not work without a valid API key.
    echo    Please edit .env and add your OpenAI API key, then run this script again.
    set /p continue="   Continue anyway? (y/N): "
    if /i not "%continue%"=="y" exit /b 1
)

REM Create necessary directories
echo 📁 Creating necessary directories...
if not exist "minio_data" mkdir minio_data
if not exist "postgres_data" mkdir postgres_data
echo ✅ Directories created

REM Stop any running containers
echo 🛑 Stopping any running containers...
%DOCKER_COMPOSE% down --remove-orphans 2>nul

REM Build services
echo 📦 Building services...
echo 🔧 Building base services...

echo 🔨 Building megaparse...
%DOCKER_COMPOSE% build --build-arg BUILDKIT_INLINE_CACHE=1 megaparse
if %errorlevel% neq 0 (
    echo ❌ Failed to build megaparse
    pause
    exit /b 1
)

echo 🔨 Building project-service...
%DOCKER_COMPOSE% build --build-arg BUILDKIT_INLINE_CACHE=1 project-service
if %errorlevel% neq 0 (
    echo ❌ Failed to build project-service
    pause
    exit /b 1
)

echo 🔨 Building reporting-service...
%DOCKER_COMPOSE% build --build-arg BUILDKIT_INLINE_CACHE=1 reporting-service
if %errorlevel% neq 0 (
    echo ❌ Failed to build reporting-service
    pause
    exit /b 1
)

echo 🔨 Building backend...
%DOCKER_COMPOSE% build --build-arg BUILDKIT_INLINE_CACHE=1 backend
if %errorlevel% neq 0 (
    echo ❌ Failed to build backend
    pause
    exit /b 1
)

echo 🔨 Building frontend...
%DOCKER_COMPOSE% build --build-arg BUILDKIT_INLINE_CACHE=1 frontend
if %errorlevel% neq 0 (
    echo ❌ Failed to build frontend
    pause
    exit /b 1
)

echo 🎉 All services built successfully!

REM Clean up
echo 🧹 Cleaning up dangling images...
docker image prune -f

echo ✨ Build process completed successfully!
echo.
echo 🚀 Starting the platform...
%DOCKER_COMPOSE% up -d

echo.
echo 🎉 Nagarro AgentiMigrate Platform is starting up!
echo ================================================
echo 🌍 Access URLs:
echo    • Frontend (Command Center): http://localhost:3000
echo    • Backend API: http://localhost:8000
echo    • Project Service: http://localhost:8002
echo    • Reporting Service: http://localhost:8003
echo    • MegaParse Service: http://localhost:5001
echo    • Neo4j Browser: http://localhost:7474
echo    • Weaviate: http://localhost:8080
echo    • MinIO Console: http://localhost:9001
echo.
echo 🔑 Default Credentials:
echo    • Neo4j: neo4j / password
echo    • MinIO: minioadmin / minioadmin
echo.
echo 📈 Build optimizations applied:
echo    ✅ Cache mounts for package managers (apt, pip, npm)
echo    ✅ Layer optimization with dependency-first copying
echo    ✅ Multi-stage builds for smaller final images
echo    ✅ BuildKit inline cache for faster rebuilds
echo    ✅ Non-root users for security
echo    ✅ Health checks for monitoring
echo.
echo 🔍 To check service status: %DOCKER_COMPOSE% ps
echo 📜 To view logs: %DOCKER_COMPOSE% logs -f [service_name]
echo 🛑 To stop platform: %DOCKER_COMPOSE% down
echo.
pause
