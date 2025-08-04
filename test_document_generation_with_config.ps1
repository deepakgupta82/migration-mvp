# Test document generation with project configuration

$projectId = "e4b76230-b814-4385-b1a7-e989c4189574"
$backendUrl = "http://localhost:8000"

Write-Host "Testing document generation with manual LLM configuration..." -ForegroundColor Yellow

# Test document generation with explicit LLM configuration in the request
$requestBody = @{
    name = "Infrastructure Assessment Report"
    description = "Comprehensive infrastructure assessment and migration recommendations"
    format = "Professional report with executive summary, technical analysis, and migration roadmap"
    output_type = "pdf"
    # Add LLM configuration directly in the request
    llm_provider = "gemini"
    llm_model = "gemini-2.5-pro"
    llm_api_key_id = "gemini_2.5_pro_1_1754123560"
} | ConvertTo-Json

try {
    $headers = @{
        "Content-Type" = "application/json"
    }
    
    Write-Host "Sending document generation request with LLM config..." -ForegroundColor Cyan
    $response = Invoke-RestMethod -Uri "$backendUrl/api/projects/$projectId/generate-document" -Method POST -Body $requestBody -Headers $headers
    
    Write-Host "✅ Document generation response:" -ForegroundColor Green
    Write-Host ($response | ConvertTo-Json -Depth 3) -ForegroundColor Cyan
    
} catch {
    Write-Host "❌ Document generation failed: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "Response body: $responseBody" -ForegroundColor Red
    }
}

Write-Host "`nTest completed." -ForegroundColor Yellow
