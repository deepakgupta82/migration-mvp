# Configure project LLM via backend endpoint

$projectId = "e4b76230-b814-4385-b1a7-e989c4189574"
$backendUrl = "http://localhost:8000"

Write-Host "Configuring project LLM via backend..." -ForegroundColor Yellow

$updateBody = @{
    llm_provider = "gemini"
    llm_model = "gemini-2.5-pro"
    llm_api_key_id = "gemini_2.5_pro_1_1754123560"
} | ConvertTo-Json

try {
    $headers = @{
        "Content-Type" = "application/json"
    }
    
    Write-Host "Updating project configuration..." -ForegroundColor Cyan
    $response = Invoke-RestMethod -Uri "$backendUrl/projects/$projectId" -Method PUT -Body $updateBody -Headers $headers
    
    Write-Host "✅ Project updated successfully:" -ForegroundColor Green
    Write-Host ($response | ConvertTo-Json -Depth 3) -ForegroundColor Cyan
    
} catch {
    Write-Host "❌ Project update failed: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "Response body: $responseBody" -ForegroundColor Red
    }
}

Write-Host "`nConfiguration completed." -ForegroundColor Yellow
