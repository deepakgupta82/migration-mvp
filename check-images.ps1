# =====================================================================================
# Nagarro AgentiMigrate Platform - Image Status Checker
# =====================================================================================
# This script checks which Docker images are built and their sizes
# Helps determine if you need to run build-images.ps1
# =====================================================================================

Write-Host "🔍 Nagarro AgentiMigrate Platform - Image Status" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

function Test-ImageExists {
    param($ImageName)
    $result = docker images -q $ImageName 2>$null
    return ($null -ne $result) -and ($result -ne "")
}

function Get-ImageInfo {
    param($ImageName)
    $info = docker images $ImageName --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}" | Select-Object -Skip 1
    return $info
}

# Check Docker availability
try {
    docker version | Out-Null
    Write-Host "✅ Docker is available" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker is not available. Please start Docker Desktop or Rancher Desktop." -ForegroundColor Red
    exit 1
}

Write-Host ""

# Define expected images
$images = @(
    @{Name="Frontend"; Tag="migration_platform_2-frontend:latest"; Required=$true},
    @{Name="Backend Full"; Tag="migration_platform_2-backend:latest"; Required=$false},
    @{Name="Backend Minimal"; Tag="migration_platform_2-backend:minimal"; Required=$false},
    @{Name="Project Service"; Tag="migration_platform_2-project-service:latest"; Required=$true},
    @{Name="Reporting Service"; Tag="migration_platform_2-reporting-service:latest"; Required=$false},
    @{Name="MegaParse Service"; Tag="migration_platform_2-megaparse:latest"; Required=$false}
)

$totalSize = 0
$builtImages = 0
$requiredImages = 0
$missingRequired = @()

Write-Host "📊 Image Status:" -ForegroundColor Yellow
Write-Host "=================" -ForegroundColor Yellow

foreach ($image in $images) {
    $exists = Test-ImageExists $image.Tag

    if ($exists) {
        $info = Get-ImageInfo $image.Tag
        $size = ($info -split '\s+')[1]
        $created = ($info -split '\s+')[2..3] -join ' '

        Write-Host "✅ $($image.Name): $size (Created: $created)" -ForegroundColor Green
        $builtImages++

        # Try to extract size in MB for total calculation
        if ($size -match '(\d+\.?\d*)([KMGT]B)') {
            $sizeValue = [float]$matches[1]
            $unit = $matches[2]
            switch ($unit) {
                'KB' { $sizeInMB = $sizeValue / 1024 }
                'MB' { $sizeInMB = $sizeValue }
                'GB' { $sizeInMB = $sizeValue * 1024 }
                'TB' { $sizeInMB = $sizeValue * 1024 * 1024 }
            }
            $totalSize += $sizeInMB
        }
    } else {
        $status = if ($image.Required) { "❌ MISSING (REQUIRED)" } else { "⚪ Not built" }
        $color = if ($image.Required) { "Red" } else { "Gray" }
        Write-Host "$status $($image.Name)" -ForegroundColor $color

        if ($image.Required) {
            $missingRequired += $image.Name
            $requiredImages++
        }
    }
}

Write-Host ""
Write-Host "📈 Summary:" -ForegroundColor Cyan
Write-Host "===========" -ForegroundColor Cyan
Write-Host "Built images: $builtImages/$($images.Count)" -ForegroundColor $(if ($builtImages -eq $images.Count) { "Green" } else { "Yellow" })

if ($totalSize -gt 0) {
    if ($totalSize -gt 1024) {
        Write-Host "Total size: $([math]::Round($totalSize / 1024, 2)) GB" -ForegroundColor Yellow
    } else {
        Write-Host "Total size: $([math]::Round($totalSize, 0)) MB" -ForegroundColor Yellow
    }
}

if ($missingRequired.Count -gt 0) {
    Write-Host "Missing required images: $($missingRequired.Count)" -ForegroundColor Red
    Write-Host ""
    Write-Host "💡 To build missing images:" -ForegroundColor Yellow
    Write-Host "   .\build-images.ps1" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "💡 For faster development with minimal backend:" -ForegroundColor Yellow
    Write-Host "   .\build-images.ps1 -Minimal" -ForegroundColor Cyan
} else {
    Write-Host "✅ All required images are available!" -ForegroundColor Green
    Write-Host ""
    Write-Host "🚀 Ready for fast startup:" -ForegroundColor Green
    Write-Host "   .\start-platform-fast.ps1" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "⚡ Expected startup time: 2-3 minutes" -ForegroundColor Green
}

Write-Host ""

# Check for old/unused images
Write-Host "🧹 Cleanup Recommendations:" -ForegroundColor Cyan
$allImages = docker images --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}" | Select-Object -Skip 1
$platformImages = $allImages | Where-Object { $_ -like "*migration_platform*" }

if ($platformImages.Count -gt $images.Count) {
    Write-Host "   • You have extra platform images that can be cleaned up" -ForegroundColor Yellow
    Write-Host "   • Run: docker image prune -f" -ForegroundColor Gray
}

$danglingImages = docker images -f "dangling=true" -q
if ($danglingImages) {
    Write-Host "   • You have dangling images that can be removed" -ForegroundColor Yellow
    Write-Host "   • Run: docker image prune -f" -ForegroundColor Gray
}

Write-Host ""
Write-Host "📝 For detailed build logs, check the logs/ directory" -ForegroundColor Gray
