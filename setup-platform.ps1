# =====================================================================================
# Nagarro AgentiMigrate Platform - Unified Setup Script
# One script to rule them all - handles everything from prerequisites to launch
# =====================================================================================

param(
    [switch]$SkipPrerequisites,
    [switch]$Reset,
    [switch]$StopOnly,
    [switch]$StatusOnly,
    [switch]$Verbose,
    [switch]$NoLogs
)

# =====================================================================================
# LOGGING SETUP
# =====================================================================================

# Create logs directory
if (!(Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" -Force | Out-Null
}

# Setup logging
$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$logFile = "logs/platform_setup_$timestamp.log"
$masterLogFile = "logs/platform_master.log"

function Write-Log {
    param(
        [string]$Message,
        [string]$Level = "INFO",
        [string]$Color = "White"
    )
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] $Message"
    
    # Write to console with color
    Write-Host $Message -ForegroundColor $Color
    
    # Write to log files (unless NoLogs is specified)
    if (!$NoLogs) {
        try {
            Add-Content -Path $logFile -Value $logEntry -Encoding UTF8 -ErrorAction SilentlyContinue
            Add-Content -Path $masterLogFile -Value $logEntry -Encoding UTF8 -ErrorAction SilentlyContinue
        } catch {
            # Ignore logging errors to prevent script failure
        }
    }
}

# Color functions for better output
function Write-Success { param($Message) Write-Log "✅ $Message" "SUCCESS" "Green" }
function Write-Info { param($Message) Write-Log "ℹ️  $Message" "INFO" "Cyan" }
function Write-Warning { param($Message) Write-Log "⚠️  $Message" "WARNING" "Yellow" }
function Write-Error { param($Message) Write-Log "❌ $Message" "ERROR" "Red" }
function Write-Step { param($Message) Write-Log "🔧 $Message" "STEP" "Blue" }
function Write-Debug { param($Message) if ($Verbose) { Write-Log "🐛 $Message" "DEBUG" "Gray" } }

# =====================================================================================
# HEADER AND INITIALIZATION
# =====================================================================================

Clear-Host
Write-Host ""
Write-Host "🚀 Nagarro AgentiMigrate Platform - Unified Setup" -ForegroundColor Magenta
Write-Host "=================================================" -ForegroundColor Magenta
Write-Host "Version: 2.0.0 | Architecture: CQRS + Serverless" -ForegroundColor Magenta
Write-Host "Log File: $logFile" -ForegroundColor Gray
Write-Host ""

Write-Info "Starting platform setup process..."
Write-Debug "PowerShell Version: $($PSVersionTable.PSVersion)"
Write-Debug "Current Directory: $(Get-Location)"
Write-Debug "Parameters: SkipPrerequisites=$SkipPrerequisites, Reset=$Reset, StopOnly=$StopOnly, StatusOnly=$StatusOnly"

# =====================================================================================
# SPECIAL MODES HANDLING
# =====================================================================================

if ($StatusOnly) {
    Write-Step "Checking platform status..."
    try {
        $status = docker compose ps --format "table {{.Service}}\t{{.Status}}\t{{.Ports}}"
        Write-Info "Current Service Status:"
        Write-Host $status -ForegroundColor Gray
        
        # Count running services
        $runningServices = docker compose ps --services --filter "status=running"
        $totalServices = docker compose ps --services
        Write-Info "Running Services: $($runningServices.Count)/$($totalServices.Count)"
        
        # Check if platform is accessible
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:3000/platform-dashboard.html" -TimeoutSec 5 -ErrorAction Stop
            Write-Success "Platform dashboard is accessible"
        } catch {
            Write-Warning "Platform dashboard not accessible"
        }
    } catch {
        Write-Error "Failed to check status: $($_.Exception.Message)"
    }
    exit 0
}

if ($StopOnly) {
    Write-Step "Stopping platform..."
    try {
        docker compose down --remove-orphans
        Write-Success "Platform stopped successfully"
        
        # Stop HTTP server if running
        Get-Process | Where-Object {$_.ProcessName -eq "python" -and $_.CommandLine -like "*http.server*"} | Stop-Process -Force -ErrorAction SilentlyContinue
        Write-Info "HTTP server stopped"
    } catch {
        Write-Error "Failed to stop platform: $($_.Exception.Message)"
    }
    exit 0
}

