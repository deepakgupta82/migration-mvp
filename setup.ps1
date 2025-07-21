# Nagarro AgentiMigrate MVP Environment Setup for Windows
Start-Transcript -Path "logs/setup.log" -Append
Write-Host "Starting Nagarro AgentiMigrate MVP Environment Setup for Windows..."

$tools = @(
    @{ Name = "Git"; Command = "git.exe"; WingetId = "Git.Git"; PathGuess = "C:\Program Files\Git\cmd" },
    @{ Name = "Rancher Desktop"; Command = "rancher-desktop.exe"; WingetId = "Rancher.RancherDesktop"; PathGuess = "C:\Program Files\Rancher Desktop" },
    @{ Name = "kubectl"; Command = "kubectl.exe"; WingetId = "Kubernetes.kubectl"; PathGuess = "$env:USERPROFILE\.rd\bin" }
)
$results = @()

foreach ($tool in $tools) {
    $found = $false
    $cmd = Get-Command $tool.Command -ErrorAction SilentlyContinue
    if ($cmd) {
        $found = $true
        $toolPath = Split-Path $cmd.Source
    } elseif (Test-Path $tool.PathGuess) {
        $found = $true
        $toolPath = $tool.PathGuess
    } else {
        Write-Host "$($tool.Name) not found. Installing..."
        winget install --id $tool.WingetId -e --silent
        $cmd = Get-Command $tool.Command -ErrorAction SilentlyContinue
        if ($cmd) {
            $found = $true
            $toolPath = Split-Path $cmd.Source
        } elseif (Test-Path $tool.PathGuess) {
            $found = $true
            $toolPath = $tool.PathGuess
        } else {
            $toolPath = ""
        }
    }
    if ($found -and $toolPath -and ($env:PATH -notlike "*$toolPath*")) {
        $env:PATH = "$toolPath;$env:PATH"
        Write-Host "Added $($tool.Name) to PATH: $toolPath"
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
} else {
    Write-Host "Kubernetes cluster running."
}

# Clone MegaParse repository if not present
if (Test-Path ".\MegaParse") {
    Write-Host "MegaParse directory already exists. Skipping clone."
} else {
    git clone https://github.com/QuivrHQ/MegaParse.git
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Failed to clone MegaParse repository."
    } else {
        Write-Host "MegaParse repository cloned successfully."
    }
}

Write-Host "Environment setup complete. You can now proceed with the project build."
Stop-Transcript
