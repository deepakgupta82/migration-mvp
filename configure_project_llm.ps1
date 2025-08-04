# Configure project with LLM provider

$projectId = "e4b76230-b814-4385-b1a7-e989c4189574"
$projectServiceUrl = "http://localhost:8002"

# First, get an authentication token
Write-Host "Getting authentication token..." -ForegroundColor Yellow
try {
    # Use form data for OAuth2PasswordRequestForm
    $loginBody = "username=admin&password=admin123"

    $loginHeaders = @{
        "Content-Type" = "application/x-www-form-urlencoded"
    }

    $tokenResponse = Invoke-RestMethod -Uri "$projectServiceUrl/token" -Method POST -Body $loginBody -Headers $loginHeaders
    $token = $tokenResponse.access_token
    Write-Host "✅ Authentication successful" -ForegroundColor Green
} catch {
    Write-Host "❌ Authentication failed: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "Response body: $responseBody" -ForegroundColor Red
    }
    exit 1
}

# Configure project with LLM provider
Write-Host "Configuring project with LLM provider..." -ForegroundColor Yellow
try {
    $updateBody = @{
        llm_provider = "gemini"
        llm_model = "gemini-2.5-pro"
        llm_api_key_id = "gemini_2.5_pro_1_1754123560"
    } | ConvertTo-Json

    $updateHeaders = @{
        "Content-Type" = "application/json"
        "Authorization" = "Bearer $token"
    }

    $updateResponse = Invoke-RestMethod -Uri "$projectServiceUrl/projects/$projectId" -Method PUT -Body $updateBody -Headers $updateHeaders
    Write-Host "✅ Project configured successfully" -ForegroundColor Green
    Write-Host "   LLM Provider: $($updateResponse.llm_provider)" -ForegroundColor Cyan
    Write-Host "   LLM Model: $($updateResponse.llm_model)" -ForegroundColor Cyan
    Write-Host "   API Key ID: $($updateResponse.llm_api_key_id)" -ForegroundColor Cyan
} catch {
    Write-Host "❌ Project configuration failed: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "Response body: $responseBody" -ForegroundColor Red
    }
    exit 1
}

Write-Host "✅ Project is now ready for document generation!" -ForegroundColor Green