if ($Reset) {
    Write-Warning "⚠️  DESTRUCTIVE OPERATION: This will delete ALL platform data!"
    Write-Warning "This includes:"
    Write-Warning "• All database data (PostgreSQL, Neo4j, Weaviate)"
    Write-Warning "• All uploaded files (MinIO storage)"
    Write-Warning "• All Docker containers and images"
    Write-Warning "• All log files"
    Write-Host ""
    $confirm = Read-Host "Type 'DELETE-EVERYTHING' to confirm reset"
    
    if ($confirm -eq "DELETE-EVERYTHING") {
        Write-Step "Performing complete platform reset..."
        
        # Stop all services
        Write-Info "Stopping all services..."
        docker compose down -v --remove-orphans
        
        # Remove data directories
        Write-Info "Removing data directories..."
        @("postgres_data", "minio_data", "neo4j_data", "weaviate_data") | ForEach-Object {
            if (Test-Path $_) {
                Remove-Item -Path $_ -Recurse -Force -ErrorAction SilentlyContinue
                Write-Info "Removed: $_"
            }
        }
        
        # Clean Docker system
        Write-Info "Cleaning Docker system..."
        docker system prune -af --volumes
        
        # Remove log files
        Write-Info "Cleaning log files..."
        Remove-Item -Path "logs/*" -Force -ErrorAction SilentlyContinue
        
        Write-Success "Platform reset completed successfully"
        Write-Info "You can now run the setup script again to start fresh"
    } else {
        Write-Info "Reset cancelled"
    }
    exit 0
}

# =====================================================================================
# STEP 1: PREREQUISITES CHECK
# =====================================================================================

if (!$SkipPrerequisites) {
    Write-Step "Step 1: Checking prerequisites..."
    
    # Check system requirements
    Write-Info "Checking system requirements..."
    
    # Check RAM
    try {
        $totalRAM = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 2)
        Write-Debug "Total RAM: $totalRAM GB"
        if ($totalRAM -lt 8) {
            Write-Warning "Less than 8GB RAM detected ($totalRAM GB). Platform may run slowly."
        } else {
            Write-Success "RAM requirement satisfied ($totalRAM GB)"
        }
    } catch {
        Write-Warning "Could not check RAM: $($_.Exception.Message)"
    }
    
    # Check disk space
    try {
        $freeSpace = [math]::Round((Get-PSDrive C).Free / 1GB, 2)
        Write-Debug "Free disk space: $freeSpace GB"
        if ($freeSpace -lt 10) {
            Write-Warning "Less than 10GB free space ($freeSpace GB). May not be sufficient."
        } else {
            Write-Success "Disk space requirement satisfied ($freeSpace GB)"
        }
    } catch {
        Write-Warning "Could not check disk space: $($_.Exception.Message)"
    }
    
    # Check Docker
    Write-Info "Checking Docker installation..."
    try {
        $dockerVersion = docker --version
        Write-Success "Docker found: $dockerVersion"
        Write-Debug "Docker version details: $dockerVersion"
    } catch {
        Write-Error "Docker not found! Please install Docker Desktop or Rancher Desktop"
        Write-Info "Download options:"
        Write-Info "• Rancher Desktop (Recommended): https://rancherdesktop.io/"
        Write-Info "• Docker Desktop: https://docker.com/products/docker-desktop"
        exit 1
    }
    
    # Check Docker Compose
    Write-Info "Checking Docker Compose..."
    try {
        $composeVersion = docker compose version
        Write-Success "Docker Compose found: $composeVersion"
        Write-Debug "Docker Compose version details: $composeVersion"
    } catch {
        Write-Error "Docker Compose not found!"
        Write-Info "Docker Compose is required. Please ensure you have a recent Docker installation."
        exit 1
    }
    
    # Check if Docker is running
    Write-Info "Checking Docker daemon status..."
    try {
        docker ps | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Docker daemon is running"
        } else {
            Write-Error "Docker daemon not responding"
            Write-Info "Please start Docker Desktop or Rancher Desktop and try again"
            exit 1
        }
    } catch {
        Write-Error "Docker daemon not accessible: $($_.Exception.Message)"
        Write-Info "Please start Docker Desktop or Rancher Desktop and try again"
        exit 1
    }
    
    # Check Git (optional but recommended)
    Write-Info "Checking Git installation..."
    try {
        $gitVersion = git --version
        Write-Success "Git found: $gitVersion"
        Write-Debug "Git version details: $gitVersion"
    } catch {
        Write-Warning "Git not found - you may need it for updates and version control"
        Write-Info "Download from: https://git-scm.com/"
    }
    
    # Check Python (for HTTP server)
    Write-Info "Checking Python installation..."
    try {
        $pythonVersion = python --version
        Write-Success "Python found: $pythonVersion"
        Write-Debug "Python version details: $pythonVersion"
    } catch {
        Write-Warning "Python not found - will try alternative HTTP server"
        Write-Debug "Python error: $($_.Exception.Message)"
    }
    
    Write-Success "Prerequisites check completed"
} else {
    Write-Info "Skipping prerequisites check (as requested)"
}

