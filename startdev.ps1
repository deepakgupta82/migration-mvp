#!/usr/bin/env pwsh
# Development Environment Startup Script for Nagarro Ascent Platform
# This script starts all required services in the correct order

Write-Host "🚀 Starting Nagarro Ascent Development Environment..." -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green

# Function to check if a port is in use
function Test-Port {
    param([int]$Port)
    try {
        $connection = Test-NetConnection -ComputerName localhost -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue
        return $connection
    } catch {
        return $false
    }
}

# Function to wait for service to be ready
function Wait-ForService {
    param(
        [string]$ServiceName,
        [int]$Port,
        [int]$TimeoutSeconds = 60
    )
    
    Write-Host "⏳ Waiting for $ServiceName to be ready on port $Port..." -ForegroundColor Yellow
    $elapsed = 0
    
    while ($elapsed -lt $TimeoutSeconds) {
        if (Test-Port -Port $Port) {
            Write-Host "✅ $ServiceName is ready!" -ForegroundColor Green
            return $true
        }
        Start-Sleep -Seconds 5
        $elapsed += 5
        Write-Host "   Still waiting... ($elapsed/$TimeoutSeconds seconds)" -ForegroundColor Gray
    }
    
    Write-Host "❌ $ServiceName failed to start within $TimeoutSeconds seconds" -ForegroundColor Red
    return $false
}

# Function to check Docker containers
function Check-DockerContainers {
    Write-Host "🐳 Checking Docker containers..." -ForegroundColor Cyan
    
    # Check if Docker is running
    try {
        docker version | Out-Null
    } catch {
        Write-Host "❌ Docker is not running. Please start Docker Desktop." -ForegroundColor Red
        exit 1
    }
    
    # Required containers
    $requiredContainers = @(
        @{Name="weaviate"; Port=8080; Image="semitechnologies/weaviate"},
        @{Name="neo4j"; Port=7474; Image="neo4j"}
    )
    
    foreach ($container in $requiredContainers) {
        $running = docker ps --filter "name=$($container.Name)" --format "{{.Names}}" | Where-Object { $_ -eq $container.Name }
        
        if (-not $running) {
            Write-Host "🔄 Starting $($container.Name) container..." -ForegroundColor Yellow
            
            if ($container.Name -eq "weaviate") {
                # Start Weaviate with proper configuration
                docker run -d --name weaviate -p 8080:8080 -e QUERY_DEFAULTS_LIMIT=25 -e AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true -e PERSISTENCE_DATA_PATH='/var/lib/weaviate' -e DEFAULT_VECTORIZER_MODULE='none' -e ENABLE_MODULES='' -e CLUSTER_HOSTNAME='node1' semitechnologies/weaviate:latest
            } elseif ($container.Name -eq "neo4j") {
                # Start Neo4j with proper configuration
                docker run -d --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password -e NEO4J_PLUGINS='["apoc"]' neo4j:latest
            }
            
            # Wait for container to be ready
            if (-not (Wait-ForService -ServiceName $container.Name -Port $container.Port -TimeoutSeconds 120)) {
                Write-Host "❌ Failed to start $($container.Name)" -ForegroundColor Red
                exit 1
            }
        } else {
            Write-Host "✅ $($container.Name) container is already running" -ForegroundColor Green
        }
    }
}

# Function to start a service in a new terminal
function Start-ServiceInTerminal {
    param(
        [string]$ServiceName,
        [string]$WorkingDirectory,
        [string]$Command,
        [int]$Port,
        [int]$WaitSeconds = 30
    )
    
    Write-Host "🔄 Starting $ServiceName..." -ForegroundColor Yellow
    
    # Check if service is already running
    if (Test-Port -Port $Port) {
        Write-Host "✅ $ServiceName is already running on port $Port" -ForegroundColor Green
        return $true
    }
    
    # Start service in new PowerShell window
    $scriptBlock = "cd '$WorkingDirectory'; $Command; Read-Host 'Press Enter to close'"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $scriptBlock
    
    # Wait for service to be ready
    return Wait-ForService -ServiceName $ServiceName -Port $Port -TimeoutSeconds $WaitSeconds
}

# Main execution
try {
    # Step 1: Check and start Docker containers
    Check-DockerContainers
    
    # Step 2: Start Project Service
    Write-Host "📊 Starting Project Service..." -ForegroundColor Cyan
    if (-not (Start-ServiceInTerminal -ServiceName "Project Service" -WorkingDirectory "project-service" -Command "`$env:SERVICE_AUTH_TOKEN='service-backend-token'; python main.py" -Port 8002 -WaitSeconds 60)) {
        Write-Host "❌ Failed to start Project Service" -ForegroundColor Red
        exit 1
    }
    
    # Step 3: Start Backend Service (takes longer)
    Write-Host "🧠 Starting Backend Service (this may take 10-15 minutes)..." -ForegroundColor Cyan
    if (-not (Start-ServiceInTerminal -ServiceName "Backend Service" -WorkingDirectory "backend" -Command "`$env:SERVICE_AUTH_TOKEN='service-backend-token'; `$env:OPENAI_API_KEY='your-openai-key-here'; python -m app.main" -Port 8000 -WaitSeconds 900)) {
        Write-Host "❌ Failed to start Backend Service" -ForegroundColor Red
        exit 1
    }
    
    # Step 4: Start Frontend
    Write-Host "🌐 Starting Frontend..." -ForegroundColor Cyan
    if (-not (Start-ServiceInTerminal -ServiceName "Frontend" -WorkingDirectory "frontend" -Command "npm start" -Port 3000 -WaitSeconds 120)) {
        Write-Host "❌ Failed to start Frontend" -ForegroundColor Red
        exit 1
    }
    
    # Step 5: Optional - Start Reporting Service
    Write-Host "📄 Starting Reporting Service (optional)..." -ForegroundColor Cyan
    if (Test-Path "reporting-service") {
        Start-ServiceInTerminal -ServiceName "Reporting Service" -WorkingDirectory "reporting-service" -Command "python main.py" -Port 8001 -WaitSeconds 60 | Out-Null
    } else {
        Write-Host "⚠️  Reporting service directory not found, skipping..." -ForegroundColor Yellow
    }
    
    Write-Host ""
    Write-Host "🎉 All services started successfully!" -ForegroundColor Green
    Write-Host "=============================================" -ForegroundColor Green
    Write-Host "📊 Project Service:  http://localhost:8002" -ForegroundColor Cyan
    Write-Host "🧠 Backend Service:   http://localhost:8000" -ForegroundColor Cyan
    Write-Host "🌐 Frontend:          http://localhost:3000" -ForegroundColor Cyan
    Write-Host "📄 Reporting Service: http://localhost:8001" -ForegroundColor Cyan
    Write-Host "🐳 Weaviate:          http://localhost:8080" -ForegroundColor Cyan
    Write-Host "🗄️  Neo4j:            http://localhost:7474" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "🔧 Development environment is ready!" -ForegroundColor Green
    Write-Host "   You can now access the platform at http://localhost:3000" -ForegroundColor White
    Write-Host ""
    Write-Host "💡 Tips:" -ForegroundColor Yellow
    Write-Host "   - Backend service takes 10-15 minutes to fully initialize" -ForegroundColor Gray
    Write-Host "   - Check individual terminal windows for service logs" -ForegroundColor Gray
    Write-Host "   - Use Ctrl+C in each terminal to stop services" -ForegroundColor Gray
    Write-Host ""
    
} catch {
    Write-Host "❌ Error starting development environment: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Keep script running
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
