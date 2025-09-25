param(
    [string]$ProjectId = "61502d23-4928-4377-92c8-81b9c4f0fffd",
    [string]$BaseUrl = "http://localhost:8006/api/graphs"
)

$ErrorActionPreference = 'Stop'

function Write-Section($text) {
    Write-Host "`n==== $text ====" -ForegroundColor Cyan
}

Write-Section "Create proposal"
$payload = [ordered]@{
    project_id = $ProjectId
    entities = @(
        @{ name = 'server-smoke-001'; type = 'Server' },
        @{ name = 'app-smoke-A'; type = 'Application' }
    )
    relationships = @(
        @{ type = 'HOSTS'; source = 'server-smoke-001'; target = 'app-smoke-A' }
    )
}
$json = $payload | ConvertTo-Json -Depth 6
Write-Host "POST $BaseUrl/projects/$ProjectId/proposals"
$created = Invoke-RestMethod -Uri "$BaseUrl/projects/$ProjectId/proposals" -Method Post -ContentType 'application/json' -Body $json
$created | ConvertTo-Json -Depth 6
$proposalId = $created.proposal_id
if (-not $proposalId) { throw "Did not receive proposal_id from create response" }
Write-Host "PROPOSAL_ID=$proposalId" -ForegroundColor Yellow

Write-Section "Validate proposal"
Write-Host "POST $BaseUrl/proposals/$proposalId/validate"
$validated = Invoke-RestMethod -Uri "$BaseUrl/proposals/$proposalId/validate" -Method Post
$validated | ConvertTo-Json -Depth 6

Write-Section "Commit proposal"
Write-Host "POST $BaseUrl/proposals/$proposalId/commit"
$committed = Invoke-RestMethod -Uri "$BaseUrl/proposals/$proposalId/commit" -Method Post
$committed | ConvertTo-Json -Depth 6

Write-Section "Get Type Registry"
Write-Host "GET  $BaseUrl/projects/$ProjectId/types"
$types = Invoke-RestMethod -Uri "$BaseUrl/projects/$ProjectId/types" -Method Get
$types | ConvertTo-Json -Depth 6

Write-Section "Done"
Write-Host "Status: OK" -ForegroundColor Green
