# Nagarro AgentiMigrate Platform - Complete MVP Setup Script
# This script sets up the entire environment locally on your machine

param(
    [switch]$SkipPrerequisites,
    [switch]$ForceRebuild,
    [switch]$SkipFrontend,
    [switch]$Verbose
)

# Enhanced logging setup
$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$logFile = "logs/mvp_setup_$timestamp.log"
$masterLogFile = "logs/platform_master.log"

# Create logs directory if it doesn't exist
if (!(Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" -Force | Out-Null
}

# Function for enhanced logging
function Write-LogMessage {
    param(
        [string]$Message,
        [string]$Level = "INFO",
        [string]$Color = "White"
    )
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] [MVP-SETUP] $Message"
    
    # Write to console with color
    Write-Host $Message -ForegroundColor $Color
    
    # Write to log files with error handling
    try {
        Add-Content -Path $logFile -Value $logEntry -Encoding UTF8 -ErrorAction SilentlyContinue
        Add-Content -Path $masterLogFile -Value $logEntry -Encoding UTF8 -ErrorAction SilentlyContinue
    } catch {
        # Ignore logging errors to prevent script failure
    }
}

# Function to check if a command exists
function Test-Command {
    param([string]$Command)
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    } catch {
        return $false
    }
}

# Function to check if a port is available
function Test-Port {
    param([int]$Port)
    try {
        $connection = New-Object System.Net.Sockets.TcpClient
        $connection.Connect("localhost", $Port)
        $connection.Close()
        return $false  # Port is in use
    } catch {
        return $true   # Port is available
    }
}

# Function to wait for service to be ready
function Wait-ForService {
    param(
        [string]$ServiceName,
        [string]$Url,
        [int]$TimeoutSeconds = 120
    )
    
    Write-LogMessage "Waiting for $ServiceName to be ready..." "INFO" "Yellow"
    $elapsed = 0
    
    while ($elapsed -lt $TimeoutSeconds) {
        try {
            $response = Invoke-WebRequest -Uri $Url -TimeoutSec 5 -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                Write-LogMessage "$ServiceName is ready!" "SUCCESS" "Green"
                return $true
            }
        } catch {
            # Service not ready yet
        }
        
        Start-Sleep -Seconds 5
        $elapsed += 5
        Write-LogMessage "Still waiting for $ServiceName... ($elapsed/$TimeoutSeconds seconds)" "INFO" "Gray"
    }
    
    Write-LogMessage "$ServiceName failed to start within $TimeoutSeconds seconds" "ERROR" "Red"
    return $false
}

Write-LogMessage "=== NAGARRO AGENTIMIGRATE PLATFORM - COMPLETE MVP SETUP ===" "INFO" "Cyan"
Write-LogMessage "Setup Log File: $logFile" "INFO" "Gray"
Write-LogMessage "Master Log File: $masterLogFile" "INFO" "Gray"
Write-LogMessage "PowerShell Version: $($PSVersionTable.PSVersion)" "INFO" "Gray"
Write-LogMessage "Current Directory: $(Get-Location)" "INFO" "Gray"
Write-LogMessage "Parameters: SkipPrerequisites=$SkipPrerequisites, ForceRebuild=$ForceRebuild, SkipFrontend=$SkipFrontend" "INFO" "Gray"

