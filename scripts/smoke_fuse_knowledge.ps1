param(
    [string]$ProjectId = "61502d23-4928-4377-92c8-81b9c4f0fffd",
    [string]$DocServiceUrl = "http://localhost:8003",
    [string]$Token = "service-backend-token",
    [switch]$RegisterOnly
)

$ErrorActionPreference = 'Stop'

$url = "$DocServiceUrl/api/documents/$ProjectId/pvc/fuse-knowledge"
$headers = @{ Authorization = "Bearer $Token" }

$body = @{ status_filter = "validated" }
if ($RegisterOnly) {
    $body = @{
        entity_types = @(
            @{ name = "Company"; description = "Organizations" },
            @{ name = "Person"; description = "Individuals" }
        )
        relationship_types = @(
            @{ name = "EMPLOYS"; from_type = "Company"; to_type = "Person"; description = "Employment relation" }
        )
        register_only = $true
    }
}

$bodyJson = $body | ConvertTo-Json -Depth 6

Write-Host "POST $url"
$response = Invoke-RestMethod -Method Post -Uri $url -Headers $headers -ContentType "application/json" -Body $bodyJson

$response | ConvertTo-Json -Depth 7
