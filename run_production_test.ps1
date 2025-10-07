#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Production test run for D4 Excel file with cache collision fix validation

.DESCRIPTION
    Processes D4_Asset_list_systems_Unix_v22.xlsx through the complete pipeline:
    1. Structured processing (JSONL extraction)
    2. Graph processing (entity/relationship extraction)
    
    Expected Results:
    - ~99 servers extracted across 6 batches
    - Zero cache collisions
    - All batches process independently with unique document IDs

.NOTES
    File Name      : run_production_test.ps1
    Prerequisite   : All services running (backend, document, graph, llm)
    Related Docs   : PRODUCTION_READY_JAN2025.md, CACHE_COLLISION_FIX_VALIDATED.md
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [string]$ProjectId = "d1d78934-bc20-4f0d-b3bf-45d8497642e5",
    
    [Parameter(Mandatory=$false)]
    [string]$Filename = "D4_Asset_list_systems_Unix_v22.xlsx",
    
    [Parameter(Mandatory=$false)]
    [switch]$EnableScatter = $false,
    
    [Parameter(Mandatory=$false)]
    [int]$ScatterMinSeconds = 5,
    
    [Parameter(Mandatory=$false)]
    [int]$ScatterMaxSeconds = 15
)

$ErrorActionPreference = 'Stop'

# Generate correlation ID for tracking
$correlationId = [guid]::NewGuid().ToString()

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "PRODUCTION TEST RUN - D4 Excel File" -ForegroundColor Cyan
Write-Host "Cache Collision Fix Validation" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  Project ID:      $ProjectId"
Write-Host "  Filename:        $Filename"
Write-Host "  Correlation ID:  $correlationId"
Write-Host "  Scatter Delays:  $EnableScatter"
if ($EnableScatter) {
    Write-Host "  Scatter Range:   $ScatterMinSeconds - $ScatterMaxSeconds seconds"
}
Write-Host ""

# Step 1: Structured Processing (JSONL Extraction)
Write-Host "Step 1: Structured Processing (JSONL Extraction)" -ForegroundColor Green
Write-Host "=" * 80 -ForegroundColor Green

$structuredUri = "http://localhost:8003/api/documents/$ProjectId/structured-process/$Filename"
$structuredHeaders = @{
    'X-Correlation-ID' = $correlationId
    'Authorization' = 'Bearer service-backend-token'
    'Content-Type' = 'application/json'
}
$structuredBody = @{
    extract_images = $true
    extract_tables = $true
    include_coordinates = $true
} | ConvertTo-Json

Write-Host "Sending request to: $structuredUri" -ForegroundColor Gray
Write-Host "Correlation ID: $correlationId" -ForegroundColor Gray

try {
    $structuredResponse = Invoke-RestMethod -Uri $structuredUri -Method Post -Headers $structuredHeaders -Body $structuredBody
    Write-Host "✅ Structured processing completed successfully" -ForegroundColor Green
    Write-Host ""
    Write-Host "Response:" -ForegroundColor Gray
    $structuredResponse | ConvertTo-Json -Depth 5 | Write-Host
} catch {
    Write-Host "❌ Structured processing failed" -ForegroundColor Red
    Write-Host "Error: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Waiting 5 seconds before graph processing..." -ForegroundColor Gray
Start-Sleep -Seconds 5

# Step 2: Graph Processing (Entity/Relationship Extraction)
Write-Host ""
Write-Host "Step 2: Graph Processing (Entity/Relationship Extraction)" -ForegroundColor Green
Write-Host "=" * 80 -ForegroundColor Green

# Set scatter environment variables if enabled
if ($EnableScatter) {
    Write-Host "Enabling scatter delays..." -ForegroundColor Yellow
    $env:SCATTER_GRAPH_BATCHES = "true"
    $env:SCATTER_MIN_SECONDS = $ScatterMinSeconds.ToString()
    $env:SCATTER_MAX_SECONDS = $ScatterMaxSeconds.ToString()
    Write-Host "  SCATTER_GRAPH_BATCHES=$env:SCATTER_GRAPH_BATCHES" -ForegroundColor Gray
    Write-Host "  SCATTER_MIN_SECONDS=$env:SCATTER_MIN_SECONDS" -ForegroundColor Gray
    Write-Host "  SCATTER_MAX_SECONDS=$env:SCATTER_MAX_SECONDS" -ForegroundColor Gray
    Write-Host ""
}

# Run graph processing using existing PowerShell script
$graphScriptParams = @{
    ProjectId = $ProjectId
    Filename = $Filename
    CorrelationId = $correlationId
    GraphMaxRetries = 3
    GraphBaseTimeoutSeconds = 300
    GraphMaxTimeoutSeconds = 600
    GraphTableContentMaxChars = 12000
    GraphNarrativeCapChars = 28000
    GraphSpreadsheetCapChars = 20000
    TableGraphBatchChars = 8000
    TableGraphMaxElements = 250  # Full production batch size
}

$graphScriptPath = Join-Path $PSScriptRoot "tools\run_graph_from_jsonl.ps1"

if (-not (Test-Path $graphScriptPath)) {
    Write-Host "❌ Graph processing script not found: $graphScriptPath" -ForegroundColor Red
    exit 1
}

Write-Host "Running graph processing script..." -ForegroundColor Gray
Write-Host "Script: $graphScriptPath" -ForegroundColor Gray
Write-Host ""

try {
    & $graphScriptPath @graphScriptParams
    Write-Host ""
    Write-Host "✅ Graph processing completed" -ForegroundColor Green
} catch {
    Write-Host "❌ Graph processing failed" -ForegroundColor Red
    Write-Host "Error: $_" -ForegroundColor Red
    exit 1
}

# Restore environment variables
if ($EnableScatter) {
    Remove-Item Env:\SCATTER_GRAPH_BATCHES -ErrorAction SilentlyContinue
    Remove-Item Env:\SCATTER_MIN_SECONDS -ErrorAction SilentlyContinue
    Remove-Item Env:\SCATTER_MAX_SECONDS -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "PRODUCTION TEST COMPLETE" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "1. Check logs for [CACHE_FIX] tags showing unique document IDs" -ForegroundColor White
Write-Host "2. Verify NO 'Returning cached result' warnings for different batches" -ForegroundColor White
Write-Host "3. Confirm entity counts in graph service logs:" -ForegroundColor White
Write-Host "   - Batch 1: ~18 entities" -ForegroundColor Gray
Write-Host "   - Batch 2: ~17 entities" -ForegroundColor Gray
Write-Host "   - Batch 3: ~16 entities" -ForegroundColor Gray
Write-Host "   - Batch 4: ~17 entities" -ForegroundColor Gray
Write-Host "   - Batch 5: ~17 entities" -ForegroundColor Gray
Write-Host "   - Batch 6: ~14 entities" -ForegroundColor Gray
Write-Host "   - TOTAL: ~99 entities (expected)" -ForegroundColor White
Write-Host ""

Write-Host "Correlation ID: $correlationId" -ForegroundColor Cyan
Write-Host ""
Write-Host "Use this correlation ID to search logs and validate results" -ForegroundColor Gray
Write-Host ""
