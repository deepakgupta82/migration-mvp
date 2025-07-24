# Nagarro AgentiMigrate Platform - Windows Environment Setup
Write-Host "🚀 Nagarro AgentiMigrate Platform - Windows Setup" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

# Create logs directory if it doesn't exist
if (!(Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" -Force | Out-Null
}

# Enhanced logging setup
$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$logFile = "logs/setup_$timestamp.log"
$masterLogFile = "logs/platform_master.log"

# Function for enhanced logging
function Write-LogMessage {
    param(
        [string]$Message,
        [string]$Level = "INFO",
        [string]$Color = "White"
    )
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] $Message"

    # Write to console with color
    Write-Host $Message -ForegroundColor $Color

    # Write to both session log and master log
    Add-Content -Path $logFile -Value $logEntry -Encoding UTF8
    Add-Content -Path $masterLogFile -Value $logEntry -Encoding UTF8
}

Start-Transcript -Path $logFile -Append
Write-LogMessage "=== NAGARRO AGENTIMIGRATE PLATFORM SETUP STARTED ===" "INFO" "Cyan"
Write-LogMessage "Setup Log File: $logFile" "INFO" "Gray"
Write-LogMessage "Master Log File: $masterLogFile" "INFO" "Gray"
Write-LogMessage "PowerShell Version: $($PSVersionTable.PSVersion)" "INFO" "Gray"
Write-LogMessage "Windows Version: $(Get-CimInstance Win32_OperatingSystem | Select-Object -ExpandProperty Caption)" "INFO" "Gray"
Write-LogMessage "Current User: $env:USERNAME" "INFO" "Gray"
Write-LogMessage "Current Directory: $(Get-Location)" "INFO" "Gray"

$tools = @(
    @{ Name = "Git"; Command = "git.exe"; WingetId = "Git.Git"; PathGuess = "C:\Program Files\Git\cmd" },
    @{ Name = "Rancher Desktop"; Command = "rdctl.exe"; WingetId = "Rancher.RancherDesktop"; PathGuess = "$env:USERPROFILE\.rd\bin" }
)
$results = @()

foreach ($tool in $tools) {
    Write-LogMessage "Checking for $($tool.Name)..." "INFO" "Yellow"
    $found = $false

    try {
        $cmd = Get-Command $tool.Command -ErrorAction SilentlyContinue
        if ($cmd) {
            $found = $true
            $toolPath = Split-Path $cmd.Source
            Write-LogMessage "✅ $($tool.Name) found in PATH at $toolPath" "SUCCESS" "Green"
        } elseif (Test-Path $tool.PathGuess) {
            $found = $true
            $toolPath = $tool.PathGuess
            Write-LogMessage "✅ $($tool.Name) found at guessed path: $toolPath" "SUCCESS" "Green"
        } else {
            Write-LogMessage "$($tool.Name) not found. Attempting installation..." "WARNING" "Yellow"
            Write-LogMessage "Running: winget install --id $($tool.WingetId) -e --silent" "INFO" "Gray"

            winget install --id $tool.WingetId -e --silent

            if ($LASTEXITCODE -eq 0) {
                Write-LogMessage "Winget installation completed with exit code: $LASTEXITCODE" "INFO" "Gray"
            } else {
                Write-LogMessage "Winget installation failed with exit code: $LASTEXITCODE" "ERROR" "Red"
            }

            # Re-check after installation
            $cmd = Get-Command $tool.Command -ErrorAction SilentlyContinue
            if ($cmd) {
                $found = $true
                $toolPath = Split-Path $cmd.Source
                Write-LogMessage "✅ $($tool.Name) successfully installed and found at $toolPath" "SUCCESS" "Green"
            } elseif (Test-Path $tool.PathGuess) {
                $found = $true
                $toolPath = $tool.PathGuess
                Write-LogMessage "✅ $($tool.Name) found at guessed path after installation: $toolPath" "SUCCESS" "Green"
            } else {
                $toolPath = ""
                Write-LogMessage "❌ $($tool.Name) installation failed or not found after installation" "ERROR" "Red"
            }
        }

        if ($found -and $toolPath -and ($env:PATH -notlike "*$toolPath*")) {
            $env:PATH = "$toolPath;$env:PATH"
            Write-LogMessage "Added $($tool.Name) to PATH: $toolPath" "INFO" "Gray"
        }
    } catch {
        Write-LogMessage "Exception while checking $($tool.Name): $($_.Exception.Message)" "ERROR" "Red"
        $toolPath = ""
    }

    $results += [PSCustomObject]@{
        Tool = $tool.Name
        Installed = $found
        Path = $toolPath
    }
}