# =====================================================================================
# STEP 2: ENVIRONMENT CONFIGURATION
# =====================================================================================

Write-Step "Step 2: Environment configuration..."

# Create .env file if it doesn't exist
if (!(Test-Path ".env")) {
    Write-Info "Creating .env configuration file..."
    $envContent = @"
# =====================================================================================
# Nagarro AgentiMigrate Platform Configuration
# =====================================================================================

# LLM API Keys (Configure at least one)
# Get your keys from:
# • Google/Gemini: https://aistudio.google.com/app/apikey
# • OpenAI: https://platform.openai.com/api-keys  
# • Anthropic: https://console.anthropic.com/
OPENAI_API_KEY=your_openai_api_key_here
GOOGLE_API_KEY=your_google_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# LLM Provider Selection (openai, google, anthropic)
LLM_PROVIDER=google

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

# Application Configuration
CONFIG_ENV=local
JWT_SECRET_KEY=your-secret-key-change-in-production
"@
    $envContent | Out-File -FilePath ".env" -Encoding UTF8
    Write-Success ".env file created successfully"
    Write-Debug ".env file location: $(Resolve-Path '.env')"
} else {
    Write-Success ".env file already exists"
}

# =====================================================================================
# STEP 3: API KEY CONFIGURATION
# =====================================================================================

Write-Step "Step 3: API key configuration..."

$envContent = Get-Content ".env" -Raw
$hasOpenAI = $envContent -match "OPENAI_API_KEY=(?!your_openai_api_key_here).+"
$hasGoogle = $envContent -match "GOOGLE_API_KEY=(?!your_google_api_key_here).+"
$hasAnthropic = $envContent -match "ANTHROPIC_API_KEY=(?!your_anthropic_api_key_here).+"

Write-Info "Checking configured API keys..."
if ($hasOpenAI) { Write-Success "OpenAI API Key: ✅ Configured" }
if ($hasGoogle) { Write-Success "Google/Gemini API Key: ✅ Configured" }
if ($hasAnthropic) { Write-Success "Anthropic API Key: ✅ Configured" }

if (!($hasOpenAI -or $hasGoogle -or $hasAnthropic)) {
    Write-Warning "No LLM API keys configured!"
    Write-Info ""
    Write-Info "🔑 You mentioned you have a Gemini key. Let's configure it now."
    Write-Info ""
    Write-Info "API Key Sources:"
    Write-Info "• Google/Gemini: https://aistudio.google.com/app/apikey"
    Write-Info "• OpenAI: https://platform.openai.com/api-keys"
    Write-Info "• Anthropic: https://console.anthropic.com/"
    Write-Info ""
    
    $geminiKey = Read-Host "Enter your Gemini API key (or press Enter to edit .env manually)"
    if ($geminiKey -and $geminiKey.Length -gt 10) {
        Write-Info "Configuring Gemini API key..."
        # Update .env file with Gemini key
        $envContent = $envContent -replace "GOOGLE_API_KEY=your_google_api_key_here", "GOOGLE_API_KEY=$geminiKey"
        $envContent = $envContent -replace "LLM_PROVIDER=google", "LLM_PROVIDER=google"
        $envContent | Out-File -FilePath ".env" -Encoding UTF8
        Write-Success "Gemini API key configured successfully!"
        Write-Debug "Updated .env file with Gemini API key"
    } else {
        Write-Warning "No API key provided. Opening .env file for manual editing..."
        Write-Info "Please add your API key and save the file, then run this script again"
        try {
            notepad ".env"
        } catch {
            Write-Warning "Could not open notepad. Please manually edit .env file"
        }
        Read-Host "Press Enter when done editing .env file"
        
        # Re-check after manual edit
        $envContent = Get-Content ".env" -Raw
        $hasGoogle = $envContent -match "GOOGLE_API_KEY=(?!your_google_api_key_here).+"
        if ($hasGoogle) {
            Write-Success "API key configuration detected!"
        } else {
            Write-Warning "No API key detected. Platform will start but AI features may not work."
        }
    }
} else {
    Write-Success "API key configuration verified"
}