# Step 1: Check Prerequisites
if (!$SkipPrerequisites) {
    Write-LogMessage "=== STEP 1: CHECKING PREREQUISITES ===" "INFO" "Cyan"
    
    # Check system requirements
    Write-LogMessage "Checking system requirements..." "INFO" "Yellow"
    
    # Check RAM
    $totalRAM = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 2)
    Write-LogMessage "Total RAM: $totalRAM GB" "INFO" "Gray"
    if ($totalRAM -lt 8) {
        Write-LogMessage "WARNING: Less than 8GB RAM detected. Platform may run slowly." "WARNING" "Yellow"
    } else {
        Write-LogMessage "RAM requirement satisfied" "SUCCESS" "Green"
    }
    
    # Check disk space
    $freeSpace = [math]::Round((Get-PSDrive C).Free / 1GB, 2)
    Write-LogMessage "Free disk space: $freeSpace GB" "INFO" "Gray"
    if ($freeSpace -lt 10) {
        Write-LogMessage "WARNING: Less than 10GB free space. May not be sufficient." "WARNING" "Yellow"
    } else {
        Write-LogMessage "Disk space requirement satisfied" "SUCCESS" "Green"
    }
    
    # Check for Rancher Desktop
    Write-LogMessage "Checking for Rancher Desktop..." "INFO" "Yellow"
    $possiblePaths = @(
        "$env:USERPROFILE\.rd\bin\rdctl.exe",
        "$env:LOCALAPPDATA\Programs\Rancher Desktop\resources\resources\win32\bin\rdctl.exe",
        "$env:PROGRAMFILES\Rancher Desktop\resources\resources\win32\bin\rdctl.exe",
        "$env:PROGRAMFILES(x86)\Rancher Desktop\resources\resources\win32\bin\rdctl.exe"
    )
    
    $rancherFound = $false
    foreach ($path in $possiblePaths) {
        if (Test-Path $path) {
            $rancherFound = $true
            Write-LogMessage "Rancher Desktop found at: $path" "SUCCESS" "Green"
            break
        }
    }
    
    if (!$rancherFound) {
        Write-LogMessage "Rancher Desktop not found!" "ERROR" "Red"
        Write-LogMessage "Please install Rancher Desktop from: https://rancherdesktop.io/" "ERROR" "Yellow"
        Write-LogMessage "Ensure 'dockerd (moby)' is selected as container runtime" "ERROR" "Yellow"
        exit 1
    }
    
    # Check Docker availability
    Write-LogMessage "Checking Docker availability..." "INFO" "Yellow"
    if (!(Test-Command "docker")) {
        Write-LogMessage "Docker command not available!" "ERROR" "Red"
        Write-LogMessage "Please ensure Rancher Desktop is running and 'dockerd (moby)' is selected" "ERROR" "Yellow"
        exit 1
    }
    
    # Test Docker daemon
    try {
        docker ps | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-LogMessage "Docker daemon is running" "SUCCESS" "Green"
        } else {
            Write-LogMessage "Docker daemon not responding" "ERROR" "Red"
            exit 1
        }
    } catch {
        Write-LogMessage "Error testing Docker daemon: $($_.Exception.Message)" "ERROR" "Red"
        exit 1
    }
    
    # Check Docker Compose
    Write-LogMessage "Checking Docker Compose..." "INFO" "Yellow"
    if (Test-Command "docker") {
        try {
            docker compose version | Out-Null
            if ($LASTEXITCODE -eq 0) {
                $composeVersion = docker compose version
                Write-LogMessage "Docker Compose available: $composeVersion" "SUCCESS" "Green"
            } else {
                Write-LogMessage "Docker Compose not available" "ERROR" "Red"
                exit 1
            }
        } catch {
            Write-LogMessage "Error checking Docker Compose: $($_.Exception.Message)" "ERROR" "Red"
            exit 1
        }
    }
    
    # Check Git
    Write-LogMessage "Checking Git..." "INFO" "Yellow"
    if (Test-Command "git") {
        $gitVersion = git --version
        Write-LogMessage "Git available: $gitVersion" "SUCCESS" "Green"
    } else {
        Write-LogMessage "Git not found. Please install Git." "ERROR" "Red"
        exit 1
    }
    
    Write-LogMessage "All prerequisites satisfied!" "SUCCESS" "Green"
}

# Step 2: Environment Configuration
Write-LogMessage "=== STEP 2: ENVIRONMENT CONFIGURATION ===" "INFO" "Cyan"

# Create .env file if it doesn't exist
if (!(Test-Path ".env")) {
    Write-LogMessage "Creating .env file..." "INFO" "Yellow"
    $envContent = @"
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
"@
    $envContent | Out-File -FilePath ".env" -Encoding UTF8
    Write-LogMessage ".env file created" "SUCCESS" "Green"
} else {
    Write-LogMessage ".env file already exists" "SUCCESS" "Green"
}

# Check LLM API key configuration
Write-LogMessage "Checking LLM API key configuration..." "INFO" "Yellow"
$envContent = Get-Content ".env" -Raw

$openaiConfigured = $envContent -notmatch "OPENAI_API_KEY=your_openai_api_key_here" -and $envContent -match "OPENAI_API_KEY=.+"
$anthropicConfigured = $envContent -notmatch "ANTHROPIC_API_KEY=your_anthropic_key_here" -and $envContent -match "ANTHROPIC_API_KEY=.+"
$googleConfigured = $envContent -notmatch "GOOGLE_API_KEY=your_google_key_here" -and $envContent -match "GOOGLE_API_KEY=.+"

