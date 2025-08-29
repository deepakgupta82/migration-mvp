# Save this as dump-code.ps1 and run in PowerShell
# It will prompt you for a folder path

# Ask for source folder
$sourceFolder = Read-Host "Enter the full path of the source folder"

# Validate path
if (-Not (Test-Path $sourceFolder)) {
    Write-Host "❌ The folder path does not exist." -ForegroundColor Red
    exit
}

# Markdown output file
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outputFile = Join-Path $sourceFolder "code_dump_$timestamp.md"

# Start writing header
"# Code Dump - $timestamp" | Out-File $outputFile -Encoding UTF8
"Source folder: $sourceFolder" | Out-File $outputFile -Append -Encoding UTF8
"" | Out-File $outputFile -Append

# Get all .py and requirements.txt files recursively
$files = Get-ChildItem -Path $sourceFolder -Recurse -Include *.py, requirements.txt

foreach ($file in $files) {
    $relativePath = $file.FullName.Substring($sourceFolder.Length).TrimStart('\','/')
    "## File: $relativePath" | Out-File $outputFile -Append -Encoding UTF8
    '```python' | Out-File $outputFile -Append -Encoding UTF8
    Get-Content $file.FullName | Out-File $outputFile -Append -Encoding UTF8
    '```' | Out-File $outputFile -Append -Encoding UTF8
    "" | Out-File $outputFile -Append -Encoding UTF8
}

Write-Host "✅ Code dump created at: $outputFile" -ForegroundColor Green