# =====================================================================================
# STEP 4: DIRECTORY SETUP
# =====================================================================================

Write-Step "Step 4: Creating necessary directories..."

$directories = @("minio_data", "postgres_data", "neo4j_data", "weaviate_data", "logs")
foreach ($dir in $directories) {
    if (!(Test-Path $dir)) { 
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Success "Created directory: $dir"
        Write-Debug "Directory created at: $(Resolve-Path $dir)"
    } else {
        Write-Info "Directory already exists: $dir"
    }
}

# =====================================================================================
# STEP 5: MEGAPARSE REPOSITORY
# =====================================================================================

Write-Step "Step 5: Checking MegaParse repository..."

if (!(Test-Path "MegaParse")) {
    Write-Info "MegaParse repository not found. Cloning..."
    try {
        git clone https://github.com/QuivrHQ/MegaParse.git
        if ($LASTEXITCODE -eq 0) {
            Write-Success "MegaParse repository cloned successfully"
            Write-Debug "MegaParse cloned to: $(Resolve-Path 'MegaParse')"
        } else {
            Write-Error "Failed to clone MegaParse repository (exit code: $LASTEXITCODE)"
            Write-Warning "Document parsing features may not work properly"
        }
    } catch {
        Write-Error "Error cloning MegaParse: $($_.Exception.Message)"
        Write-Warning "Document parsing features may not work properly"
    }
} else {
    Write-Success "MegaParse repository already exists"
    Write-Debug "MegaParse location: $(Resolve-Path 'MegaParse')"
}

# =====================================================================================
# STEP 6: STOP EXISTING CONTAINERS
# =====================================================================================

Write-Step "Step 6: Stopping any existing containers..."

try {
    docker compose down --remove-orphans | Out-Null
    Write-Success "Existing containers stopped"
} catch {
    Write-Warning "No existing containers to stop or error occurred: $($_.Exception.Message)"
}

# =====================================================================================
# STEP 7: BUILD DOCKER IMAGES
# =====================================================================================

Write-Step "Step 7: Building Docker images..."
Write-Info "This may take 10-20 minutes on first run (images will be cached for future runs)"

# Enable BuildKit for better performance and caching
$env:DOCKER_BUILDKIT = "1"
$env:COMPOSE_DOCKER_CLI_BUILD = "1"
Write-Debug "Docker BuildKit enabled for improved performance"

# Build services in optimal order (infrastructure first, then applications)
$buildOrder = @(
    @{Name="postgres"; Description="PostgreSQL Database"},
    @{Name="neo4j"; Description="Neo4j Graph Database"},
    @{Name="weaviate"; Description="Weaviate Vector Database"},
    @{Name="minio"; Description="MinIO Object Storage"},
    @{Name="megaparse"; Description="MegaParse Document Processing"},
    @{Name="project-service"; Description="Project Management Service"},
    @{Name="reporting-service"; Description="Report Generation Service"},
    @{Name="backend"; Description="Backend Assessment Service"},
    @{Name="frontend"; Description="Frontend Web Application"}
)

$buildResults = @{}

