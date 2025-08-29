param(
  [string]$ApiBase = 'http://localhost:8000',
  [string]$Token   = 'service-backend-token'
)

$ErrorActionPreference = 'Stop'
$headers = @{
  'Authorization' = "Bearer $Token"
  'Content-Type'  = 'application/json'
}

$projects = Invoke-RestMethod -Headers $headers -Method GET -Uri ("{0}/api/projects" -f $ApiBase.TrimEnd('/'))
if ($projects.PSObject.Properties.Name -contains 'data') { $projects = $projects.data }

# Emit as JSON for easy consumption (id, name)
if ($projects -is [System.Array]) {
  $projects | Select-Object id, name | ConvertTo-Json -Depth 5
} else {
  @($projects | Select-Object id, name) | ConvertTo-Json -Depth 5
}
