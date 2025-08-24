# setup_venvs_and_start.ps1
Write-Host "=== Fixing Python environments for all services ===" -ForegroundColor Cyan

# Define all services with their paths
$Services = @(
    @{ Name = "Backend";     Path = "backend" },
    @{ Name = "Project";     Path = "project-service" },
    @{ Name = "Reporting";   Path = "reporting-service" },
    @{ Name = "Document";    Path = "services\document-service" },
    @{ Name = "Vector";      Path = "services\vector-service" },
    @{ Name = "Graph";       Path = "services\graph-service" },
    @{ Name = "LLM";         Path = "services\llm-service" },
    @{ Name = "AI Agent";    Path = "services\ai-agent-service" },
    @{ Name = "WebSocket";   Path = "services\websocket-service" },
    @{ Name = "Storage";     Path = "services\storage-service" }
)

foreach ($svc in $Services) {
    $ServiceName = $svc.Name
    $ServicePath = $svc.Path
    Write-Host "`n-------------------------------------------------" -ForegroundColor Gray
    Write-Host "Service: $ServiceName" -ForegroundColor Green
    Write-Host "Path   : $ServicePath" -ForegroundColor DarkCyan

    if (-Not (Test-Path $ServicePath)) {
        Write-Host "  -> Path not found, skipping!" -ForegroundColor Red
        continue
    }

    Push-Location $ServicePath

    # Step 1: Setup venv if not exists
    if (-Not (Test-Path ".venv")) {
        Write-Host "  -> Creating venv in $ServicePath" -ForegroundColor Yellow
        python -m venv .venv
    } else {
        Write-Host "  -> venv already exists." -ForegroundColor Green
    }

    # Step 2: Show Python version
    Write-Host "  -> Using Python:" -ForegroundColor Yellow
    & .\.venv\Scripts\python.exe --version

    # Step 3: Upgrade pip
    Write-Host "  -> Upgrading pip..." -ForegroundColor Yellow
    & .\.venv\Scripts\python.exe -m pip install --upgrade pip

    # Step 4: Install dependencies
    if (Test-Path "requirements.txt") {
        Write-Host "  -> Installing dependencies from requirements.txt..." -ForegroundColor Yellow
        & .\.venv\Scripts\python.exe -m pip install -r requirements.txt -v
    } else {
        Write-Host "  -> No requirements.txt found, skipping dependencies." -ForegroundColor DarkGray
    }

    Pop-Location
}

Write-Host "`n=== Environment setup complete for all services ===" -ForegroundColor Cyan