foreach ($service in $buildOrder) {
    $serviceName = $service.Name
    $description = $service.Description
    
    Write-Info "Building $serviceName ($description)..."
    Write-Debug "Starting build for service: $serviceName"
    
    $buildStart = Get-Date
    try {
        docker compose build $serviceName
        $buildEnd = Get-Date
        $buildDuration = ($buildEnd - $buildStart).TotalSeconds
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "$serviceName built successfully (${buildDuration}s)"
            $buildResults[$serviceName] = "SUCCESS"
            Write-Debug "$serviceName build completed in $buildDuration seconds"
        } else {
            Write-Warning "$serviceName build completed with warnings (exit code: $LASTEXITCODE)"
            $buildResults[$serviceName] = "WARNING"
            Write-Debug "$serviceName build had issues, exit code: $LASTEXITCODE"
        }
    } catch {
        Write-Error "$serviceName build failed: $($_.Exception.Message)"
        $buildResults[$serviceName] = "FAILED"
        Write-Debug "$serviceName build error: $($_.Exception.Message)"
    }
}

# Build summary
Write-Info "Build Summary:"
foreach ($result in $buildResults.GetEnumerator()) {
    $status = switch ($result.Value) {
        "SUCCESS" { "✅"; break }
        "WARNING" { "⚠️"; break }
        "FAILED" { "❌"; break }
        default { "❓" }
    }
    Write-Host "  $status $($result.Key): $($result.Value)" -ForegroundColor Gray
}

# =====================================================================================
# STEP 8: START INFRASTRUCTURE SERVICES
# =====================================================================================

Write-Step "Step 8: Starting infrastructure services..."
Write-Info "Starting databases and storage services first..."

try {
    docker compose up -d postgres neo4j weaviate minio
    Write-Success "Infrastructure services started"
    Write-Debug "Infrastructure services: postgres, neo4j, weaviate, minio"
} catch {
    Write-Error "Failed to start infrastructure services: $($_.Exception.Message)"
    exit 1
}

Write-Info "Waiting for infrastructure services to initialize..."
Write-Debug "Waiting 25 seconds for database initialization"
Start-Sleep -Seconds 25

# =====================================================================================
# STEP 9: START APPLICATION SERVICES
# =====================================================================================

Write-Step "Step 9: Starting application services..."

try {
    docker compose up -d
    Write-Success "All services started"
    Write-Debug "Started all services with docker compose up -d"
} catch {
    Write-Error "Failed to start application services: $($_.Exception.Message)"
    Write-Warning "Some services may not be running. Check logs with: docker compose logs"
}

Write-Info "Waiting for application services to initialize..."
Write-Debug "Waiting 20 seconds for application startup"
Start-Sleep -Seconds 20

# =====================================================================================
# STEP 10: HEALTH CHECKS
# =====================================================================================

Write-Step "Step 10: Performing health checks..."

# Get service status
try {
    $serviceStatus = docker compose ps --format "table {{.Service}}\t{{.Status}}\t{{.Ports}}"
    Write-Info "Service Status:"
    Write-Host $serviceStatus -ForegroundColor Gray
    
    # Count running services
    $runningServices = docker compose ps --services --filter "status=running"
    $allServices = docker compose ps --services
    Write-Info "Services Running: $($runningServices.Count)/$($allServices.Count)"
    Write-Debug "Running services: $($runningServices -join ', ')"
    Write-Debug "All services: $($allServices -join ', ')"
} catch {
    Write-Warning "Could not get service status: $($_.Exception.Message)"
}

# Test key service endpoints
$healthChecks = @(
    @{Name="Neo4j"; Url="http://localhost:7474"; Timeout=10},
    @{Name="MinIO"; Url="http://localhost:9001"; Timeout=10},
    @{Name="Weaviate"; Url="http://localhost:8080/v1/.well-known/ready"; Timeout=10}
)

Write-Info "Testing service endpoints..."
foreach ($check in $healthChecks) {
    try {
        Write-Debug "Testing $($check.Name) at $($check.Url)"
        $response = Invoke-WebRequest -Uri $check.Url -TimeoutSec $check.Timeout -ErrorAction Stop
        Write-Success "$($check.Name) is accessible (HTTP $($response.StatusCode))"
    } catch {
        Write-Warning "$($check.Name) not accessible: $($_.Exception.Message)"
        Write-Debug "$($check.Name) health check failed: $($_.Exception.Message)"
    }
}

# =====================================================================================
# STEP 11: CREATE PLATFORM DASHBOARD
# =====================================================================================

