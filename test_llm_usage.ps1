# Smoke test: llm-service → usage ingestion (PowerShell)
# Usage: powershell -ExecutionPolicy Bypass -File .\test_llm_usage.ps1

$ErrorActionPreference = 'Stop'

# Config
$serviceToken = 'service-backend-token'
$llmUrl = 'http://localhost:8007/api/llm/process'
$usageListBase = 'http://localhost:8002/api/usage/llm-calls'

# Correlation and project
$correlationId = [guid]::NewGuid().Guid
# Use a known project id from your environment; adjust if needed
$projectId = 'd1d78934-bc20-4f0d-b3bf-45d8497642e5'

Write-Host "Calling llm-service /api/llm/process (corr=$correlationId)..."
$headers = @{ 'X-Correlation-ID' = $correlationId; Authorization = "Bearer $serviceToken" }
$body = @{ process_type = 'conversation'; prompt = 'Say hello briefly.'; project_id = $projectId; allow_global = $true } | ConvertTo-Json

try {
  $resp = Invoke-RestMethod -Uri $llmUrl -Headers $headers -Method Post -ContentType 'application/json' -Body $body
  Write-Host 'LLM response:'
  $resp | ConvertTo-Json -Depth 6 | Write-Host
} catch {
  Write-Warning "LLM call failed (this is okay for usage ingestion testing): $($_.Exception.Message)"
}

Start-Sleep -Seconds 1

Write-Host "Fetching usage by correlation_id..."
$encodedCorr = [System.Uri]::EscapeDataString($correlationId)
$usageUrl = "${usageListBase}?correlation_id=$encodedCorr&limit=5"
Write-Host ("Query URL: " + $usageUrl)
$uriObj = [System.Uri]::new($usageUrl)
$usage = Invoke-RestMethod -Uri $uriObj -Headers @{ Authorization = "Bearer $serviceToken" } -Method Get
$usage | ConvertTo-Json -Depth 6 | Write-Host

Write-Host 'Done.'
