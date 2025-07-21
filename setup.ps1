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

# Check Docker installation
if (-not (Get-Command docker.exe -ErrorAction SilentlyContinue)) {
    Write-Host "Docker not found. Installing Docker Desktop..."
    winget install --id Docker.DockerDesktop -e --silent
    if (-not (Get-Command docker.exe -ErrorAction SilentlyContinue)) {
        Write-Host "Error: Docker installation failed."
        exit 1
    }
}
Write-Host "Docker... OK"

# Check Minikube installation
if (-not (Get-Command minikube.exe -ErrorAction SilentlyContinue)) {
    Write-Host "Minikube not found. Installing Minikube..."
    winget install --id Kubernetes.Minikube -e --silent
    if (-not (Get-Command minikube.exe -ErrorAction SilentlyContinue)) {
        Write-Host "Error: Minikube installation failed."
        exit 1
    }
}
Write-Host "Minikube... OK"

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

# Start Minikube
Write-Host "Starting Minikube cluster..."
minikube start --driver=docker
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Minikube failed to start."
    exit 1
}
Write-Host "Minikube cluster running."

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