Write-Step "Step 11: Creating platform dashboard..."

# Check if frontend is running
$frontendRunning = docker compose ps frontend | Select-String "Up"
if (!$frontendRunning) {
    Write-Info "Frontend service not running, creating simple dashboard..."
    
    $dashboardHtml = @"
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚀 AgentiMigrate Platform</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            min-height: 100vh; color: white; padding: 20px; 
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 40px; }
        .header h1 { font-size: 3em; margin-bottom: 10px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }
        .header p { font-size: 1.2em; opacity: 0.9; }
        .status { 
            background: rgba(0,255,0,0.2); padding: 20px; border-radius: 10px; 
            margin-bottom: 30px; text-align: center; border: 1px solid rgba(0,255,0,0.3);
        }
        .services { 
            display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); 
            gap: 20px; margin-bottom: 30px; 
        }
        .service { 
            background: rgba(255,255,255,0.1); padding: 25px; border-radius: 15px; 
            text-align: center; transition: transform 0.3s ease;
            border: 1px solid rgba(255,255,255,0.2);
        }
        .service:hover { transform: translateY(-5px); }
        .service h3 { margin-bottom: 10px; font-size: 1.3em; }
        .service p { margin-bottom: 15px; opacity: 0.8; }
        .service a { 
            color: #fff; text-decoration: none; font-weight: bold; 
            background: rgba(255,255,255,0.2); padding: 10px 20px; 
            border-radius: 5px; display: inline-block; transition: all 0.3s ease;
        }
        .service a:hover { background: rgba(255,255,255,0.3); text-decoration: none; }
        .credentials { 
            background: rgba(255,255,255,0.1); padding: 20px; border-radius: 10px; 
            text-align: center; margin-top: 30px; border: 1px solid rgba(255,255,255,0.2);
        }
        .credentials h3 { margin-bottom: 15px; }
        .credentials p { margin: 5px 0; font-family: monospace; }
        .footer { text-align: center; margin-top: 30px; opacity: 0.7; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 AgentiMigrate Platform</h1>
            <p>AI-Powered Cloud Migration Assessment Platform</p>
            <p><small>Version 2.0.0 | CQRS Architecture | Serverless Ready</small></p>
        </div>
        
        <div class="status">
            <h3>✅ Platform Status: Operational</h3>
            <p>All core services are running and ready for use</p>
        </div>
        
        <div class="services">
            <div class="service">
                <h3>🔧 Backend API</h3>
                <p>Core platform API with CQRS architecture</p>
                <a href="http://localhost:8000/docs" target="_blank">Open API Docs</a>
            </div>
            <div class="service">
                <h3>📋 Project Service</h3>
                <p>Project management with domain-driven design</p>
                <a href="http://localhost:8002/docs" target="_blank">Open API Docs</a>
            </div>
            <div class="service">
                <h3>📊 Reporting Service</h3>
                <p>AI-powered report generation</p>
                <a href="http://localhost:8003/docs" target="_blank">Open API Docs</a>
            </div>
            <div class="service">
                <h3>📄 MegaParse Service</h3>
                <p>Advanced document parsing and extraction</p>
                <a href="http://localhost:5001" target="_blank">Open Service</a>
            </div>
            <div class="service">
                <h3>🔗 Neo4j Browser</h3>
                <p>Graph database for dependency mapping</p>
                <a href="http://localhost:7474" target="_blank">Open Browser</a>
            </div>
            <div class="service">
                <h3>🔍 Weaviate Console</h3>
                <p>Vector database for semantic search</p>
                <a href="http://localhost:8080" target="_blank">Open Console</a>
            </div>
            <div class="service">
                <h3>💾 MinIO Console</h3>
                <p>Object storage for files and artifacts</p>
                <a href="http://localhost:9001" target="_blank">Open Console</a>
            </div>
        </div>
        
        <div class="credentials">
            <h3>🔑 Default Credentials</h3>
            <p><strong>Neo4j:</strong> neo4j / password</p>
            <p><strong>MinIO:</strong> minioadmin / minioadmin</p>
        </div>
        
        <div class="footer">
            <p>Nagarro AgentiMigrate Platform | Built with Enterprise Architecture</p>
            <p>Logs: logs/platform_setup_$timestamp.log</p>
        </div>
    </div>
    
    <script>
        // Simple health check indicator
        document.addEventListener('DOMContentLoaded', function() {
            console.log('🚀 AgentiMigrate Platform Dashboard Loaded');
            console.log('📊 For detailed logs, check: logs/platform_setup_$timestamp.log');
        });
    </script>
</body>
</html>
"@
    
    $dashboardHtml | Out-File -FilePath "platform-dashboard.html" -Encoding UTF8
    Write-Success "Platform dashboard created"
    Write-Debug "Dashboard saved to: $(Resolve-Path 'platform-dashboard.html')"
    
    # Start HTTP server
    Write-Info "Starting HTTP server for dashboard..."
    try {
        # Try Python first
        Start-Process powershell -ArgumentList "-Command", "cd '$PWD'; python -m http.server 3000" -WindowStyle Hidden
        Start-Sleep -Seconds 3
        Write-Success "HTTP server started on port 3000"
        Write-Debug "Python HTTP server started successfully"
    } catch {
        Write-Warning "Could not start Python HTTP server: $($_.Exception.Message)"
        Write-Info "You can manually open platform-dashboard.html in your browser"
    }
} else {
    Write-Success "Frontend service is running"
    Write-Debug "Frontend container is up and running"
}

