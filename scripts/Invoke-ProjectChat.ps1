param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectId,
    [Parameter(Mandatory=$true)]
    [string]$Question,
    [string]$ApiBase = 'http://localhost:8000',
    [string]$Token = 'service-backend-token'
)

$ErrorActionPreference = 'Stop'
$headers = @{
  'Authorization' = "Bearer $Token"
  'Content-Type'  = 'application/json'
}

$body = @{ question = $Question } | ConvertTo-Json
$url  = ('{0}/api/projects/{1}/chat' -f $ApiBase.TrimEnd('/'), $ProjectId)

try {
  $resp = Invoke-RestMethod -Headers $headers -Method POST -Uri $url -Body $body
  if ($null -eq $resp) {
    Write-Host 'null response'
    exit 1
  }
  $resp | ConvertTo-Json -Depth 6
} catch {
  Write-Error $_
  exit 1
}
