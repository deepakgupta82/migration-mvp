# =====================================================================================
# Build All Platform Images - One Time Setup
# =====================================================================================
# This script builds all Docker images once for fast startup
# Run this when: First time setup, dependencies change, or code updates needed
# =====================================================================================

[CmdletBinding()]
param (
    [switch]$Minimal,         # Build minimal versions without heavy ML deps
    [switch]$Force,           # Force rebuild existing images
    [switch]$SkipCache        # Skip Docker cache
)

Write-Host "Platform Image Builder - One Time Setup" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# Create logs directory
if (!(Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" -Force | Out-Null
}

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$logFile = "logs/build_all_$timestamp.log"

function Write-Log {
    param($Message, $Color = "White")
    $timestampedMessage = "[$(Get-Date -Format 'HH:mm:ss')] $Message"
    Write-Host $timestampedMessage -ForegroundColor $Color
    $timestampedMessage | Out-File -FilePath $logFile -Append
}

# Check Docker availability
try {
    docker version | Out-Null
    Write-Log "SUCCESS: Docker is available" "Green"
} catch {
    Write-Log "ERROR: Docker is not available. Please start Docker Desktop or Rancher Desktop." "Red"
    exit 1
}

# Enable BuildKit for better performance
$env:DOCKER_BUILDKIT = "1"
$env:COMPOSE_DOCKER_CLI_BUILD = "1"
Write-Log "INFO: Docker BuildKit enabled for optimized builds" "Yellow"

# Define build order (infrastructure first, then applications)
$buildOrder = @(
    @{
        Name = "frontend"
        Description = "React Frontend Application"
        EstimatedTime = "3-5 minutes"
        Command = "docker compose build frontend"
    },
    @{
        Name = "project-service"
        Description = "Project Management Service"
        EstimatedTime = "2-3 minutes"
        Command = "docker compose build project-service"
    },
    @{
        Name = "reporting-service"
        Description = "Report Generation Service"
        EstimatedTime = "3-4 minutes"
        Command = "docker compose build reporting-service"
    }
)

# Add backend based on minimal flag
if ($Minimal) {
    Write-Log "INFO: Building MINIMAL backend (no heavy ML dependencies)" "Yellow"
    # We'll need to create the minimal backend build later
    Write-Log "INFO: Minimal backend build will be implemented in next phase" "Yellow"
} else {
    $buildOrder += @{
        Name = "backend"
        Description = "Backend API with AI/ML (WARNING: Takes 8-15 minutes)"
        EstimatedTime = "8-15 minutes"
        Command = "docker compose build backend"
    }
    
    $buildOrder += @{
        Name = "megaparse"
        Description = "Document Processing Service"
        EstimatedTime = "4-6 minutes"
        Command = "docker compose build megaparse"
    }
}

Write-Log "INFO: Build Plan:" "Cyan"
$totalEstimatedTime = 0
foreach ($build in $buildOrder) {
    $timeRange = $build.EstimatedTime -replace "(\d+)-(\d+)", { $matches[2] }
    $totalEstimatedTime += [int]$timeRange
    Write-Log "   - $($build.Description): $($build.EstimatedTime)" "Gray"
}

Write-Log "INFO: Estimated total build time: ~$totalEstimatedTime minutes" "Yellow"
Write-Log "TIP: This is a ONE-TIME process. Daily startup will be 2-3 minutes!" "Cyan"
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
    Write-Log "BUILD: [$currentBuild/$totalBuilds] Building $($build.Description)..." "Cyan"
    Write-Log "   Estimated time: $($build.EstimatedTime)" "Gray"
    Write-Log "   Command: $($build.Command)" "Gray"
    
    $startTime = Get-Date
    try {
        Invoke-Expression $build.Command
        if ($LASTEXITCODE -eq 0) {
            $endTime = Get-Date
            $duration = ($endTime - $startTime).TotalMinutes
            Write-Log "SUCCESS: $($build.Name) built successfully in $([math]::Round($duration, 1)) minutes" "Green"
            $buildResults[$build.Name] = "SUCCESS"
        } else {
            Write-Log "ERROR: Failed to build $($build.Name)" "Red"
            $buildResults[$build.Name] = "FAILED"
        }
    } catch {
        Write-Log "ERROR: Error building $($build.Name): $($_.Exception.Message)" "Red"
        $buildResults[$build.Name] = "ERROR"
    }
    
    Write-Log "" "White"
}

# Summary
Write-Log "INFO: Build Summary:" "Cyan"
Write-Log "===================" "Cyan"

$successful = 0
$failed = 0

foreach ($result in $buildResults.GetEnumerator()) {
    $status = switch ($result.Value) {
        "SUCCESS" { $successful++; "SUCCESS"; "Green" }
        "FAILED" { $failed++; "FAILED"; "Red" }
        "ERROR" { $failed++; "ERROR"; "Red" }
    }
    Write-Log "   $($result.Key): $($status[0])" $status[1]
}

Write-Log "" "White"
Write-Log "RESULTS: $successful successful, $failed failed" "Cyan"

if ($failed -eq 0) {
    Write-Log "SUCCESS: All builds completed successfully!" "Green"
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
