# Start AWS Pricing MCP Service
# This script loads AWS credentials from .env.aws and starts the Docker container

param(
    [string]$EnvFile = ".env.aws"
)

$ErrorActionPreference = "Stop"

Write-Host "[*] Starting AWS Pricing MCP Service..." -ForegroundColor Cyan

# Check if .env.aws exists
if (-not (Test-Path $EnvFile)) {
    Write-Host "[ERROR] $EnvFile not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please create $EnvFile with your AWS credentials:" -ForegroundColor Yellow
    Write-Host "  AWS_ACCESS_KEY_ID=your_key" -ForegroundColor Gray
    Write-Host "  AWS_SECRET_ACCESS_KEY=your_secret" -ForegroundColor Gray
    Write-Host "  AWS_REGION=us-east-1" -ForegroundColor Gray
    Write-Host ""
    Write-Host "You can copy the template: Copy-Item .env.aws.template $EnvFile" -ForegroundColor Yellow
    exit 1
}

# Load environment variables from .env.aws
Write-Host "[*] Loading AWS credentials from $EnvFile..." -ForegroundColor Yellow
$envVars = @{}
Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        $key = $matches[1].Trim()
        $value = $matches[2].Trim()
        if ($value) {
            $envVars[$key] = $value
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
            Write-Host "  [OK] Loaded $key" -ForegroundColor Green
        }
    }
}

# Verify required credentials
$required = @("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")
$missing = @()
foreach ($var in $required) {
    if (-not $envVars[$var]) {
        $missing += $var
    }
}

if ($missing.Count -gt 0) {
    Write-Host "[ERROR] Missing required AWS credentials:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    exit 1
}

# Stop existing container if running
Write-Host ""
Write-Host "[*] Stopping existing container (if any)..." -ForegroundColor Yellow
docker-compose stop aws-pricing-mcp 2>$null
docker-compose rm -f aws-pricing-mcp 2>$null

# Start the service
Write-Host ""
Write-Host "[*] Starting AWS Pricing MCP container..." -ForegroundColor Cyan
docker-compose up -d aws-pricing-mcp

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[SUCCESS] AWS Pricing MCP service started successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "[*] Container status:" -ForegroundColor Cyan
    docker-compose ps aws-pricing-mcp
    
    Write-Host ""
    Write-Host "[*] View logs with:" -ForegroundColor Yellow
    Write-Host "  docker-compose logs -f aws-pricing-mcp" -ForegroundColor Gray
    
    Write-Host ""
    Write-Host "[NEXT] Register with AI Agent Service" -ForegroundColor Cyan
    Write-Host "  cd services/ai-agent-service" -ForegroundColor Gray
    Write-Host "  .venv\Scripts\python.exe scripts/init_aws_pricing_mcp.py --docker" -ForegroundColor Gray
} else {
    Write-Host ""
    Write-Host "[ERROR] Failed to start AWS Pricing MCP service" -ForegroundColor Red
    Write-Host "Check logs with: docker-compose logs aws-pricing-mcp" -ForegroundColor Yellow
    exit 1
}