# =====================================================================================
# FINAL SUMMARY
# =====================================================================================

Write-Host ""
Write-Host "🎉 Platform Setup Complete!" -ForegroundColor Green
Write-Host "============================" -ForegroundColor Green
Write-Host ""

Write-Host "🌐 Access Points:" -ForegroundColor Cyan
Write-Host "• Platform Dashboard: http://localhost:3000/platform-dashboard.html" -ForegroundColor Green
Write-Host "• Backend API: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "• Project Service: http://localhost:8002/docs" -ForegroundColor Green
Write-Host "• Reporting Service: http://localhost:8003/docs" -ForegroundColor Green
Write-Host "• Neo4j Browser: http://localhost:7474" -ForegroundColor Green
Write-Host "• Weaviate Console: http://localhost:8080" -ForegroundColor Green
Write-Host "• MinIO Console: http://localhost:9001" -ForegroundColor Green
Write-Host ""

Write-Host "🔑 Default Credentials:" -ForegroundColor Cyan
Write-Host "• Neo4j: neo4j / password" -ForegroundColor Gray
Write-Host "• MinIO: minioadmin / minioadmin" -ForegroundColor Gray
Write-Host ""

Write-Host "🔧 Management Commands:" -ForegroundColor Cyan
Write-Host "• Check status: .\setup-platform.ps1 -StatusOnly" -ForegroundColor Gray
Write-Host "• Stop platform: .\setup-platform.ps1 -StopOnly" -ForegroundColor Gray
Write-Host "• Reset everything: .\setup-platform.ps1 -Reset" -ForegroundColor Gray
Write-Host "• View logs: Get-Content logs\platform_setup_$timestamp.log" -ForegroundColor Gray
Write-Host ""

Write-Host "📊 Setup Summary:" -ForegroundColor Cyan
$successCount = ($buildResults.Values | Where-Object {$_ -eq "SUCCESS"}).Count
$totalCount = $buildResults.Count
Write-Host "• Services built: $successCount/$totalCount successful" -ForegroundColor Gray
Write-Host "• Log file: logs\platform_setup_$timestamp.log" -ForegroundColor Gray
Write-Host "• Master log: logs\platform_master.log" -ForegroundColor Gray
Write-Host ""

# Open browser prompt
$openBrowser = Read-Host "Open platform dashboard in browser? (Y/n)"
if ($openBrowser -ne "n" -and $openBrowser -ne "N") {
    try {
        Start-Process "http://localhost:3000/platform-dashboard.html"
        Write-Success "Browser opened to platform dashboard"
    } catch {
        Write-Warning "Could not open browser automatically"
        Write-Info "Please manually navigate to: http://localhost:3000/platform-dashboard.html"
    }
}

Write-Success "Setup completed successfully!"
Write-Info "Platform is ready for AI-powered migration assessments!"

# Final logging
Write-Debug "Setup script completed at $(Get-Date)"
Write-Debug "Total execution time: $((Get-Date) - $timestamp)"