Write-Host "`n--- Setup Summary ---"
foreach ($result in $results) {
    if ($result.Installed) {
        Write-Host "$($result.Tool): Installed at $($result.Path)"
    } else {
        Write-Host "$($result.Tool): NOT INSTALLED. Please install manually."
    }
}

# Check Rancher Desktop status
Write-Host "🔍 Checking Rancher Desktop status..." -ForegroundColor Yellow
try {
    # Check if Rancher Desktop is installed
    $rancherPath = "$env:USERPROFILE\.rd\bin\rdctl.exe"
    if (Test-Path $rancherPath) {
        Write-Host "✅ Rancher Desktop is installed" -ForegroundColor Green
    } else {
        Write-Host "❌ Rancher Desktop not found. Please install it." -ForegroundColor Red
        Write-Host "   Download from: https://rancherdesktop.io/" -ForegroundColor Yellow
        exit 1
    }

    # Check if Docker is available (through Rancher Desktop)
    $dockerVersion = docker --version 2>$null
    if ($dockerVersion) {
        Write-Host "✅ Docker is available: $dockerVersion" -ForegroundColor Green
    } else {
        Write-Host "❌ Docker not available. Please ensure Rancher Desktop is running." -ForegroundColor Red
        Write-Host "   1. Start Rancher Desktop from Start Menu" -ForegroundColor Yellow
        Write-Host "   2. Wait for it to fully start (may take 2-3 minutes)" -ForegroundColor Yellow
        Write-Host "   3. Ensure 'dockerd (moby)' is selected as container runtime" -ForegroundColor Yellow
        exit 1
    }

    # Check if Docker daemon is running
    docker ps > $null 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Docker daemon is running" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Docker daemon is not running. Please start Rancher Desktop." -ForegroundColor Yellow
        Write-Host "   Waiting for Docker daemon to start..." -ForegroundColor Yellow

        # Wait for Docker to start
        $dockerReady = $false
        for ($i = 0; $i -lt 60; $i++) {
            docker ps > $null 2>&1
            if ($LASTEXITCODE -eq 0) {
                $dockerReady = $true
                break
            }
            Start-Sleep -Seconds 5
            Write-Host "   Still waiting... ($($i * 5) seconds)" -ForegroundColor Gray
        }

        if ($dockerReady) {
            Write-Host "✅ Docker daemon is now running" -ForegroundColor Green
        } else {
            Write-Host "❌ Error: Docker daemon failed to start. Please check Rancher Desktop." -ForegroundColor Red
            Write-Host "   1. Open Rancher Desktop from Start Menu" -ForegroundColor Yellow
            Write-Host "   2. Go to Settings and ensure 'dockerd (moby)' is selected" -ForegroundColor Yellow
            Write-Host "   3. Wait for it to fully start" -ForegroundColor Yellow
            Write-Host "   4. Run this script again" -ForegroundColor Yellow
            exit 1
        }
    }

    # Check Docker Compose
    try {
        $composeVersion = docker compose version 2>$null
        if ($composeVersion) {
            Write-Host "✅ Docker Compose is available: $composeVersion" -ForegroundColor Green
        } else {
            # Try legacy docker-compose
            $composeVersion = docker-compose --version 2>$null
            if ($composeVersion) {
                Write-Host "✅ Docker Compose (legacy) is available: $composeVersion" -ForegroundColor Green
            } else {
                Write-Host "❌ Error: Docker Compose not available" -ForegroundColor Red
                Write-Host "   Please ensure Rancher Desktop is properly configured" -ForegroundColor Yellow
                exit 1
            }
        }
    } catch {
        Write-Host "❌ Error: Docker Compose not available" -ForegroundColor Red
        exit 1
    }

} catch {
    Write-Host "❌ Error: Rancher Desktop not found or not working properly" -ForegroundColor Red
    Write-Host "   Please install Rancher Desktop from: https://rancherdesktop.io/" -ForegroundColor Yellow
    exit 1
}