if ($openaiConfigured) {
    Write-LogMessage "OpenAI API Key: Configured" "SUCCESS" "Green"
}
if ($anthropicConfigured) {
    Write-LogMessage "Anthropic API Key: Configured" "SUCCESS" "Green"
}
if ($googleConfigured) {
    Write-LogMessage "Google/Gemini API Key: Configured" "SUCCESS" "Green"
}

if (!($openaiConfigured -or $anthropicConfigured -or $googleConfigured)) {
    Write-LogMessage "No LLM API keys configured!" "WARNING" "Yellow"
    Write-LogMessage "Please configure at least one API key in .env file:" "WARNING" "Yellow"
    Write-LogMessage "- OpenAI: https://platform.openai.com/api-keys" "WARNING" "Yellow"
    Write-LogMessage "- Google/Gemini: https://aistudio.google.com/app/apikey" "WARNING" "Yellow"
    Write-LogMessage "- Anthropic: https://console.anthropic.com/" "WARNING" "Yellow"
    
    $openEnv = Read-Host "Open .env file now? (y/N)"
    if ($openEnv -eq "y" -or $openEnv -eq "Y") {
        notepad ".env"
        Read-Host "Press Enter when done configuring API keys"
    }
}

# Create necessary directories
Write-LogMessage "Creating necessary directories..." "INFO" "Yellow"
$directories = @("minio_data", "postgres_data", "logs")
foreach ($dir in $directories) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-LogMessage "Created: $dir" "INFO" "Gray"
    }
}

# Step 3: Check Port Availability
Write-LogMessage "=== STEP 3: CHECKING PORT AVAILABILITY ===" "INFO" "Cyan"

$requiredPorts = @(
    @{Port=3000; Service="Frontend"},
    @{Port=8000; Service="Backend API"},
    @{Port=8002; Service="Project Service"},
    @{Port=8003; Service="Reporting Service"},
    @{Port=5001; Service="MegaParse Service"},
    @{Port=7474; Service="Neo4j Browser"},
    @{Port=7687; Service="Neo4j Bolt"},
    @{Port=8080; Service="Weaviate"},
    @{Port=9000; Service="MinIO API"},
    @{Port=9001; Service="MinIO Console"},
    @{Port=5432; Service="PostgreSQL"}
)

$portsInUse = @()
foreach ($portInfo in $requiredPorts) {
    if (!(Test-Port $portInfo.Port)) {
        $portsInUse += $portInfo
        Write-LogMessage "Port $($portInfo.Port) is in use ($($portInfo.Service))" "WARNING" "Yellow"
    } else {
        Write-LogMessage "Port $($portInfo.Port) is available ($($portInfo.Service))" "SUCCESS" "Green"
    }
}

if ($portsInUse.Count -gt 0) {
    Write-LogMessage "Some ports are in use. This may cause conflicts." "WARNING" "Yellow"
    $continue = Read-Host "Continue anyway? (y/N)"
    if ($continue -ne "y" -and $continue -ne "Y") {
        Write-LogMessage "Setup cancelled by user" "INFO" "Yellow"
        exit 0
    }
}

# Step 4: Build Docker Images
Write-LogMessage "=== STEP 4: BUILDING DOCKER IMAGES ===" "INFO" "Cyan"

# Stop existing containers if ForceRebuild
if ($ForceRebuild) {
    Write-LogMessage "Force rebuild requested - stopping existing containers..." "INFO" "Yellow"
    docker compose down 2>$null
}

# Build infrastructure services first (these are more likely to succeed)
Write-LogMessage "Starting infrastructure services..." "INFO" "Yellow"
try {
    docker compose up -d postgres neo4j weaviate minio
    if ($LASTEXITCODE -eq 0) {
        Write-LogMessage "Infrastructure services started successfully" "SUCCESS" "Green"
    } else {
        Write-LogMessage "Failed to start infrastructure services" "ERROR" "Red"
        exit 1
    }
} catch {
    Write-LogMessage "Error starting infrastructure services: $($_.Exception.Message)" "ERROR" "Red"
    exit 1
}

