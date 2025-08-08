#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Development Platform Startup Script for Nagarro's Ascent Platform
.DESCRIPTION
    Checks required Docker containers, starts services in correct order, and validates startup
.NOTES
    Requires: Docker, Node.js, Python 3.9+, PowerShell 7+
#>

param(
    [switch]$SkipContainerCheck,
    [switch]$Verbose
)

# Configuration
$ErrorActionPreference = "Stop"
$VerbosePreference = if ($Verbose) { "Continue" } else { "SilentlyContinue" }

# Required containers and their health check ports
$RequiredContainers = @{
    "weaviate_service" = @{ Port = 8080; HealthPath = "/v1/meta" }
    "minio_service" = @{ Port = 9000; HealthPath = "/minio/health/live" }
    "postgres_service" = @{ Port = 5432; HealthPath = $null }
    "neo4j_service" = @{ Port = 7474; HealthPath = "/" }
    "megaparse_service" = @{ Port = 7676; HealthPath = "/health" }
}

# Service configurations
$Services = @{
    "project-service" = @{
        Path = "project-service"
        Command = "`$env:SERVICE_AUTH_TOKEN='service-backend-token'; python -m uvicorn main:app --host 0.0.0.0 --port 8002 --reload"
        Port = 8002
        HealthPath = "/health"
        StartupTime = 60
    }
    "reporting-service" = @{
        Path = "reporting-service"
        Command = "python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload"
        Port = 8001
        HealthPath = "/health"
        StartupTime = 60
    }
    "backend" = @{
        Path = "backend"
        Command = "`$env:SERVICE_AUTH_TOKEN='service-backend-token'; `$env:OPENAI_API_KEY='your-openai-key-here'; `$env:WEAVIATE_URL='http://localhost:8080'; `$env:NEO4J_URL='bolt://localhost:7687'; `$env:NEO4J_USER='neo4j'; `$env:NEO4J_PASSWORD='password'; `$env:PROJECT_SERVICE_URL='http://localhost:8002'; `$env:REPORTING_SERVICE_URL='http://localhost:8001'; `$env:OBJECT_STORAGE_ENDPOINT='localhost:9000'; `$env:OBJECT_STORAGE_ACCESS_KEY='minioadmin'; `$env:OBJECT_STORAGE_SECRET_KEY='minioadmin'; python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
        Port = 8000
        HealthPath = "/health"
        StartupTime = 300  # 5 minutes for backend
    }
    "frontend" = @{ 
        Path = "frontend"
        Command = "npm start"
        Port = 3000
        HealthPath = "/"
        StartupTime = 120
    }
}

# Logging functions
function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $color = switch ($Level) {
        "ERROR" { "Red" }
        "WARN" { "Yellow" }
        "SUCCESS" { "Green" }
        default { "White" }
    }
    Write-Host "[$timestamp] [$Level] $Message" -ForegroundColor $color
}

function Test-Port {
    param([string]$HostName = "localhost", [int]$Port, [int]$Timeout = 5)
    try {
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        $asyncResult = $tcpClient.BeginConnect($HostName, $Port, $null, $null)
        $wait = $asyncResult.AsyncWaitHandle.WaitOne($Timeout * 1000, $false)
        if ($wait) {
            $tcpClient.EndConnect($asyncResult)
            $tcpClient.Close()
            return $true
        } else {
            $tcpClient.Close()
            return $false
        }
    } catch {
        return $false
    }
}

