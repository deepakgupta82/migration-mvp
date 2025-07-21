# Nagarro AgentiMigrate MVP Environment Setup for Windows

Write-Host "Starting Nagarro AgentiMigrate MVP Environment Setup for Windows..."

# Check Git installation
if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) {
    Write-Host "Git not found. Installing Git..."
    winget install --id Git.Git -e --silent
    if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) {
        Write-Host "Error: Git installation failed."
        exit 1
    }
}
Write-Host "Git... OK"

# Check Rancher Desktop installation
if (-not (Get-Command "C:\Program Files\Rancher Desktop\rancher-desktop.exe" -ErrorAction SilentlyContinue)) {
    Write-Host "Rancher Desktop not found. Installing Rancher Desktop..."
    winget install --id Rancher.RancherDesktop -e --silent
    if (-not (Get-Command "C:\Program Files\Rancher Desktop\rancher-desktop.exe" -ErrorAction SilentlyContinue)) {
        Write-Host "Error: Rancher Desktop installation failed."
        exit 1
    }
}
Write-Host "Rancher Desktop... OK"

# Check kubectl installation
if (-not (Get-Command kubectl.exe -ErrorAction SilentlyContinue)) {
    Write-Host "kubectl not found. Installing kubectl..."
    winget install --id Kubernetes.kubectl -e --silent
    if (-not (Get-Command kubectl.exe -ErrorAction SilentlyContinue)) {
        Write-Host "Error: kubectl installation failed."
        exit 1
    }
}
Write-Host "kubectl... OK"

# Ensure Rancher Desktop Kubernetes backend is running
Write-Host "Please ensure Rancher Desktop is running and Kubernetes backend is enabled."
Write-Host "Waiting for Kubernetes cluster to be ready..."
$kubectlReady = $false
for ($i = 0; $i -lt 30; $i++) {
    kubectl get nodes > $null 2>&1
    if ($LASTEXITCODE -eq 0) {
        $kubectlReady = $true
        break
    }
    Start-Sleep -Seconds 5
}
if (-not $kubectlReady) {
    Write-Host "Error: Kubernetes cluster not ready. Please check Rancher Desktop settings."
    exit 1
}
Write-Host "Kubernetes cluster running."

# Clone MegaParse repository if not present
if (Test-Path ".\MegaParse") {
    Write-Host "MegaParse directory already exists. Skipping clone."
} else {
    git clone https://github.com/QuivrHQ/MegaParse.git
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Failed to clone MegaParse repository."
        exit 1
    } else {
        Write-Host "MegaParse repository cloned successfully."
    }
}

Write-Host "Environment setup complete. You can now proceed with the project build."
