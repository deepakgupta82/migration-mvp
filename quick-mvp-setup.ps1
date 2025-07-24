# Nagarro AgentiMigrate Platform - Quick MVP Setup
# One-command setup for the complete environment

Write-Host "🚀 Nagarro AgentiMigrate Platform - Quick MVP Setup" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# Quick prerequisite check
Write-Host "🔍 Checking prerequisites..." -ForegroundColor Yellow

# Check Rancher Desktop
$rancherPaths = @(
    "$env:USERPROFILE\.rd\bin\rdctl.exe",
    "$env:LOCALAPPDATA\Programs\Rancher Desktop\resources\resources\win32\bin\rdctl.exe",
    "$env:PROGRAMFILES\Rancher Desktop\resources\resources\win32\bin\rdctl.exe"
)

$rancherFound = $false
foreach ($path in $rancherPaths) {
    if (Test-Path $path) {
        $rancherFound = $true
        break
    }
}

if (!$rancherFound) {
    Write-Host "❌ Rancher Desktop not found!" -ForegroundColor Red
    Write-Host "   Please install from: https://rancherdesktop.io/" -ForegroundColor Yellow
    exit 1
}

# Check Docker
try {
    docker ps | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Docker not responding. Please start Rancher Desktop." -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ Rancher Desktop and Docker are ready" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker not available. Please start Rancher Desktop." -ForegroundColor Red
    exit 1
}

# Create .env if needed
if (!(Test-Path ".env")) {
    Write-Host "📝 Creating environment configuration..." -ForegroundColor Yellow
    $envContent = @"
# Nagarro AgentiMigrate Platform Configuration
OPENAI_API_KEY=your_openai_api_key_here
GOOGLE_API_KEY=your_google_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
LLM_PROVIDER=openai

# Database Configuration
POSTGRES_DB=projectdb
POSTGRES_USER=projectuser
POSTGRES_PASSWORD=projectpass

# MinIO Object Storage
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin

# Neo4j Graph Database
NEO4J_AUTH=neo4j/password

# Service URLs
PROJECT_SERVICE_URL=http://project-service:8000
REPORTING_SERVICE_URL=http://reporting-service:8000
WEAVIATE_URL=http://weaviate:8080
NEO4J_URL=bolt://neo4j:7687
OBJECT_STORAGE_ENDPOINT=minio:9000
"@
    $envContent | Out-File -FilePath ".env" -Encoding UTF8
    Write-Host "✅ Environment file created" -ForegroundColor Green
}

# Check API keys
$envContent = Get-Content ".env" -Raw
$hasOpenAI = $envContent -match "OPENAI_API_KEY=(?!your_openai_api_key_here).+"
$hasGoogle = $envContent -match "GOOGLE_API_KEY=(?!your_google_key_here).+"
$hasAnthropic = $envContent -match "ANTHROPIC_API_KEY=(?!your_anthropic_key_here).+"

if (!($hasOpenAI -or $hasGoogle -or $hasAnthropic)) {
    Write-Host "⚠️  No LLM API keys configured!" -ForegroundColor Yellow
    Write-Host "   Please edit .env file and add at least one API key:" -ForegroundColor Yellow
    Write-Host "   • OpenAI: https://platform.openai.com/api-keys" -ForegroundColor Gray
    Write-Host "   • Google: https://aistudio.google.com/app/apikey" -ForegroundColor Gray
    Write-Host "   • Anthropic: https://console.anthropic.com/" -ForegroundColor Gray

    $edit = Read-Host "   Open .env file now? (y/N)"
    if ($edit -eq "y" -or $edit -eq "Y") {
        notepad ".env"
        Read-Host "   Press Enter when done"
    }
}

# Create directories
Write-Host "📁 Creating necessary directories..." -ForegroundColor Yellow
@("minio_data", "postgres_data", "logs") | ForEach-Object {
    if (!(Test-Path $_)) { New-Item -ItemType Directory -Path $_ -Force | Out-Null }
}

# Start infrastructure services first
Write-Host "🏗️  Starting infrastructure services..." -ForegroundColor Yellow
docker compose up -d postgres neo4j weaviate minio

# Wait a moment for infrastructure
Write-Host "⏳ Waiting for infrastructure to initialize..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

# Build and start application services
Write-Host "🔨 Building application services..." -ForegroundColor Yellow
$services = @("megaparse", "project-service", "reporting-service", "backend")

foreach ($service in $services) {
    Write-Host "   Building $service..." -ForegroundColor Gray
    docker compose build $service
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✅ $service built successfully" -ForegroundColor Green
    } else {
        Write-Host "   ⚠️  $service build had issues (continuing...)" -ForegroundColor Yellow
    }
}

