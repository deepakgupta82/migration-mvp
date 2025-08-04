# Test document generation for project e4b76230-b814-4385-b1a7-e989c4189574

$projectId = "e4b76230-b814-4385-b1a7-e989c4189574"
$backendUrl = "http://localhost:8000"

# Test 1: Check if project exists
Write-Host "Testing project existence..." -ForegroundColor Yellow
try {
    $projectResponse = Invoke-RestMethod -Uri "$backendUrl/projects" -Method GET
    $project = $projectResponse | Where-Object { $_.id -eq $projectId }
    if ($project) {
        Write-Host "✅ Project found: $($project.name)" -ForegroundColor Green
        Write-Host "   LLM Provider: $($project.llm_provider)" -ForegroundColor Cyan
        Write-Host "   LLM Model: $($project.llm_model)" -ForegroundColor Cyan
    } else {
        Write-Host "❌ Project not found" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ Failed to get projects: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Test 2: Check LLM configurations
Write-Host "`nTesting LLM configurations..." -ForegroundColor Yellow
try {
    $llmConfigs = Invoke-RestMethod -Uri "$backendUrl/llm-configurations" -Method GET
    Write-Host "✅ Found $($llmConfigs.Count) LLM configurations:" -ForegroundColor Green
    foreach ($config in $llmConfigs) {
        Write-Host "   - $($config.name) ($($config.provider)/$($config.model)) - $($config.status)" -ForegroundColor Cyan
    }
} catch {
    Write-Host "❌ Failed to get LLM configurations: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 3: Test document generation
Write-Host "`nTesting document generation..." -ForegroundColor Yellow
$requestBody = @{
    name = "Infrastructure Assessment Report"
    description = "Comprehensive infrastructure assessment and migration recommendations"
    format = "Professional report with executive summary, technical analysis, and migration roadmap"
    output_type = "pdf"
} | ConvertTo-Json

try {
    $headers = @{
        "Content-Type" = "application/json"
    }
    
    Write-Host "Sending document generation request..." -ForegroundColor Cyan
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
