# Nagarro AgentiMigrate MVP Environment Setup for Windows

Write-Host "Starting Nagarro AgentiMigrate MVP Environment Setup for Windows..."

# Check Git installation
if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Git is not installed or not in PATH. Please install Git and try again."
    exit 1
} else {
    Write-Host "Git... OK"
}

# Check Docker installation
if (-not (Get-Command docker.exe -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Docker is not installed or not in PATH. Please install Docker Desktop and try again."
    exit 1
} else {
    Write-Host "Docker... OK"
}

# Check Docker daemon status
docker info > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Docker daemon is not running. Please start Docker Desktop and try again."
    exit 1
} else {
    Write-Host "Docker daemon... OK"
}

# Check Docker Compose installation
if (-not (Get-Command docker-compose.exe -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Docker Compose is not installed or not in PATH. Please install Docker Compose and try again."
    exit 1
} else {
    Write-Host "Docker Compose... OK"
}

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
