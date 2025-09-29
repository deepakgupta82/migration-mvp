param(
  [Parameter(Mandatory=$true)][string]$ProjectId,
  [Parameter(Mandatory=$true)][string]$Filename,
  [string]$CorrelationId = $(New-Guid).Guid,
  [int]$GraphMaxRetries = 3,
  [int]$GraphBaseTimeoutSeconds = 120,
  [int]$GraphMaxTimeoutSeconds = 300,
  [int]$GraphTableContentMaxChars = 8000,
  [int]$GraphNarrativeCapChars = 28000,
  [int]$GraphSpreadsheetCapChars = 20000,
  [int]$TableGraphBatchChars = 12000,
  [int]$TableGraphMaxElements = 450,
  [switch]$FactsOnly = $false,
  [int]$FactsMaxElements = 8
)

$ErrorActionPreference = 'Stop'

# Service endpoints
$storageUrl = $env:STORAGE_SERVICE_URL; if (-not $storageUrl) { $storageUrl = 'http://localhost:8010' }
$graphUrl   = $env:GRAPH_SERVICE_URL;  if (-not $graphUrl)   { $graphUrl   = 'http://localhost:8006' }
$token = $env:SERVICE_AUTH_TOKEN; if (-not $token) { $token = 'service-backend-token' }

# Build structured JSONL name
$baseName = [System.IO.Path]::GetFileNameWithoutExtension($Filename)
$structuredName = "$baseName`_structured.jsonl"

Write-Host "Correlation ID: $CorrelationId"
Write-Host "Downloading structured JSONL: $structuredName"

$headers = @{ 'Authorization' = "Bearer $token"; 'X-Correlation-ID' = $CorrelationId }
$structuredUri = "$storageUrl/api/storage/projects/$ProjectId/download/structured/$structuredName"
try {
  $resp = Invoke-WebRequest -Uri $structuredUri -Headers $headers -Method Get -TimeoutSec 180
  if ($resp.StatusCode -ne 200) { throw "HTTP $($resp.StatusCode) downloading structured JSONL" }
  $jsonl = [System.Text.Encoding]::UTF8.GetString($resp.Content)
} catch {
  throw "Failed to download structured JSONL: $_"
}

# Parse JSONL into structured_elements expected by graph-service
$elements = @()
$jsonl -split "`n" | ForEach-Object {
  $line = $_.Trim()
  if (-not $line) { return }
  try {
    $obj = $line | ConvertFrom-Json -ErrorAction Stop
  } catch { return }
  if ($obj.type -ne 'element') { return }
  $data = $obj.data
  $text = "" + $data.text
  if ($null -eq $text -or $text.Trim().Length -le 5) { return }
  $etype = if ($data.type) { ($data.type.ToString()).ToLower() } else { 'unknown' }
  $elements += [pscustomobject]@{
    element_id     = $data.element_id
    content        = $text
    element_type   = $etype
    page_number    = $data.page_number
    hierarchy_level= $data.hierarchy_level
    metadata       = $data.metadata
  }
}

if ($elements.Count -eq 0) { throw "No suitable elements parsed from JSONL" }

# If only facts extraction is requested, call the dedicated endpoint once with a small subset
if ($FactsOnly) {
  Write-Host ("FactsOnly mode: posting first {0} elements to /structured/facts" -f [Math]::Min($FactsMaxElements, $elements.Count))
  $subset = $elements | Select-Object -First $FactsMaxElements
  $payload = @{ 
    document_id = ([Guid]::NewGuid().Guid)
    filename = $Filename
    structured_elements = $subset
    processing_type = 'structured_extraction'
    extract_entities = $false
    extract_relationships = $false
  } | ConvertTo-Json -Depth 10 -Compress
  try {
    $timeout = [Math]::Min([int]([Math]::Max($GraphBaseTimeoutSeconds, 60)), $GraphMaxTimeoutSeconds)
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $resp = Invoke-RestMethod -Uri "$graphUrl/api/graphs/projects/$ProjectId/structured/facts" -Method Post -Headers $headers -Body $payload -ContentType 'application/json' -TimeoutSec $timeout
    $sw.Stop()
    Write-Host ("Facts extraction done in {0:N1}s. Count={1} Stored={2}" -f $sw.Elapsed.TotalSeconds, ($resp.count -as [int]), ($resp.stored -as [bool]))
    $resp | ConvertTo-Json -Depth 5
    return
  } catch {
    throw "FactsOnly request failed: $_"
  }
}

