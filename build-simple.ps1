# =====================================================================================
# Simple Platform Image Builder - Phase 1 Implementation
# =====================================================================================
# This script builds Docker images one by one with better error handling
# =====================================================================================

[CmdletBinding()]
param (
    [switch]$Minimal,         # Build minimal versions without heavy ML deps
    [switch]$Force            # Force rebuild existing images
)

Write-Host "Platform Image Builder - Phase 1 Implementation" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# Create logs directory
if (!(Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" -Force | Out-Null
}

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$logFile = "logs/build_simple_$timestamp.log"

function Write-Log {
    param($Message, $Color = "White")
    $timestampedMessage = "[$(Get-Date -Format 'HH:mm:ss')] $Message"
    Write-Host $timestampedMessage -ForegroundColor $Color
    $timestampedMessage | Out-File -FilePath $logFile -Append
}

function Wait-ForDocker {
    Write-Log "Checking Docker availability..." "Yellow"
    $maxAttempts = 12
    $attempt = 0
    
    while ($attempt -lt $maxAttempts) {
        try {
            docker version | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Log "SUCCESS: Docker is available" "Green"
                return $true
            }
        } catch {
            # Continue trying
        }
        
        $attempt++
        Write-Log "Attempt $attempt/$maxAttempts - Docker not ready, waiting 10 seconds..." "Yellow"
        Start-Sleep -Seconds 10
    }
    
    Write-Log "ERROR: Docker is not available after $maxAttempts attempts" "Red"
    return $false
}

function Test-ImageExists {
    param($ImageName)
    try {
        $result = docker images -q $ImageName 2>$null
        return ($null -ne $result) -and ($result -ne "")
    } catch {
        return $false
    }
}

# Wait for Docker to be ready
if (-not (Wait-ForDocker)) {
    Write-Log "FAILED: Cannot connect to Docker. Please ensure Docker Desktop is running." "Red"
    exit 1
}

# Enable BuildKit for better performance
$env:DOCKER_BUILDKIT = "1"
$env:COMPOSE_DOCKER_CLI_BUILD = "1"
Write-Log "INFO: Docker BuildKit enabled for optimized builds" "Yellow"

# Define build order (start with lighter services)
$buildOrder = @(
    @{
        Name = "frontend"
        Description = "React Frontend Application"
        Command = "docker compose build frontend"
        Priority = 1
    },
    @{
        Name = "project-service"
        Description = "Project Management Service"
        Command = "docker compose build project-service"
        Priority = 2
    },
    @{
        Name = "reporting-service"
        Description = "Report Generation Service"
        Command = "docker compose build reporting-service"
        Priority = 3
    }
)

# Add backend and megaparse if not minimal
if (-not $Minimal) {
    $buildOrder += @{
        Name = "backend"
        Description = "Backend API with AI/ML (8-15 minutes)"
        Command = "docker compose build backend"
        Priority = 4
    }
    
    $buildOrder += @{
        Name = "megaparse"
        Description = "Document Processing Service (4-6 minutes)"
        Command = "docker compose build megaparse"
        Priority = 5
    }
} else {
    Write-Log "INFO: Building in MINIMAL mode (skipping heavy AI/ML services)" "Yellow"
}

Write-Log "INFO: Build Plan:" "Cyan"
foreach ($build in $buildOrder) {
    $exists = Test-ImageExists "migration_platform_2-$($build.Name):latest"
    $status = if ($exists -and -not $Force) { "EXISTS (will skip)" } else { "WILL BUILD" }
    Write-Log "   - $($build.Description): $status" "Gray"
}

Write-Log "" "White"
$confirm = Read-Host "Continue with build? (y/N)"
if ($confirm -ne "y" -and $confirm -ne "Y") {
    Write-Log "Build cancelled by user" "Yellow"
    exit 0
}

# Build images
$buildResults = @{}
$totalBuilds = $buildOrder.Count
$currentBuild = 0

foreach ($build in $buildOrder) {
    $currentBuild++
    
    # Check if image already exists
    $exists = Test-ImageExists "migration_platform_2-$($build.Name):latest"
    if ($exists -and -not $Force) {
        Write-Log "SKIP: [$currentBuild/$totalBuilds] $($build.Name) already exists" "Yellow"
        $buildResults[$build.Name] = "SKIPPED"
        continue
    }
    
    Write-Log "BUILD: [$currentBuild/$totalBuilds] Building $($build.Description)..." "Cyan"
    Write-Log "   Command: $($build.Command)" "Gray"
    
    $startTime = Get-Date
    try {
        # Execute the build command
        $output = Invoke-Expression $build.Command 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            $endTime = Get-Date
            $duration = ($endTime - $startTime).TotalMinutes
            Write-Log "SUCCESS: $($build.Name) built successfully in $([math]::Round($duration, 1)) minutes" "Green"
            $buildResults[$build.Name] = "SUCCESS"
        } else {
            Write-Log "ERROR: Failed to build $($build.Name)" "Red"
            Write-Log "Output: $output" "Red"
            $buildResults[$build.Name] = "FAILED"
        }
    } catch {
        Write-Log "ERROR: Exception building $($build.Name): $($_.Exception.Message)" "Red"
        $buildResults[$build.Name] = "ERROR"
    }
    
    Write-Log "" "White"
}

# Summary
Write-Log "INFO: Build Summary:" "Cyan"
Write-Log "===================" "Cyan"

$successful = 0
$failed = 0
$skipped = 0

foreach ($result in $buildResults.GetEnumerator()) {
    $status = switch ($result.Value) {
        "SUCCESS" { $successful++; "SUCCESS"; "Green" }
        "FAILED" { $failed++; "FAILED"; "Red" }
        "ERROR" { $failed++; "ERROR"; "Red" }
        "SKIPPED" { $skipped++; "SKIPPED"; "Yellow" }
    }
    Write-Log "   $($result.Key): $($status[0])" $status[1]
}

Write-Log "" "White"
Write-Log "RESULTS: $successful successful, $skipped skipped, $failed failed" "Cyan"

if ($failed -eq 0) {
    Write-Log "SUCCESS: Phase 1 completed successfully!" "Green"
    Write-Log "NEXT STEPS:" "Cyan"
    Write-Log "   1. Run: .\start-optimized.ps1" "Yellow"
    Write-Log "   2. Platform will start in 2-3 minutes instead of 20!" "Green"
    Write-Log "   3. Frontend: http://localhost:3000" "Yellow"
} else {
    Write-Log "WARNING: Some builds failed. Check the logs above for details." "Red"
    Write-Log "TIP: Try running with -Force flag to rebuild from scratch" "Yellow"
}

Write-Log "" "White"
Write-Log "LOG: Build log saved to: $logFile" "Gray"
