# E2E: Document-service → project-service usage logging (Windows PowerShell)
# - Triggers process-selected for one file
# - Then queries project-service for agent-runs and agent-events filtered by correlation id

param(
  [string]$ProjectId = 'd1d78934-bc20-4f0d-b3bf-45d8497642e5',
  [string]$Filename = 'D4_Asset_list_systems_Unix_v22.xlsx'
)

$ErrorActionPreference = 'Stop'

# Generate correlation id
$CorrelationId = [guid]::NewGuid().Guid
Write-Host "CorrelationId: $CorrelationId"

# Trigger processing
$docUrl = 'http://localhost:8003/api/documents/{0}/process-selected' -f $ProjectId
$headers = @{ 'Authorization' = 'Bearer service-backend-token'; 'X-Correlation-ID' = $CorrelationId }
$body = @{ file_names = @($Filename); reprocess = $false } | ConvertTo-Json

Write-Host "POST $docUrl"
$resp = Invoke-RestMethod -Uri $docUrl -Method Post -Headers $headers -Body $body -ContentType 'application/json'
$jobId = $resp.job_id
Write-Host "Job started: $jobId"

Start-Sleep -Seconds 3

# Query usage: agent-runs by correlation id
$usageBase = 'http://localhost:8002/api/usage'
$agentRunsUrl = "$usageBase/agent-runs?correlation_id=$CorrelationId&limit=5"
Write-Host "GET $agentRunsUrl"
$agentRuns = Invoke-RestMethod -Uri $agentRunsUrl -Method Get -Headers @{ Authorization = 'Bearer service-backend-token' }
$agentRuns | ConvertTo-Json -Depth 5

# Query usage: agent-events by correlation id
$agentEventsUrl = "$usageBase/agent-events?correlation_id=$CorrelationId&limit=10"
Write-Host "GET $agentEventsUrl"
$agentEvents = Invoke-RestMethod -Uri $agentEventsUrl -Method Get -Headers @{ Authorization = 'Bearer service-backend-token' }
$agentEvents | ConvertTo-Json -Depth 6

# Optional: llm-calls (may be empty from doc-service)
$llmCallsUrl = "$usageBase/llm-calls?correlation_id=$CorrelationId&limit=5"
Write-Host "GET $llmCallsUrl"
$llmCalls = Invoke-RestMethod -Uri $llmCallsUrl -Method Get -Headers @{ Authorization = 'Bearer service-backend-token' }
$llmCalls | ConvertTo-Json -Depth 6
