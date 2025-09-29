param(
    [Parameter(Mandatory=$true)][string]$ProjectId,
    [string]$BaseUrl = "http://localhost:8006/api/graphs"
)

$ErrorActionPreference = 'Stop'

$uri = "$BaseUrl/projects/$ProjectId/maintenance/materialize-ip-edges"
Write-Host "Calling: $uri"
$response = Invoke-RestMethod -Uri $uri -Method Post
$response | ConvertTo-Json -Depth 6
