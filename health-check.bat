@echo off
REM =====================================================================================
REM Nagarro AgentiMigrate Platform - Windows Health Check Script (Rancher Desktop)
REM =====================================================================================

echo 🏥 Nagarro AgentiMigrate Platform - Health Check
echo ================================================
echo    Using Rancher Desktop for containerization

REM Determine Docker Compose command
docker compose version >nul 2>&1
if %errorlevel% equ 0 (
    set DOCKER_COMPOSE=docker compose
) else (
    set DOCKER_COMPOSE=docker-compose
)

echo 📊 Container Status:
echo ===================

REM Check containers
echo 📦 Checking containers...
docker ps --format "table {{.Names}}\t{{.Status}}" | findstr /C:"frontend_service" /C:"backend_service" /C:"project_service" /C:"reporting_service" /C:"megaparse_service" /C:"postgres_service" /C:"neo4j_service" /C:"weaviate_service" /C:"minio_service"

echo.
echo 🌐 Service Health Checks:
echo =========================

REM Function to check service health (simplified for batch)
echo 🔍 Checking services...

REM Check Frontend
curl -s -o nul -w "Frontend: %%{http_code}" http://localhost:3000
echo.

REM Check Backend API
curl -s -o nul -w "Backend API: %%{http_code}" http://localhost:8000/docs
echo.

REM Check Project Service
curl -s -o nul -w "Project Service: %%{http_code}" http://localhost:8002/docs
echo.

REM Check Reporting Service
curl -s -o nul -w "Reporting Service: %%{http_code}" http://localhost:8001/docs
echo.

REM Check MegaParse Service
curl -s -o nul -w "MegaParse Service: %%{http_code}" http://localhost:5001
echo.

REM Check Neo4j
curl -s -o nul -w "Neo4j Browser: %%{http_code}" http://localhost:7474
echo.

REM Check Weaviate
curl -s -o nul -w "Weaviate: %%{http_code}" http://localhost:8080/v1/.well-known/ready
echo.

REM Check MinIO
curl -s -o nul -w "MinIO Console: %%{http_code}" http://localhost:9001
echo.

echo.
echo 💾 Data Persistence Check:
echo ==========================

REM Check data directories
if exist "minio_data" (
    echo ✅ minio_data directory exists
) else (
    echo ⚠️  minio_data directory missing
)

REM Check Docker volumes
docker volume ls | findstr postgres_data >nul
if %errorlevel% equ 0 (
    echo ✅ postgres_data volume exists
) else (
    echo ⚠️  postgres_data volume missing
)

echo.
echo 🔧 Configuration Check:
echo =======================

REM Check .env file
if exist ".env" (
    echo ✅ .env file exists

    REM Check OpenAI API key
    findstr /C:"your_openai_api_key_here" .env >nul 2>&1
    if %errorlevel% equ 0 (
        echo ❌ OpenAI API key not configured
        echo    Please edit .env and add your OpenAI API key
    ) else (
        echo ✅ OpenAI API key configured
    )
) else (
    echo ❌ .env file missing
    echo    Run build-optimized.bat to create .env file
)

echo.
echo 📈 Resource Usage:
echo ==================
docker system df

echo.
echo 📋 Quick Commands:
echo ==================
echo 🔍 Check service status: %DOCKER_COMPOSE% ps
echo 📜 View all logs: %DOCKER_COMPOSE% logs
echo 🔄 Restart services: %DOCKER_COMPOSE% restart
echo 🛑 Stop platform: %DOCKER_COMPOSE% down
echo 🚀 Start platform: %DOCKER_COMPOSE% up -d

echo.
echo 🌍 Access URLs:
echo ===============
echo    • Frontend: http://localhost:3000
echo    • Backend API: http://localhost:8000
echo    • Neo4j Browser: http://localhost:7474
echo    • MinIO Console: http://localhost:9001

echo.
pause
