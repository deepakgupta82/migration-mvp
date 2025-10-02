# E2E: AI-agent-service → project-service usage logging (Windows PowerShell)
# - Triggers crew document run
# - Then queries project-service for agent-runs and agent-events by correlation id

param(
  [string]$ProjectId = 'd1d78934-bc20-4f0d-b3bf-45d8497642e5',
  [string]$DocType = 'Project Summary'
)

$ErrorActionPreference = 'Stop'

$CorrelationId = [guid]::NewGuid().Guid
Write-Host "CorrelationId: $CorrelationId"

$agentUrl = 'http://localhost:8008/api/agents/projects/{0}/crews/document/run' -f $ProjectId
$headers = @{ 'Authorization' = 'Bearer service-backend-token'; 'X-Correlation-ID' = $CorrelationId }
$body = @{ document_type = $DocType; document_description = 'Short summary doc'; output_format = 'markdown' } | ConvertTo-Json

Write-Host "POST $agentUrl"
$resp = Invoke-RestMethod -Uri $agentUrl -Method Post -Headers $headers -Body $body -ContentType 'application/json'
$jobId = $resp.job_id
Write-Host "Job started: $jobId"

Start-Sleep -Seconds 3

$usageBase = 'http://localhost:8002/api/usage'
$agentRunsUrl = "$usageBase/agent-runs?correlation_id=$CorrelationId&limit=5"
Write-Host "GET $agentRunsUrl"
$agentRuns = Invoke-RestMethod -Uri $agentRunsUrl -Method Get -Headers @{ Authorization = 'Bearer service-backend-token' }
$agentRuns | ConvertTo-Json -Depth 5

$agentEventsUrl = "$usageBase/agent-events?correlation_id=$CorrelationId&limit=10"
Write-Host "GET $agentEventsUrl"
$agentEvents = Invoke-RestMethod -Uri $agentEventsUrl -Method Get -Headers @{ Authorization = 'Bearer service-backend-token' }
$agentEvents | ConvertTo-Json -Depth 6