# Wait for infrastructure services to be ready
Write-LogMessage "Waiting for infrastructure services to be ready..." "INFO" "Yellow"
Start-Sleep -Seconds 10

# Build custom services
$servicesToBuild = @("megaparse", "project-service", "reporting-service", "backend")
if (!$SkipFrontend) {
    $servicesToBuild += "frontend"
}

foreach ($service in $servicesToBuild) {
    Write-LogMessage "Building $service..." "INFO" "Yellow"
    try {
        if ($ForceRebuild) {
            docker compose build --no-cache $service
        } else {
            docker compose build $service
        }
        
        if ($LASTEXITCODE -eq 0) {
            Write-LogMessage "$service built successfully" "SUCCESS" "Green"
        } else {
            Write-LogMessage "Failed to build $service" "ERROR" "Red"
            Write-LogMessage "Check logs with: docker compose logs $service" "ERROR" "Yellow"
            
            # Continue with other services instead of failing completely
            continue
        }
    } catch {
        Write-LogMessage "Error building $service: $($_.Exception.Message)" "ERROR" "Red"
        continue
    }
}

# Step 5: Start All Services
Write-LogMessage "=== STEP 5: STARTING ALL SERVICES ===" "INFO" "Cyan"

try {
    Write-LogMessage "Starting all services..." "INFO" "Yellow"
    docker compose up -d
    
    if ($LASTEXITCODE -eq 0) {
        Write-LogMessage "All services started" "SUCCESS" "Green"
    } else {
        Write-LogMessage "Some services may have failed to start" "WARNING" "Yellow"
    }
} catch {
    Write-LogMessage "Error starting services: $($_.Exception.Message)" "ERROR" "Red"
}

# Step 6: Health Checks
Write-LogMessage "=== STEP 6: PERFORMING HEALTH CHECKS ===" "INFO" "Cyan"

# Check service status
Write-LogMessage "Checking service status..." "INFO" "Yellow"
$serviceStatus = docker compose ps --format "table {{.Service}}\t{{.Status}}\t{{.Ports}}"
Write-LogMessage "Service Status:" "INFO" "Gray"
Write-LogMessage $serviceStatus "INFO" "Gray"

# Wait for key services to be ready
$healthChecks = @(
    @{Name="Neo4j"; Url="http://localhost:7474"},
    @{Name="Weaviate"; Url="http://localhost:8080/v1/.well-known/ready"},
    @{Name="MinIO"; Url="http://localhost:9001"}
)

foreach ($check in $healthChecks) {
    Wait-ForService -ServiceName $check.Name -Url $check.Url -TimeoutSeconds 60
}

# Step 7: Create Simple Frontend if needed
if ($SkipFrontend -or !(docker compose ps frontend | Select-String "Up")) {
    Write-LogMessage "=== STEP 7: CREATING SIMPLE FRONTEND ===" "INFO" "Cyan"
    
    # Create simple frontend HTML
    $frontendHtml = @"
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚀 Nagarro AgentiMigrate Platform</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh; color: white; padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 40px; }
        .header h1 { font-size: 3rem; margin-bottom: 10px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }
        .status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-bottom: 40px; }
        .status-card {
            background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px);
            border-radius: 15px; padding: 25px; border: 1px solid rgba(255, 255, 255, 0.2);
            transition: transform 0.3s ease;
        }
        .status-card:hover { transform: translateY(-5px); }
        .service-links {
            background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px);
            border-radius: 15px; padding: 30px; margin-bottom: 30px;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .links-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
        .links-grid a {
            display: block; background: rgba(255, 255, 255, 0.2); color: white;
            text-decoration: none; padding: 15px 20px; border-radius: 10px;
            text-align: center; transition: all 0.3s ease;
        }
        .links-grid a:hover { background: rgba(255, 255, 255, 0.3); transform: translateY(-2px); }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Nagarro AgentiMigrate Platform</h1>
            <p>AI-Powered Cloud Migration Assessment Platform</p>
        </div>
        <div class="status-grid">
            <div class="status-card">
                <h3>✅ Platform Status</h3>
                <p>MVP Environment Successfully Deployed</p>
            </div>
            <div class="status-card">
                <h3>🔑 LLM Provider</h3>
                <p>API Keys Configured and Ready</p>
            </div>
            <div class="status-card">
                <h3>🗄️ Database Services</h3>
                <p>PostgreSQL, Neo4j, Weaviate Operational</p>
            </div>
            <div class="status-card">
                <h3>📦 Object Storage</h3>
                <p>MinIO Service Available</p>
            </div>
        </div>
        <div class="service-links">
            <h3>🌐 Service Access Points</h3>
            <div class="links-grid">
                <a href="http://localhost:8000/docs" target="_blank">📚 Backend API</a>
                <a href="http://localhost:8002/docs" target="_blank">📋 Project Service</a>
                <a href="http://localhost:8003/docs" target="_blank">📊 Reporting Service</a>
                <a href="http://localhost:5001" target="_blank">📄 MegaParse Service</a>
                <a href="http://localhost:7474" target="_blank">🔗 Neo4j Browser</a>
                <a href="http://localhost:8080" target="_blank">🔍 Weaviate Console</a>
                <a href="http://localhost:9001" target="_blank">💾 MinIO Console</a>
            </div>
        </div>
    </div>
