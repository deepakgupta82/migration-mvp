# Test LLM configuration for the project

$projectId = "e4b76230-b814-4385-b1a7-e989c4189574"
$backendUrl = "http://localhost:8000"

Write-Host "Testing LLM configuration for project..." -ForegroundColor Yellow

try {
    Write-Host "Testing project LLM configuration..." -ForegroundColor Cyan
    $response = Invoke-RestMethod -Uri "$backendUrl/api/projects/$projectId/test-llm" -Method POST
    
    Write-Host "✅ LLM test result:" -ForegroundColor Green
    Write-Host ($response | ConvertTo-Json -Depth 3) -ForegroundColor Cyan
    
} catch {
    Write-Host "❌ LLM test failed: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "Response body: $responseBody" -ForegroundColor Red
    }
}

Write-Host "`nTest completed." -ForegroundColor Yellow