# Trim table content and optionally cap total elements
$maxTableChars = $GraphTableContentMaxChars
$elements = $elements | ForEach-Object {
  $e = $_ | Select-Object *
  if ($e.element_type -eq 'table' -and $e.content.Length -gt $maxTableChars) {
    $meta = @{}
    if ($e.metadata -is [hashtable]) { $meta = $e.metadata } elseif ($e.metadata) { $meta = @{} }
    $meta['_trimmed_for_graph'] = $true
    $meta['_original_length'] = $e.content.Length
    $meta['_kept_chars'] = $maxTableChars
    $e.metadata = $meta
    $e.content = $e.content.Substring(0, $maxTableChars)
  }
  $e
}

# Decide batching
$docType = if ($Filename -match '\.(xlsx|xls|csv)$') { 'excel_table' } else { 'mixed' }
$cap = if ($docType -eq 'excel_table') { $GraphSpreadsheetCapChars } else { $GraphNarrativeCapChars }
$totalChars = (
  $elements |
    ForEach-Object {
      if ($null -ne $_.content) { [int]$_.content.Length } else { 0 }
    } |
    Measure-Object -Sum
).Sum
$needBatching = ($docType -eq 'excel_table') -or ($totalChars -gt $cap)

function Split-Batches([array]$items, [int]$maxChars, [int]$maxElems) {
  $batches = @()
  $buf = @(); $chars = 0
  foreach ($e in $items) {
    $c = if ($e.content) { $e.content.Length } else { 0 }
    if (($buf.Count -ge $maxElems) -or (($chars + $c) -gt $maxChars -and $buf.Count -gt 0)) {
      $batches += ,@($buf)
      $buf = @(); $chars = 0
    }
    $buf += $e; $chars += $c
  }
  if ($buf.Count -gt 0) { $batches += ,@($buf) }
  return ,$batches
}

$batches = if ($needBatching) { Split-Batches -items $elements -maxChars $TableGraphBatchChars -maxElems $TableGraphMaxElements } else { ,@($elements) }

Write-Host ("Prepared {0} batches (needBatching={1})" -f $batches.Count, $needBatching)

$totalEntities = 0; $totalRels = 0; $totalElems = 0; $totalTime = 0.0
$sharedDocId = [Guid]::NewGuid().Guid

for ($i=0; $i -lt $batches.Count; $i++) {
  $batch = $batches[$i]
  Write-Host ("Posting batch {0}/{1} with {2} elements" -f ($i+1), $batches.Count, $batch.Count)
  $attempt = 0
  $lastErr = $null
  while ($attempt -lt $GraphMaxRetries) {
    $timeout = [Math]::Min($GraphBaseTimeoutSeconds + ($attempt*30), $GraphMaxTimeoutSeconds)
    try {
      $payload = @{ 
        document_id = $sharedDocId
        filename = $Filename
        structured_elements = $batch
        processing_type = 'structured_extraction'
        extract_entities = $true
        extract_relationships = $true
      } | ConvertTo-Json -Depth 10 -Compress
      $sw = [System.Diagnostics.Stopwatch]::StartNew()
      $resp = Invoke-RestMethod -Uri "$graphUrl/api/graphs/projects/$ProjectId/process-structured" -Method Post -Headers $headers -Body $payload -ContentType 'application/json' -TimeoutSec $timeout
      $sw.Stop()
      $totalTime += $sw.Elapsed.TotalSeconds
      if ($resp.status -eq 'success') {
        $totalEntities += [int]($resp.entities_extracted)
        $totalRels += [int]($resp.relationships_found)
        $totalElems += [int]($resp.elements_analyzed)
        break
      } else {
        throw "Graph response status not success"
      }
    } catch {
      $lastErr = $_
      $attempt++
      if ($attempt -lt $GraphMaxRetries) {
        $delay = @(2,5,10)[$attempt-1]
        Write-Warning ("Attempt $attempt failed; retrying in $delay s... Error: $lastErr")
        Start-Sleep -Seconds $delay
      }
    }
  }
  if ($attempt -ge $GraphMaxRetries -and $lastErr) {
    throw "Batch $($i+1) failed after $GraphMaxRetries attempts: $lastErr"
  }
}

Write-Host "Done. Entities=$totalEntities Relationships=$totalRels Elements=$totalElems Time(s)=$([Math]::Round($totalTime,2))"