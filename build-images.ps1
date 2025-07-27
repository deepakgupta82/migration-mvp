# =====================================================================================
# Nagarro AgentiMigrate Platform - Optimized Image Builder
# =====================================================================================
# This script builds Docker images ONCE and caches them for fast startup
# Run this script when:
# - First time setup
# - Dependencies change (requirements.txt, package.json)
# - Code changes that require rebuild
# =====================================================================================

[CmdletBinding()]
param (
    [switch]$Force,           # Force rebuild all images
    [switch]$Frontend,        # Build only frontend
    [switch]$Backend,         # Build only backend
    [switch]$Services,        # Build only services (project, reporting)
    [switch]$SkipCache,       # Skip Docker cache
    [switch]$Minimal,         # Build minimal versions without heavy ML deps
    [string]$Registry = ""    # Push to registry after build
)

Write-Host "Nagarro AgentiMigrate Platform - Optimized Image Builder" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

# Create logs directory
if (!(Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" -Force | Out-Null
}

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$logFile = "logs/build_$timestamp.log"

function Write-Log {
    param($Message, $Color = "White")
    $timestampedMessage = "[$(Get-Date -Format 'HH:mm:ss')] $Message"
    Write-Host $timestampedMessage -ForegroundColor $Color
    $timestampedMessage | Out-File -FilePath $logFile -Append
}

function Test-ImageExists {
    param($ImageName)
    $result = docker images -q $ImageName 2>$null
    return ($null -ne $result) -and ($result -ne "")
}

function Get-ImageSize {
    param($ImageName)
    $result = docker images $ImageName --format "table {{.Size}}" | Select-Object -Skip 1
    return $result
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
Write-Log "🚀 Docker BuildKit enabled for optimized builds" "Yellow"

# Determine what to build
$buildAll = -not ($Frontend -or $Backend -or $Services)

# Build configuration
$builds = @()

if ($buildAll -or $Frontend) {
    $builds += @{
        Name = "frontend"
        Context = "./frontend"
        Dockerfile = "./frontend/Dockerfile"
        Tag = "migration_platform_2-frontend:latest"
        Description = "React Frontend Application"
        EstimatedTime = "3-5 minutes"
        Priority = 1
    }
}

if ($buildAll -or $Backend) {
    if ($Minimal) {
        $builds += @{
            Name = "backend-minimal"
            Context = "./backend"
            Dockerfile = "./backend/Dockerfile.minimal"
            Tag = "migration_platform_2-backend:minimal"
            Description = "Backend API (Minimal - No ML)"
            EstimatedTime = "2-3 minutes"
            Priority = 2
        }
    } else {
        $builds += @{
            Name = "backend"
            Context = "./backend"
            Dockerfile = "./backend/Dockerfile"
            Tag = "migration_platform_2-backend:latest"
            Description = "Backend API with AI/ML"
            EstimatedTime = "8-12 minutes"
            Priority = 3
        }
    }
}

if ($buildAll -or $Services) {
    $builds += @{
        Name = "project-service"
        Context = "./project-service"
        Dockerfile = "./project-service/Dockerfile"
        Tag = "migration_platform_2-project-service:latest"
        Description = "Project Management Service"
        EstimatedTime = "2-3 minutes"
        Priority = 1
    }

    $builds += @{
        Name = "reporting-service"
        Context = "./reporting-service"
        Dockerfile = "./reporting-service/Dockerfile"
        Tag = "migration_platform_2-reporting-service:latest"
        Description = "Report Generation Service"
        EstimatedTime = "3-4 minutes"
        Priority = 2
    }

    $builds += @{
        Name = "megaparse"
        Context = "./MegaParse"
        Dockerfile = "./MegaParse/Dockerfile"
        Tag = "migration_platform_2-megaparse:latest"
        Description = "Document Processing Service"
        EstimatedTime = "4-6 minutes"
        Priority = 2
    }
}

# Sort builds by priority
$builds = $builds | Sort-Object Priority

Write-Log "📋 Build Plan:" "Cyan"
$totalEstimatedTime = 0
foreach ($build in $builds) {
    $exists = Test-ImageExists $build.Tag
    $status = if ($exists -and -not $Force) { "EXISTS (will skip)" } else { "WILL BUILD" }
    $timeRange = $build.EstimatedTime -replace "(\d+)-(\d+)", { $matches[2] }
    $totalEstimatedTime += [int]$timeRange

    Write-Log "   • $($build.Description): $status ($($build.EstimatedTime))" "Gray"
}

if ($totalEstimatedTime -gt 0) {
    Write-Log "⏱️ Estimated total build time: ~$totalEstimatedTime minutes" "Yellow"
    Write-Log "💡 Tip: Use -Minimal flag for faster builds without heavy ML dependencies" "Cyan"
}

Write-Log "" "White"

# Build images
$buildResults = @{}
$totalBuilds = $builds.Count
$currentBuild = 0

foreach ($build in $builds) {
    $currentBuild++
    $exists = Test-ImageExists $build.Tag

    if ($exists -and -not $Force) {
        Write-Log "⏭️ [$currentBuild/$totalBuilds] Skipping $($build.Name) - image already exists" "Yellow"
        Write-Log "   Use -Force to rebuild existing images" "Gray"
        $buildResults[$build.Name] = "SKIPPED"
        continue
    }

    Write-Log "🏗️ [$currentBuild/$totalBuilds] Building $($build.Description)..." "Cyan"
    Write-Log "   Context: $($build.Context)" "Gray"
    Write-Log "   Tag: $($build.Tag)" "Gray"

    $buildArgs = @(
        "build"
        "-t", $build.Tag
        "-f", $build.Dockerfile
    )

    if (-not $SkipCache) {
        $buildArgs += "--build-arg", "BUILDKIT_INLINE_CACHE=1"
    }

    $buildArgs += $build.Context

    $startTime = Get-Date
    try {
        & docker @buildArgs
        if ($LASTEXITCODE -eq 0) {
            $endTime = Get-Date
            $duration = ($endTime - $startTime).TotalMinutes
            $size = Get-ImageSize $build.Tag
            Write-Log "✅ $($build.Name) built successfully in $([math]::Round($duration, 1)) minutes (Size: $size)" "Green"
            $buildResults[$build.Name] = "SUCCESS"

            # Push to registry if specified
            if ($Registry) {
                $registryTag = "$Registry/$($build.Tag)"
                Write-Log "📤 Pushing to registry: $registryTag" "Yellow"
                docker tag $build.Tag $registryTag
                docker push $registryTag
            }
        } else {
            Write-Log "❌ Failed to build $($build.Name)" "Red"
            $buildResults[$build.Name] = "FAILED"
        }
    } catch {
        Write-Log "❌ Error building $($build.Name): $($_.Exception.Message)" "Red"
        $buildResults[$build.Name] = "ERROR"
    }

    Write-Log "" "White"
}

# Summary
Write-Log "📊 Build Summary:" "Cyan"
Write-Log "=================" "Cyan"

$successful = 0
$failed = 0
$skipped = 0

foreach ($result in $buildResults.GetEnumerator()) {
    $status = switch ($result.Value) {
        "SUCCESS" { $successful++; "✅ SUCCESS"; "Green" }
        "FAILED" { $failed++; "❌ FAILED"; "Red" }
        "ERROR" { $failed++; "❌ ERROR"; "Red" }
        "SKIPPED" { $skipped++; "⏭️ SKIPPED"; "Yellow" }
    }
    Write-Log "   $($result.Key): $($status[0])" $status[1]
}

Write-Log "" "White"
Write-Log "📈 Results: $successful successful, $skipped skipped, $failed failed" "Cyan"

if ($failed -eq 0) {
    Write-Log "🎉 All builds completed successfully!" "Green"
    Write-Log "💡 Next steps:" "Cyan"
    Write-Log "   • Run: .\start-platform.ps1 -SkipBuild" "Yellow"
    Write-Log "   • Or: docker compose up -d" "Yellow"
    Write-Log "   • Platform will start in 2-3 minutes instead of 20!" "Green"
} else {
    Write-Log "⚠️ Some builds failed. Check the logs above for details." "Red"
    Write-Log "💡 Try running with -Force flag to rebuild from scratch" "Yellow"
}

Write-Log "" "White"
Write-Log "📝 Build log saved to: $logFile" "Gray"
