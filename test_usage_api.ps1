# Smoke test for project-service usage API (PowerShell)
# Usage: powershell -ExecutionPolicy Bypass -File .\test_usage_api.ps1

$ErrorActionPreference = 'Stop'

# Config
$serviceToken = 'service-backend-token'
$baseUrl = 'http://localhost:8002/api/usage/llm-calls'

# Generate a unique correlation ID
$correlationId = [guid]::NewGuid().Guid

# Prepare payload
$payload = @{
    provider = 'openai'
    model = 'gpt-4o-mini'
    task_id = 'smoke-test'
    correlation_id = $correlationId
    input_tokens = 5
    output_tokens = 7
    total_tokens = 12
    duration_ms = 123
    status = 'success'
} | ConvertTo-Json

# POST usage record
Write-Host "Posting usage record..."
$response = Invoke-RestMethod -Uri $baseUrl -Headers @{ Authorization = "Bearer $serviceToken" } -Method Post -ContentType 'application/json' -Body $payload
$response | ConvertTo-Json -Depth 5 | Write-Host


# GET usage record by correlation_id
Start-Sleep -Seconds 1
Write-Host "Fetching usage record by correlation_id..."
# Ensure the query string is properly encoded and the URL is valid
$encodedCorrelationId = [System.Uri]::EscapeDataString($correlationId)
$queryUrl = $baseUrl + "?correlation_id=" + $encodedCorrelationId + "&limit=1"
Write-Host ("Query URL: " + $queryUrl)
$getResponse = Invoke-RestMethod -Uri $queryUrl -Headers @{ Authorization = "Bearer $serviceToken" } -Method Get
$getResponse | ConvertTo-Json -Depth 5 | Write-Host

Write-Host "Smoke test complete."
