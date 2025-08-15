# =====================================================================================
# Microservices Platform Startup Script
# =====================================================================================
# This script starts the Nagarro Ascent Platform in microservices mode
# Usage: .\start-microservices.ps1 [profile]
# Profiles: dev, prod, minimal
# =====================================================================================

param(
    [Parameter(Position=0)]
    [ValidateSet("dev", "prod", "minimal", "")]
    [string]$Environment = "dev"
)

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "🚀 Starting Nagarro Ascent Platform (Microservices Mode)" -ForegroundColor Green
Write-Host "Environment: $Environment" -ForegroundColor Yellow
Write-Host "=================================================" -ForegroundColor Cyan

# Set error handling
$ErrorActionPreference = "Stop"

# Environment setup
$env:COMPOSE_PROJECT_NAME = "nagarro_ascent_microservices"

try {
    Write-Host "📋 Checking prerequisites..." -ForegroundColor Blue
    
    # Check Docker
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker is not installed or not in PATH"
    }
    
    # Check Docker Compose
    if (-not (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
        throw "Docker Compose is not installed or not in PATH"
    }
    
    # Check if Docker daemon is running
    try {
        docker info | Out-Null
    }
    catch {
        throw "Docker daemon is not running. Please start Docker Desktop."
    }
    
    Write-Host "✅ Prerequisites check passed" -ForegroundColor Green

    Write-Host "`n🛠️  Building services..." -ForegroundColor Blue
    
    # Create required directories
    $directories = @("logs", "markitdown_debug", "data/chroma_db")
    foreach ($dir in $directories) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
            Write-Host "📁 Created directory: $dir" -ForegroundColor Gray
        }
    }
    
    # Start services based on environment
    switch ($Environment) {
        "minimal" {
            Write-Host "🎯 Starting minimal services (Infrastructure only)..." -ForegroundColor Yellow
            docker-compose -f docker-compose.microservices.yml up -d redis postgres neo4j minio
        }
        "dev" {
            Write-Host "🔧 Starting development services..." -ForegroundColor Yellow
            docker-compose -f docker-compose.microservices.yml up -d --build
        }
        "prod" {
            Write-Host "🏭 Starting production services..." -ForegroundColor Yellow
            docker-compose -f docker-compose.microservices.yml up -d --no-build
        }
        default {
            Write-Host "🔧 Starting development services (default)..." -ForegroundColor Yellow
            docker-compose -f docker-compose.microservices.yml up -d --build
        }
    }
    
    Write-Host "`n⏳ Waiting for services to start..." -ForegroundColor Blue
    
    # Wait for infrastructure services
    $services = @{
        "PostgreSQL" = @{ url = "http://localhost:5432"; container = "postgres" }
        "Redis" = @{ url = "http://localhost:6379"; container = "redis" }
        "Neo4j" = @{ url = "http://localhost:7474"; container = "neo4j" }
        "MinIO" = @{ url = "http://localhost:9001"; container = "minio" }
    }
    
    if ($Environment -ne "minimal") {
        $services["Document Service"] = @{ url = "http://localhost:8004/health"; container = "document-service" }
        $services["Project Service"] = @{ url = "http://localhost:8002/health"; container = "project-service" }
        $services["Reporting Service"] = @{ url = "http://localhost:8003/health"; container = "reporting-service" }
        $services["Backend API"] = @{ url = "http://localhost:8000/health"; container = "backend" }
        $services["Frontend"] = @{ url = "http://localhost:3000"; container = "frontend" }
    }
    
    $maxWait = 300 # 5 minutes
    $waited = 0
    $interval = 5
    
    do {
        $allHealthy = $true
        
        foreach ($serviceName in $services.Keys) {
            $service = $services[$serviceName]
            $containerName = "${env:COMPOSE_PROJECT_NAME}-$($service.container)-1"
            
            try {
                $containerStatus = docker inspect -f '{{.State.Status}}' $containerName 2>$null
                if ($containerStatus -ne "running") {
                    Write-Host "⏳ $serviceName container not running yet..." -ForegroundColor Yellow
                    $allHealthy = $false
                    continue
                }
                
                # Test health endpoint if available
                if ($service.url -like "*health*") {
                    try {
                        $response = Invoke-WebRequest -Uri $service.url -TimeoutSec 2 -UseBasicParsing
                        if ($response.StatusCode -eq 200) {
                            Write-Host "✅ $serviceName is healthy" -ForegroundColor Green
                        } else {
                            $allHealthy = $false
                        }
                    }
                    catch {
                        Write-Host "⏳ $serviceName health check pending..." -ForegroundColor Yellow
                        $allHealthy = $false
                    }
                } else {
                    Write-Host "✅ $serviceName container is running" -ForegroundColor Green
                }
            }
            catch {
                Write-Host "⏳ $serviceName not ready yet..." -ForegroundColor Yellow
                $allHealthy = $false
            }
        }
        
        if (-not $allHealthy) {
            Start-Sleep $interval
            $waited += $interval
            
            if ($waited -ge $maxWait) {
                Write-Host "⚠️  Timeout waiting for services. Some services may still be starting." -ForegroundColor Yellow
                break
            }
        }
        
    } while (-not $allHealthy)
    
    Write-Host "`n🎉 Microservices Platform Started Successfully!" -ForegroundColor Green
    Write-Host "=================================================" -ForegroundColor Cyan
    
    # Display service URLs
    Write-Host "`n🌐 Service URLs:" -ForegroundColor Blue
    Write-Host "• Frontend:           http://localhost:3000" -ForegroundColor White
    Write-Host "• Backend API:        http://localhost:8000" -ForegroundColor White
    Write-Host "• Document Service:   http://localhost:8004" -ForegroundColor White
    Write-Host "• Project Service:    http://localhost:8002" -ForegroundColor White
    Write-Host "• Reporting Service:  http://localhost:8003" -ForegroundColor White
    Write-Host "`n🛢️  Infrastructure:" -ForegroundColor Blue
    Write-Host "• PostgreSQL:         localhost:5432" -ForegroundColor White
    Write-Host "• Neo4j Browser:      http://localhost:7474" -ForegroundColor White
    Write-Host "• MinIO Console:      http://localhost:9001" -ForegroundColor White
    Write-Host "• Redis:              localhost:6379" -ForegroundColor White
    
    Write-Host "`n📋 Management Commands:" -ForegroundColor Blue
    Write-Host "• View logs:          docker-compose -f docker-compose.microservices.yml logs -f" -ForegroundColor Gray
    Write-Host "• Stop services:      docker-compose -f docker-compose.microservices.yml down" -ForegroundColor Gray
    Write-Host "• Restart service:    docker-compose -f docker-compose.microservices.yml restart <service-name>" -ForegroundColor Gray
    Write-Host "• Check status:       docker-compose -f docker-compose.microservices.yml ps" -ForegroundColor Gray
    
    Write-Host "`n🔍 Next Steps:" -ForegroundColor Blue
    Write-Host "1. Access the frontend at http://localhost:3000" -ForegroundColor White
    Write-Host "2. Check API documentation at http://localhost:8000/docs" -ForegroundColor White
    Write-Host "3. Monitor service health at individual health endpoints" -ForegroundColor White
    
    Write-Host "`n=================================================" -ForegroundColor Cyan
    
    # Option to show logs
    Write-Host "`nWould you like to view the logs? (y/n): " -ForegroundColor Yellow -NoNewline
    $showLogs = Read-Host
    
    if ($showLogs -eq "y" -or $showLogs -eq "Y") {
        Write-Host "`n📄 Showing service logs (Press Ctrl+C to stop)..." -ForegroundColor Blue
        docker-compose -f docker-compose.microservices.yml logs -f
    }
    
}
catch {
    Write-Host "`n❌ Error starting microservices platform:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    
    Write-Host "`n🔍 Troubleshooting:" -ForegroundColor Yellow
    Write-Host "1. Ensure Docker Desktop is running" -ForegroundColor White
    Write-Host "2. Check available disk space (need ~2GB)" -ForegroundColor White
    Write-Host "3. Verify no other services are using ports 3000, 8000-8004, 5432, 6379, 7474, 7687, 9000-9001" -ForegroundColor White
    Write-Host "4. Run 'docker-compose -f docker-compose.microservices.yml logs' to see detailed errors" -ForegroundColor White
    
    exit 1
}

Write-Host "`n✨ Platform is ready for development!" -ForegroundColor Green
