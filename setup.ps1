# Nagarro AgentiMigrate MVP Environment Setup for Windows (Robust Edition)

Write-Host "Starting Nagarro AgentiMigrate MVP Environment Setup for Windows..." -ForegroundColor Yellow

# Function to check if a command is in the system PATH
function Test-CommandExists {
    param($command)
    return (Get-Command $command -ErrorAction SilentlyContinue)
}

# --- 1. Git Verification ---
if (-not (Test-CommandExists git)) {
    Write-Host "Git not found. Please install Git from https://git-scm.com/ and ensure it's added to your PATH." -ForegroundColor Red
    exit 1
}
Write-Host "Git... OK" -ForegroundColor Green

# --- 2. Rancher Desktop & Docker/Nerdctl Verification ---
# The most reliable way to check for Rancher is to see if its tools are in the PATH.
if (-not (Test-CommandExists nerdctl) -and -not (Test-CommandExists docker)) {
    Write-Host "Rancher Desktop tools ('nerdctl' or 'docker') not found in PATH." -ForegroundColor Red
    Write-Host "Please install Rancher Desktop from https://rancherdesktop.io/."
    Write-Host "IMPORTANT: During installation or in settings, ensure 'System' access is enabled and tools are added to the system PATH."
    exit 1
}
Write-Host "Rancher Desktop CLI tools... OK" -ForegroundColor Green

# --- 3. Kubectl Verification ---
if (-not (Test-CommandExists kubectl)) {
    Write-Host "kubectl not found in PATH. This should be configured within Rancher Desktop." -ForegroundColor Red
    Write-Host "Please open Rancher Desktop settings -> Kubernetes Settings and ensure 'Enable Kubernetes' is checked."
    exit 1
}
Write-Host "kubectl... OK" -ForegroundColor Green

# --- 4. Verify Cluster is Running ---
Write-Host "Checking if Kubernetes cluster is responsive..."
$kubectlReady = $false
for ($i = 0; $i -lt 30; $i++) {
    kubectl get nodes > $null 2>&1
    if ($LASTEXITCODE -eq 0) {
        $kubectlReady = $true
        break
    }
    Write-Host "Cluster not ready yet, waiting 5 seconds... (Attempt $($i+1)/30)"
    Start-Sleep -Seconds 5
}
if (-not $kubectlReady) {
    Write-Host "Error: Kubernetes cluster is not responding. Please open Rancher Desktop and ensure it has started correctly." -ForegroundColor Red
    exit 1
}
Write-Host "Kubernetes cluster is running." -ForegroundColor Green

# --- 5. Clone MegaParse Repository ---
if (Test-Path ".\MegaParse") {
    Write-Host "MegaParse directory already exists. Skipping clone."
} else {
    Write-Host "Cloning MegaParse repository..."
    git clone https://github.com/QuivrHQ/MegaParse.git
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Failed to clone MegaParse repository." -ForegroundColor Red
        exit 1
    }
}
Write-Host "MegaParse repository... OK" -ForegroundColor Green

Write-Host "`nEnvironment setup complete. You are ready to run the MVP." -ForegroundColor Green