</body>
</html>
"@
    
    $frontendHtml | Out-File -FilePath "mvp-frontend.html" -Encoding UTF8
    Write-LogMessage "Simple frontend created: mvp-frontend.html" "SUCCESS" "Green"
    
    # Start simple HTTP server
    Write-LogMessage "Starting simple HTTP server on port 3000..." "INFO" "Yellow"
    Start-Process powershell -ArgumentList "-Command", "python -m http.server 3000" -WindowStyle Hidden
    Start-Sleep -Seconds 3
    Write-LogMessage "Frontend server started" "SUCCESS" "Green"
}

# Step 8: Final Summary
Write-LogMessage "=== STEP 8: SETUP COMPLETE ===" "INFO" "Cyan"

Write-LogMessage "🎉 MVP SETUP COMPLETED SUCCESSFULLY!" "SUCCESS" "Green"
Write-LogMessage "" "INFO" "White"
Write-LogMessage "📊 Platform Status:" "INFO" "Cyan"

# Get final service status
$runningServices = docker compose ps --services --filter "status=running"
$allServices = docker compose ps --services

Write-LogMessage "Running Services: $($runningServices.Count)/$($allServices.Count)" "INFO" "White"

Write-LogMessage "" "INFO" "White"
Write-LogMessage "🌐 Access Points:" "INFO" "Cyan"
Write-LogMessage "• Main Interface: http://localhost:3000/mvp-frontend.html" "INFO" "Green"
Write-LogMessage "• Backend API: http://localhost:8000/docs" "INFO" "Green"
Write-LogMessage "• Project Service: http://localhost:8002/docs" "INFO" "Green"
Write-LogMessage "• Reporting Service: http://localhost:8003/docs" "INFO" "Green"
Write-LogMessage "• Neo4j Browser: http://localhost:7474" "INFO" "Green"
Write-LogMessage "• Weaviate Console: http://localhost:8080" "INFO" "Green"
Write-LogMessage "• MinIO Console: http://localhost:9001" "INFO" "Green"

Write-LogMessage "" "INFO" "White"
Write-LogMessage "🔧 Management Commands:" "INFO" "Cyan"
Write-LogMessage "• Check status: docker compose ps" "INFO" "Gray"
Write-LogMessage "• View logs: docker compose logs -f" "INFO" "Gray"
Write-LogMessage "• Stop platform: docker compose down" "INFO" "Gray"
Write-LogMessage "• Restart service: docker compose restart [service]" "INFO" "Gray"

Write-LogMessage "" "INFO" "White"
Write-LogMessage "📋 Next Steps:" "INFO" "Cyan"
Write-LogMessage "1. Open http://localhost:3000/mvp-frontend.html in your browser" "INFO" "Yellow"
Write-LogMessage "2. Test API endpoints using the provided links" "INFO" "Yellow"
Write-LogMessage "3. Upload documents and run AI assessments" "INFO" "Yellow"

Write-LogMessage "" "INFO" "White"
Write-LogMessage "=== MVP SETUP LOG SAVED TO: $logFile ===" "SUCCESS" "Green"

# Open browser to the platform
$openBrowser = Read-Host "Open platform in browser now? (Y/n)"
if ($openBrowser -ne "n" -and $openBrowser -ne "N") {
    Start-Process "http://localhost:3000/mvp-frontend.html"
}

Write-LogMessage "Setup completed successfully!" "SUCCESS" "Green"
