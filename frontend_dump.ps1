param(
    [string]$mode = "backend",    # backend or frontend
    [string]$includeFolders = ""  # comma-separated list of folders to include
)

# Root of your project
$root = Get-Location

# Resolve folders to scan
$folders = @()
if ($includeFolders -ne "") {
    $folders = $includeFolders.Split(",") | ForEach-Object { $_.Trim() }
} elseif ($mode -eq "frontend") {
    $folders = @("frontend")
} elseif ($mode -eq "backend") {
    $folders = @("backend", "services")
} else {
    Write-Host "Unknown mode: $mode" -ForegroundColor Red
    exit
}

# Output file
$outputFile = Join-Path $root ("dump_" + $mode + "_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".md")
if (Test-Path $outputFile) { Remove-Item $outputFile }

Write-Host "Scanning folders: $($folders -join ', ')" -ForegroundColor Cyan

# Collect files
$allFiles = @()
foreach ($folder in $folders) {
    $path = Join-Path $root $folder
    if (Test-Path $path) {
        $allFiles += Get-ChildItem -Path $path -Recurse -File
    }
}

# Exclude unwanted folders and test files
$files = $allFiles | Where-Object {
    $_.FullName -notmatch "\\(\.venv|__pycache__|node_modules)(\\|$)" -and
    $_.Name -notmatch "test"
}

if ($files.Count -eq 0) {
    Write-Host "No matching files found." -ForegroundColor Yellow
    exit
}

# Show files found
Write-Host "Found $($files.Count) files:" -ForegroundColor Cyan
$files | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }

# Dump contents
$index = 0
foreach ($file in $files) {
    $index++
    Write-Host "[$index/$($files.Count)] Dumping: $($file.FullName)" -ForegroundColor Green

    $relativePath = $file.FullName.Substring($root.Path.Length).TrimStart('\','/')
    "## File: $relativePath" | Out-File $outputFile -Append -Encoding UTF8

    # Detect language
    $lang = ""
    if ($mode -eq "frontend") {
        switch -Wildcard ($file.Extension) {
            ".js"   { $lang = "javascript" }
            ".jsx"  { $lang = "javascript" }
            ".ts"   { $lang = "typescript" }
            ".tsx"  { $lang = "typescript" }
            ".css"  { $lang = "css" }
            ".scss" { $lang = "scss" }
            ".json" { $lang = "json" }
            default { $lang = "" }
        }
    }
    elseif ($mode -eq "backend") {
        if ($file.Extension -eq ".py") { $lang = "python" }
        elseif ($file.Name -eq "requirements.txt") { $lang = "text" }
    }

    if ($lang -ne "") {
        "```$lang" | Out-File $outputFile -Append -Encoding UTF8
    } else {
        "```" | Out-File $outputFile -Append -Encoding UTF8
    }

    Get-Content $file.FullName | Out-File $outputFile -Append -Encoding UTF8
    '```' | Out-File $outputFile -Append -Encoding UTF8
    "" | Out-File $outputFile -Append -Encoding UTF8
}

Write-Host "Code dump ($mode) created at: $outputFile" -ForegroundColor Green