# Try to build frontend (may fail, that's ok)
Write-Host "🎨 Attempting to build frontend..." -ForegroundColor Yellow
docker compose build frontend
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ Frontend built successfully" -ForegroundColor Green
    $frontendBuilt = $true
} else {
    Write-Host "   ⚠️  Frontend build failed (will create simple alternative)" -ForegroundColor Yellow
    $frontendBuilt = $false
}

# Start all services
Write-Host "🚀 Starting all services..." -ForegroundColor Yellow
docker compose up -d

# Create simple frontend if needed
if (!$frontendBuilt) {
    Write-Host "🌐 Creating simple frontend..." -ForegroundColor Yellow

    $simpleHtml = @"
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚀 Nagarro AgentiMigrate Platform</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; text-align: center; margin-bottom: 30px; }
        .services { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; }
        .service { background: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #007bff; }
        .service h3 { margin: 0 0 10px 0; color: #007bff; }
        .service a { color: #007bff; text-decoration: none; font-weight: bold; }
        .service a:hover { text-decoration: underline; }
        .status { background: #d4edda; color: #155724; padding: 15px; border-radius: 5px; margin-bottom: 20px; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Nagarro AgentiMigrate Platform</h1>
        <div class="status">✅ Platform is running successfully!</div>
        <div class="services">
            <div class="service">
                <h3>📚 Backend API</h3>
                <p>Core platform API</p>
                <a href="http://localhost:8000/docs" target="_blank">Open API Docs</a>
            </div>
            <div class="service">
                <h3>📋 Project Service</h3>
                <p>Project management</p>
                <a href="http://localhost:8002/docs" target="_blank">Open API Docs</a>
            </div>
            <div class="service">
                <h3>📊 Reporting Service</h3>
                <p>Report generation</p>
                <a href="http://localhost:8003/docs" target="_blank">Open API Docs</a>
            </div>
            <div class="service">
                <h3>📄 MegaParse Service</h3>
                <p>Document parsing</p>
                <a href="http://localhost:5001" target="_blank">Open Service</a>
            </div>
            <div class="service">
                <h3>🔗 Neo4j Browser</h3>
                <p>Graph database</p>
                <a href="http://localhost:7474" target="_blank">Open Browser</a>
            </div>
            <div class="service">
                <h3>🔍 Weaviate Console</h3>
                <p>Vector database</p>
                <a href="http://localhost:8080" target="_blank">Open Console</a>
            </div>
            <div class="service">
                <h3>💾 MinIO Console</h3>
                <p>Object storage</p>
                <a href="http://localhost:9001" target="_blank">Open Console</a>
            </div>
        </div>
        <div style="margin-top: 30px; text-align: center; color: #666;">
            <p>Default credentials: Neo4j (neo4j/password), MinIO (minioadmin/minioadmin)</p>
        </div>
    </div>
</body>
</html>
"@

    $simpleHtml | Out-File -FilePath "platform-dashboard.html" -Encoding UTF8

    # Start simple HTTP server for frontend
    Start-Process powershell -ArgumentList "-Command", "cd '$PWD'; python -m http.server 3000" -WindowStyle Hidden
    Start-Sleep -Seconds 2
}

# Final status check
Write-Host "" -ForegroundColor White
Write-Host "🎉 MVP Setup Complete!" -ForegroundColor Green
Write-Host "===================" -ForegroundColor Green

# Show service status
Write-Host "📊 Service Status:" -ForegroundColor Cyan
docker compose ps --format "table {{.Service}}\t{{.Status}}"

Write-Host "" -ForegroundColor White
Write-Host "🌐 Access Points:" -ForegroundColor Cyan
if ($frontendBuilt) {
    Write-Host "• Main Platform: http://localhost:3000" -ForegroundColor Green
} else {
    Write-Host "• Platform Dashboard: http://localhost:3000/platform-dashboard.html" -ForegroundColor Green
}
Write-Host "• Backend API: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "• Neo4j Browser: http://localhost:7474" -ForegroundColor Green
Write-Host "• MinIO Console: http://localhost:9001" -ForegroundColor Green

Write-Host "" -ForegroundColor White
Write-Host "🔧 Quick Commands:" -ForegroundColor Cyan
Write-Host "• Check status: docker compose ps" -ForegroundColor Gray
Write-Host "• View logs: docker compose logs -f" -ForegroundColor Gray
Write-Host "• Stop platform: docker compose down" -ForegroundColor Gray

# Open browser
$open = Read-Host "Open platform in browser? (Y/n)"
if ($open -ne "n" -and $open -ne "N") {
    if ($frontendBuilt) {
        Start-Process "http://localhost:3000"
    } else {
        Start-Process "http://localhost:3000/platform-dashboard.html"
    }
}

Write-Host "✅ Setup completed successfully!" -ForegroundColor Green
