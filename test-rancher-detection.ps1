# Rancher Desktop Detection Test Script
Write-Host "🔍 Rancher Desktop Detection Test" -ForegroundColor Cyan
Write-Host "=================================" -ForegroundColor Cyan

# Test all possible detection methods
Write-Host ""
Write-Host "1. Testing file-based detection:" -ForegroundColor Yellow

$possiblePaths = @(
    "$env:USERPROFILE\.rd\bin\rdctl.exe",
    "$env:LOCALAPPDATA\Programs\Rancher Desktop\resources\resources\win32\bin\rdctl.exe",
    "$env:PROGRAMFILES\Rancher Desktop\resources\resources\win32\bin\rdctl.exe",
    "$env:PROGRAMFILES(x86)\Rancher Desktop\resources\resources\win32\bin\rdctl.exe",
    "$env:LOCALAPPDATA\Programs\Rancher Desktop\rdctl.exe",
    "$env:PROGRAMFILES\Rancher Desktop\rdctl.exe",
    "$env:PROGRAMFILES(x86)\Rancher Desktop\rdctl.exe"
)

$foundPaths = @()
foreach ($path in $possiblePaths) {
    Write-Host "   Checking: $path" -ForegroundColor Gray
    if (Test-Path $path) {
        Write-Host "   ✅ FOUND: $path" -ForegroundColor Green
        $foundPaths += $path
    } else {
        Write-Host "   ❌ Not found" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "2. Testing process-based detection:" -ForegroundColor Yellow

$rancherProcesses = Get-Process -Name "*rancher*" -ErrorAction SilentlyContinue
if ($rancherProcesses) {
    Write-Host "   ✅ Rancher processes found:" -ForegroundColor Green
    foreach ($proc in $rancherProcesses) {
        Write-Host "      - $($proc.Name) (PID: $($proc.Id)) at $($proc.Path)" -ForegroundColor Green
    }
} else {
    Write-Host "   ❌ No Rancher processes found" -ForegroundColor Red
}

Write-Host ""
Write-Host "3. Testing Docker availability:" -ForegroundColor Yellow

try {
    $dockerVersion = docker --version 2>$null
    if ($dockerVersion) {
        Write-Host "   ✅ Docker command available: $dockerVersion" -ForegroundColor Green
        
        # Test Docker daemon
        Write-Host "   Testing Docker daemon..." -ForegroundColor Gray
        docker ps >$null 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "   ✅ Docker daemon responding" -ForegroundColor Green
        } else {
            Write-Host "   ❌ Docker daemon not responding (exit code: $LASTEXITCODE)" -ForegroundColor Red
        }
    } else {
        Write-Host "   ❌ Docker command not available" -ForegroundColor Red
    }
} catch {
    Write-Host "   ❌ Error testing Docker: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "4. Testing Docker Compose availability:" -ForegroundColor Yellow

try {
    $composeVersion = docker compose version 2>$null
    if ($composeVersion) {
        Write-Host "   ✅ Docker Compose available: $composeVersion" -ForegroundColor Green
    } else {
        # Try legacy docker-compose
        $composeVersion = docker-compose --version 2>$null
        if ($composeVersion) {
            Write-Host "   ✅ Docker Compose (legacy) available: $composeVersion" -ForegroundColor Green
        } else {
            Write-Host "   ❌ Docker Compose not available" -ForegroundColor Red
        }
    }
} catch {
    Write-Host "   ❌ Error testing Docker Compose: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "5. Environment information:" -ForegroundColor Yellow
Write-Host "   USERPROFILE: $env:USERPROFILE" -ForegroundColor Gray
Write-Host "   LOCALAPPDATA: $env:LOCALAPPDATA" -ForegroundColor Gray
Write-Host "   PROGRAMFILES: $env:PROGRAMFILES" -ForegroundColor Gray
if ($env:PROGRAMFILES_X86) {
    Write-Host "   PROGRAMFILES(x86): $env:PROGRAMFILES_X86" -ForegroundColor Gray
}

Write-Host ""
Write-Host "6. Registry check:" -ForegroundColor Yellow
try {
    $rancherRegistry = Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*" | Where-Object { $_.DisplayName -like "*Rancher*" }
    if ($rancherRegistry) {
        Write-Host "   ✅ Rancher Desktop found in registry:" -ForegroundColor Green
        foreach ($entry in $rancherRegistry) {
            Write-Host "      - $($entry.DisplayName) at $($entry.InstallLocation)" -ForegroundColor Green
        }
    } else {
        Write-Host "   ❌ Rancher Desktop not found in registry" -ForegroundColor Red
    }
} catch {
    Write-Host "   ❌ Error checking registry: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "📋 Summary:" -ForegroundColor Cyan
if ($foundPaths.Count -gt 0) {
    Write-Host "✅ Rancher Desktop installation detected!" -ForegroundColor Green
    Write-Host "   Found at: $($foundPaths[0])" -ForegroundColor Green
} elseif ($rancherProcesses) {
    Write-Host "✅ Rancher Desktop is running but installation path not found in expected locations" -ForegroundColor Yellow
    Write-Host "   Process found: $($rancherProcesses[0].Path)" -ForegroundColor Yellow
} else {
    Write-Host "❌ Rancher Desktop not detected" -ForegroundColor Red
    Write-Host "   Please ensure Rancher Desktop is installed and running" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "💡 If Rancher Desktop is installed but not detected:" -ForegroundColor Cyan
Write-Host "   1. Check if it's running from Start Menu" -ForegroundColor Gray
Write-Host "   2. Verify 'dockerd (moby)' is selected as container runtime" -ForegroundColor Gray
Write-Host "   3. Try restarting Rancher Desktop" -ForegroundColor Gray
Write-Host "   4. Check the installation directory manually" -ForegroundColor Gray

Read-Host "Press Enter to exit"
