# =====================================================================================
# Optimized Platform Startup - Uses Pre-built Images
# =====================================================================================
# This script starts the platform using PRE-BUILT images for 2-3 minute startup
# Prerequisites: Run .\build-all.ps1 first to build the images
# =====================================================================================

[CmdletBinding()]
param (
    [switch]$StopOnly,        # Stop platform only
    [switch]$Restart,         # Restart platform
    [switch]$Minimal,         # Use minimal profile
    [string]$StartupProfile = "core" # Startup profile: minimal, core, full
)

Write-Host "Optimized Platform Startup" -ForegroundColor Cyan
Write-Host "==========================" -ForegroundColor Cyan

# Create logs directory
if (!(Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" -Force | Out-Null
}

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$logFile = "logs/startup_optimized_$timestamp.log"

function Write-Log {
    param($Message, $Color = "White")
    $timestampedMessage = "[$(Get-Date -Format 'HH:mm:ss')] $Message"
    Write-Host $timestampedMessage -ForegroundColor $Color
    $timestampedMessage | Out-File -FilePath $logFile -Append
}

# Determine Docker Compose command
if (Get-Command "docker" -ErrorAction SilentlyContinue) {
    try {
        docker compose version | Out-Null
        $DOCKER_COMPOSE = "docker compose"
    } catch {
        $DOCKER_COMPOSE = "docker-compose"
    }
} else {
    Write-Log "ERROR: Docker is not available. Please start Docker Desktop or Rancher Desktop." "Red"
    exit 1
}

Write-Log "INFO: Using $DOCKER_COMPOSE" "Gray"

# Handle stop-only request
if ($StopOnly) {
    Write-Log "INFO: Stopping platform..." "Yellow"
    & $DOCKER_COMPOSE.Split() down --remove-orphans
    Write-Log "SUCCESS: Platform stopped" "Green"
    exit 0
}

# Handle restart request
if ($Restart) {
    Write-Log "INFO: Restarting platform..." "Yellow"
    & $DOCKER_COMPOSE.Split() down --remove-orphans
    Start-Sleep -Seconds 3
}

# Override profile if Minimal flag is used
if ($Minimal) {
    $StartupProfile = "minimal"
}

# Define services for each profile
$serviceProfiles = @{
    "minimal" = @{
        Infrastructure = @("postgres", "neo4j", "minio")
        Applications = @("frontend", "project-service")
        Description = "Basic functionality (no AI/ML)"
    }
    "core" = @{
        Infrastructure = @("postgres", "neo4j", "weaviate", "minio")
        Applications = @("frontend", "project-service", "reporting-service")
        Description = "Core features with basic AI"
    }
    "full" = @{
        Infrastructure = @("postgres", "neo4j", "weaviate", "minio")
        Applications = @("frontend", "backend", "project-service", "reporting-service", "megaparse")
        Description = "All features including advanced AI/ML"
    }
}

if (-not $serviceProfiles.ContainsKey($StartupProfile.ToLower())) {
    Write-Log "ERROR: Invalid profile '$StartupProfile'. Use: minimal, core, or full" "Red"
    exit 1
}

$selectedProfile = $serviceProfiles[$StartupProfile.ToLower()]
Write-Log "INFO: Starting in $($StartupProfile.ToUpper()) mode - $($selectedProfile.Description)" "Yellow"

# Check if required images exist
$requiredImages = @()
foreach ($service in $selectedProfile.Applications) {
    switch ($service) {
        "frontend" { $requiredImages += "migration_platform_2-frontend:latest" }
        "backend" { $requiredImages += "migration_platform_2-backend:latest" }
        "project-service" { $requiredImages += "migration_platform_2-project-service:latest" }
        "reporting-service" { $requiredImages += "migration_platform_2-reporting-service:latest" }
        "megaparse" { $requiredImages += "migration_platform_2-megaparse:latest" }
    }
}

$missingImages = @()
foreach ($image in $requiredImages) {
    $result = docker images -q $image 2>$null
    if (-not $result) {
        $missingImages += $image
    }
}

if ($missingImages.Count -gt 0) {
    Write-Log "ERROR: Missing required images:" "Red"
    foreach ($image in $missingImages) {
        Write-Log "   - $image" "Red"
    }
    Write-Log "" "White"
    Write-Log "SOLUTION: Please run the build script first:" "Yellow"
    Write-Log "   .\build-all.ps1" "Cyan"
    exit 1
}

Write-Log "SUCCESS: All required images are available" "Green"

# Create optimized docker-compose override
$overrideContent = @"
version: '3.8'

services:
  frontend:
    image: migration_platform_2-frontend:latest
    build: null

  project-service:
    image: migration_platform_2-project-service:latest
    build: null

  reporting-service:
    image: migration_platform_2-reporting-service:latest
    build: null
"@

if ($StartupProfile.ToLower() -eq "full") {
    $overrideContent += @"

  backend:
    image: migration_platform_2-backend:latest
    build: null

  megaparse:
    image: migration_platform_2-megaparse:latest
    build: null
"@
}

$overrideContent | Out-File -FilePath "docker-compose.optimized.yml" -Encoding UTF8
Write-Log "INFO: Created optimized startup configuration" "Gray"

# Start infrastructure services first
Write-Log "INFO: Starting infrastructure services..." "Yellow"
Write-Log "   Services: $($selectedProfile.Infrastructure -join ', ')" "Gray"

try {
    if ($DOCKER_COMPOSE -eq "docker compose") {
        docker compose -f docker-compose.yml -f docker-compose.optimized.yml up -d @($selectedProfile.Infrastructure)
    } else {
        docker-compose -f docker-compose.yml -f docker-compose.optimized.yml up -d @($selectedProfile.Infrastructure)
    }
    Write-Log "SUCCESS: Infrastructure services started" "Green"
} catch {
    Write-Log "ERROR: Failed to start infrastructure services: $($_.Exception.Message)" "Red"
    exit 1
}

# Wait for infrastructure to be ready
Write-Log "INFO: Waiting for infrastructure to be ready..." "Yellow"
Start-Sleep -Seconds 15

# Start application services
Write-Log "INFO: Starting application services..." "Yellow"
Write-Log "   Services: $($selectedProfile.Applications -join ', ')" "Gray"

try {
    if ($DOCKER_COMPOSE -eq "docker compose") {
        docker compose -f docker-compose.yml -f docker-compose.optimized.yml up -d @($selectedProfile.Applications)
    } else {
        docker-compose -f docker-compose.yml -f docker-compose.optimized.yml up -d @($selectedProfile.Applications)
    }
    Write-Log "SUCCESS: Application services started" "Green"
} catch {
    Write-Log "ERROR: Failed to start application services: $($_.Exception.Message)" "Red"
    exit 1
}

# Wait for services to initialize
Write-Log "INFO: Waiting for services to initialize..." "Yellow"
Start-Sleep -Seconds 10

# Check service status
Write-Log "INFO: Checking service status..." "Yellow"
if ($DOCKER_COMPOSE -eq "docker compose") {
    docker compose ps
} else {
    docker-compose ps
}

Write-Log "" "White"
Write-Log "SUCCESS: Platform started successfully!" "Green"
Write-Log "=======================================" "Green"

# Display access URLs
Write-Log "ACCESS URLS:" "Cyan"
Write-Log "   Frontend (Command Center): http://localhost:3000" "Yellow"

if ($selectedProfile.Applications -contains "project-service") {
    Write-Log "   Project Service: http://localhost:8002" "Yellow"
}

if ($selectedProfile.Applications -contains "reporting-service") {
    Write-Log "   Reporting Service: http://localhost:8003" "Yellow"
}

if ($selectedProfile.Applications -contains "backend") {
    Write-Log "   Backend API: http://localhost:8000" "Yellow"
}

if ($selectedProfile.Applications -contains "megaparse") {
    Write-Log "   MegaParse Service: http://localhost:5001" "Yellow"
}

Write-Log "   Neo4j Browser: http://localhost:7474" "Yellow"
Write-Log "   MinIO Console: http://localhost:9001" "Yellow"

Write-Log "" "White"
Write-Log "PERFORMANCE: Startup completed in ~2-3 minutes instead of 20!" "Green"
Write-Log "MANAGEMENT:" "Cyan"
Write-Log "   Stop: .\start-optimized.ps1 -StopOnly" "Gray"
Write-Log "   Restart: .\start-optimized.ps1 -Restart" "Gray"

Write-Log "" "White"
Write-Log "LOG: Startup log saved to: $logFile" "Gray"