function Test-ServiceHealth {
    param([string]$Url, [int]$Timeout = 10)
    try {
        $response = Invoke-WebRequest -Uri $Url -TimeoutSec $Timeout -UseBasicParsing -ErrorAction SilentlyContinue
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

# Check if Docker is running
function Test-DockerRunning {
    try {
        docker version | Out-Null
        return $true
    } catch {
        return $false
    }
}

# Check required containers
function Test-RequiredContainers {
    Write-Log "Checking required Docker containers..."
    
    if (-not (Test-DockerRunning)) {
        Write-Log "Docker is not running. Please start Rancher Desktop first." "ERROR"
        return $false
    }

    $runningContainers = docker ps --format "table {{.Names}}" | Select-Object -Skip 1
    $missingContainers = @()

    foreach ($containerName in $RequiredContainers.Keys) {
        if ($runningContainers -notcontains $containerName) {
            $missingContainers += $containerName
        } else {
            $config = $RequiredContainers[$containerName]
            if ($config.Port) {
                if (Test-Port -Port $config.Port) {
                    Write-Log "[OK] $containerName is running and accessible on port $($config.Port)" "SUCCESS"
                } else {
                    Write-Log "[WARN] $containerName is running but port $($config.Port) is not accessible" "WARN"
                }
            }
        }
    }

    if ($missingContainers.Count -gt 0) {
        Write-Log "Missing containers: $($missingContainers -join ', ')" "ERROR"
        Write-Log "Please start the required containers using:" "ERROR"
        Write-Log "  docker-compose up -d" "ERROR"
        Write-Log "Or use Rancher Desktop to start the containers." "ERROR"
        return $false
    }

    Write-Log "All required containers are running!" "SUCCESS"
    return $true
}

# Start a service
function Start-Service {
    param([string]$ServiceName, [hashtable]$Config)
    
    Write-Log "Starting $ServiceName..."
    
    $servicePath = Join-Path $PWD $Config.Path
    if (-not (Test-Path $servicePath)) {
        Write-Log "Service path not found: $servicePath" "ERROR"
        return $null
    }

    try {
        $process = Start-Process -FilePath "pwsh" -ArgumentList "-Command", "cd '$servicePath'; $($Config.Command)" -PassThru -WindowStyle Hidden
        Write-Log "Started $ServiceName (PID: $($process.Id))"
        return $process
    } catch {
        Write-Log "Failed to start ${ServiceName}: $($_.Exception.Message)" "ERROR"
        return $null
    }
}

# Wait for service to be healthy
function Wait-ForServiceHealth {
    param([string]$ServiceName, [hashtable]$Config, [int]$MaxWaitSeconds)
    
    $healthUrl = "http://localhost:$($Config.Port)$($Config.HealthPath)"
    $elapsed = 0
    $checkInterval = 5

    Write-Log "Waiting for $ServiceName to be healthy (max ${MaxWaitSeconds}s)..."
    
    while ($elapsed -lt $MaxWaitSeconds) {
        if (Test-ServiceHealth -Url $healthUrl) {
            Write-Log "[OK] $ServiceName is healthy!" "SUCCESS"
            return $true
        }

        Start-Sleep $checkInterval
        $elapsed += $checkInterval
        Write-Log "[WAIT] Waiting for $ServiceName... (${elapsed}s/${MaxWaitSeconds}s)"
    }

    Write-Log "[ERROR] $ServiceName failed to become healthy within ${MaxWaitSeconds}s" "ERROR"
    return $false
}

# Check frontend compilation errors
function Test-FrontendCompilation {
    Write-Log "Checking frontend compilation..."
    
    try {
        $frontendPath = Join-Path $PWD "frontend"
        Set-Location $frontendPath
        
        $result = npx tsc --noEmit 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Log "[OK] Frontend compilation successful!" "SUCCESS"
            return $true
        } else {
            Write-Log "[ERROR] Frontend compilation errors found:" "ERROR"
            Write-Log $result "ERROR"
            return $false
        }
    } catch {
        Write-Log "Failed to check frontend compilation: $($_.Exception.Message)" "ERROR"
        return $false
    } finally {
        Set-Location $PWD
    }
}

# Main execution
function Start-Platform {
    Write-Log "Starting Nagarro's Ascent Platform (Development Mode)" "SUCCESS"
    Write-Log "=================================================="
    
    # Check containers unless skipped
    if (-not $SkipContainerCheck) {
        if (-not (Test-RequiredContainers)) {
            Write-Log "[ERROR] Container check failed. Exiting." "ERROR"
            exit 1
        }
    } else {
        Write-Log "[WARN] Skipping container check as requested" "WARN"
    }

    # Check frontend compilation first
    if (-not (Test-FrontendCompilation)) {
        Write-Log "[ERROR] Frontend compilation failed. Please fix errors before starting." "ERROR"
        exit 1
    }

    # Start services in order
    $serviceProcesses = @{}
    
    foreach ($serviceName in $Services.Keys) {
        $config = $Services[$serviceName]
        $process = Start-Service -ServiceName $serviceName -Config $config
        
        if ($process) {
            $serviceProcesses[$serviceName] = $process
            
            # Wait for service to be healthy
            if (-not (Wait-ForServiceHealth -ServiceName $serviceName -Config $config -MaxWaitSeconds $config.StartupTime)) {
                Write-Log "[ERROR] Failed to start $serviceName. Stopping all services." "ERROR"
                
                # Stop all started services
                foreach ($proc in $serviceProcesses.Values) {
                    if (-not $proc.HasExited) {
                        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
                    }
                }
                exit 1
            }
        } else {
            Write-Log "[ERROR] Failed to start $serviceName. Exiting." "ERROR"
            exit 1
        }
        
        Start-Sleep 2  # Brief pause between services
    }

    Write-Log "[SUCCESS] Platform started successfully!" "SUCCESS"
    Write-Log "=================================================="
    Write-Log "Services running:"
    foreach ($serviceName in $Services.Keys) {
        $config = $Services[$serviceName]
        Write-Log "  * ${serviceName}: http://localhost:$($config.Port)" "SUCCESS"
    }
    Write-Log ""
    Write-Log "Frontend: http://localhost:3000" "SUCCESS"
    Write-Log "Backend API: http://localhost:8000" "SUCCESS"
    Write-Log ""
    Write-Log "Press Ctrl+C to stop all services"
    
    # Keep script running and monitor services
    try {
        while ($true) {
            Start-Sleep 10
            # Check if any service has died
            foreach ($serviceName in $serviceProcesses.Keys) {
                $process = $serviceProcesses[$serviceName]
                if ($process.HasExited) {
                    Write-Log "[ERROR] $serviceName has stopped unexpectedly (Exit Code: $($process.ExitCode))" "ERROR"
                }
            }
        }
    } catch {
        Write-Log "Stopping all services..." "WARN"
        foreach ($process in $serviceProcesses.Values) {
            if (-not $process.HasExited) {
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

# Execute main function
Start-Platform