# Check system requirements
Write-Host "📊 Checking system requirements..." -ForegroundColor Yellow

# Check available RAM
$totalRAM = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
Write-Host "   Total RAM: $totalRAM GB" -ForegroundColor Gray
if ($totalRAM -lt 8) {
    Write-Host "⚠️  Warning: Less than 8GB RAM detected. Platform may run slowly." -ForegroundColor Yellow
    Write-Host "   Recommended: 16GB RAM for optimal performance" -ForegroundColor Yellow
} else {
    Write-Host "✅ Sufficient RAM available" -ForegroundColor Green
}

# Check available disk space
$freeSpace = [math]::Round((Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'").FreeSpace / 1GB, 1)
Write-Host "   Free disk space: $freeSpace GB" -ForegroundColor Gray
if ($freeSpace -lt 10) {
    Write-Host "⚠️  Warning: Less than 10GB free space. May not be sufficient." -ForegroundColor Yellow
} else {
    Write-Host "✅ Sufficient disk space available" -ForegroundColor Green
}

# Clone MegaParse repository if not present
Write-Host "💾 Checking MegaParse repository..." -ForegroundColor Yellow
if (Test-Path ".\MegaParse") {
    Write-Host "✅ MegaParse directory already exists" -ForegroundColor Green
} else {
    Write-Host "   Cloning MegaParse repository..." -ForegroundColor Gray
    git clone https://github.com/QuivrHQ/MegaParse.git
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Error: Failed to clone MegaParse repository" -ForegroundColor Red
        exit 1
    } else {
        Write-Host "✅ MegaParse repository cloned successfully" -ForegroundColor Green
    }
}

# Create .env file if it doesn't exist
Write-Host "🔧 Setting up environment configuration..." -ForegroundColor Yellow
if (!(Test-Path ".env")) {
    Write-Host "   Creating .env file..." -ForegroundColor Gray
    @"
# Nagarro AgentiMigrate Platform Configuration
# OpenAI API Key (Required for AI agents)
OPENAI_API_KEY=your_openai_api_key_here

# Alternative LLM Providers (Optional)
# ANTHROPIC_API_KEY=your_anthropic_key_here
# GOOGLE_API_KEY=your_google_key_here

# LLM Provider Selection (openai, anthropic, google)
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

# Service URLs (Internal Docker network)
PROJECT_SERVICE_URL=http://project-service:8000
REPORTING_SERVICE_URL=http://reporting-service:8000
WEAVIATE_URL=http://weaviate:8080
NEO4J_URL=bolt://neo4j:7687
OBJECT_STORAGE_ENDPOINT=minio:9000
"@ | Out-File -FilePath ".env" -Encoding UTF8
    Write-Host "✅ .env file created" -ForegroundColor Green
    Write-Host "⚠️  IMPORTANT: Please edit .env file and add your OpenAI API key!" -ForegroundColor Yellow
    Write-Host "   You can get one from: https://platform.openai.com/api-keys" -ForegroundColor Yellow
} else {
    Write-Host "✅ .env file already exists" -ForegroundColor Green
}

# Create necessary directories
Write-Host "📁 Creating necessary directories..." -ForegroundColor Yellow
$directories = @("minio_data", "postgres_data", "logs")
foreach ($dir in $directories) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "   Created: $dir" -ForegroundColor Gray
    }
}
Write-Host "✅ Directories ready" -ForegroundColor Green

Write-Host ""
Write-Host "✨ Environment setup complete!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "🚀 Next steps:" -ForegroundColor Cyan
Write-Host "   1. Edit .env file and add your OpenAI API key" -ForegroundColor Yellow
Write-Host "   2. Run: .\build-optimized.bat" -ForegroundColor Yellow
Write-Host "   3. Access platform at: http://localhost:3000" -ForegroundColor Yellow
Write-Host ""
Write-Host "📚 Documentation:" -ForegroundColor Cyan
Write-Host "   - Quick Start: QUICK_START.md" -ForegroundColor Gray
Write-Host "   - Full README: README.md" -ForegroundColor Gray
Write-Host ""

Stop-Transcript
