# Document Deletion Test Script
# Tests the complete document deletion workflow including storage, embeddings, and graph data

param(
    [Parameter(Mandatory=$false)]
    [string]$ProjectId = "",
    
    [Parameter(Mandatory=$false)]
    [string]$FileId = "",
    
    [string]$BaseUrl = "http://localhost:8000"
)

function Write-Log {
    param([string]$Message, [string]$Color = "White")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $Message" -ForegroundColor $Color
}

function Test-Deletion {
    param([string]$ProjectId, [string]$FileId)
    
    Write-Log "Testing complete document deletion workflow..." "Cyan"
    Write-Log "Project ID: $ProjectId" "Gray"
    Write-Log "File ID: $FileId" "Gray"
    Write-Log "Base URL: $BaseUrl" "Gray"
    
    try {
        # Test the complete deletion endpoint
        $deleteUrl = "$BaseUrl/api/projects/$ProjectId/files/$FileId"
        Write-Log "Calling DELETE $deleteUrl" "Yellow"
        
        $response = Invoke-WebRequest -Uri $deleteUrl -Method DELETE -ContentType "application/json"
        
        if ($response.StatusCode -eq 200) {
            $result = $response.Content | ConvertFrom-Json
            Write-Log "✅ Deletion successful!" "Green"
            Write-Log "   Message: $($result.message)" "White"
            Write-Log "   Files deleted: $(($result.deleted_files | Measure-Object).Count)" "White"
            Write-Log "   Embeddings deleted: $($result.embeddings_deleted)" "White"
            Write-Log "   Graph nodes deleted: $($result.graph_nodes_deleted)" "White"
            return $true
        } else {
            Write-Log "❌ Deletion failed with status $($response.StatusCode)" "Red"
            Write-Log "   Error: $($response.Content)" "Red"
            return $false
        }
    }
    catch {
        Write-Log "❌ Error during deletion test: $($_.Exception.Message)" "Red"
        if ($_.Exception.Response) {
            $responseStream = $_.Exception.Response.GetResponseStream()
            $reader = New-Object System.IO.StreamReader($responseStream)
            $responseBody = $reader.ReadToEnd()
            Write-Log "   Response: $responseBody" "Red"
        }
        return $false
    }
}

function Show-Usage {
    Write-Host "Usage: .\test_document_deletion.ps1 -ProjectId <project_id> -FileId <file_id>" -ForegroundColor Yellow
    Write-Host "Example: .\test_document_deletion.ps1 -ProjectId ""123e4567-e89b-12d3-a456-426614174000"" -FileId ""abc123""" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Parameters:" -ForegroundColor Cyan
    Write-Host "  -ProjectId  : The project ID (required)" -ForegroundColor White
    Write-Host "  -FileId     : The file ID to delete (required)" -ForegroundColor White
    Write-Host "  -BaseUrl    : The base URL (default: http://localhost:8000)" -ForegroundColor White
}

# Main execution
if ($ProjectId -eq "" -or $FileId -eq "") {
    Show-Usage
    exit 1
}

Write-Host ""
Write-Host "Document Deletion Test Script" -ForegroundColor Green
Write-Host "=" * 40 -ForegroundColor Green
Write-Host ""

$success = Test-Deletion -ProjectId $ProjectId -FileId $FileId

Write-Host ""
Write-Host "=" * 40 -ForegroundColor Green
if ($success) {
    Write-Log "🎉 Test completed successfully!" "Green"
} else {
    Write-Log "❌ Test failed. Check the output above." "Red"
}
Write-Host ""