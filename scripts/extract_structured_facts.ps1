Param(
    [Parameter(Mandatory = $true)] [string] $ProjectId,
    [Parameter(Mandatory = $true)] [string] $StructuredFile
)

$ErrorActionPreference = 'Stop'

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg) { Write-Host "[ERROR] $msg" -ForegroundColor Red }

# Service endpoints
$storageUrl = $env:STORAGE_SERVICE_URL
if ([string]::IsNullOrWhiteSpace($storageUrl)) { $storageUrl = 'http://localhost:8010' }
$graphUrl = $env:GRAPH_SERVICE_URL
if ([string]::IsNullOrWhiteSpace($graphUrl)) { $graphUrl = 'http://localhost:8006' }

# Auth header
$token = $env:SERVICE_AUTH_TOKEN
if ([string]::IsNullOrWhiteSpace($token)) { $token = 'service-backend-token' }
$headers = @{ Authorization = "Bearer $token" }

$downloadUrl = "$storageUrl/api/storage/projects/$ProjectId/download/structured/$StructuredFile"
Write-Info "Downloading structured JSONL from $downloadUrl"

try {
    $resp = Invoke-WebRequest -Uri $downloadUrl -Headers $headers -Method Get -UseBasicParsing
    $jsonl = $resp.Content
} catch {
    Write-Err "Failed to download structured JSONL: $($_.Exception.Message)"; exit 1
}

if ([string]::IsNullOrWhiteSpace($jsonl)) { Write-Err "Structured JSONL is empty"; exit 1 }

# Parse JSONL lines and normalize into StructuredDocumentElement objects
$lines = $jsonl -split "`n"
$elements = New-Object System.Collections.ArrayList
$maxElements = 350
$lineNo = 0

function Get-TableCsvFromMetadata($md) {
    try {
        if ($null -eq $md) { return $null }
        $td = $null
        if ($md.ContainsKey('table_data')) { $td = $md['table_data'] }
        elseif ($md.ContainsKey('table')) { $td = $md['table'] }
        $columns = $null; $rows = $null
        if ($td -ne $null -and $td -is [hashtable]) {
            if ($td.ContainsKey('columns')) { $columns = $td['columns'] }
            if ($td.ContainsKey('rows')) { $rows = $td['rows'] }
        }
        if (($columns -eq $null -or $rows -eq $null) -and ($md -is [hashtable])) {
            if ($md.ContainsKey('columns')) { $columns = $md['columns'] }
            if ($md.ContainsKey('rows')) { $rows = $md['rows'] }
        }
        if ($columns -eq $null -or $rows -eq $null) { return $null }
        # Flatten values
        function _flat($v) {
            if ($null -eq $v) { return '' }
            if ($v -is [string]) { return $v }
            if ($v -is [System.Collections.IEnumerable] -and -not ($v -is [string])) { return ($v | ForEach-Object { "$_" }) -join ' ' }
            if ($v -is [hashtable]) { return ($v.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join ',' }
            return "$v"
        }
        $header = ($columns | ForEach-Object { _flat $_ }) -join ','
        $rowLines = @()
        foreach ($r in $rows) {
            if ($r -is [System.Collections.IEnumerable] -and -not ($r -is [string])) {
                $rowLines += (($r | ForEach-Object { _flat $_ }) -join ',')
            } else {
                $rowLines += (_flat $r)
            }
        }
        if ([string]::IsNullOrWhiteSpace($header) -or $rowLines.Count -eq 0) { return $null }
        return ($header + "`n" + ($rowLines -join "`n"))
    } catch { return $null }
}

foreach ($line in $lines) {
    if ($elements.Count -ge $maxElements) { break }
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    $lineNo += 1
    $obj = $null
    try { $obj = $line | ConvertFrom-Json -ErrorAction Stop } catch { continue }

    # Determine content priority: text -> content -> table metadata CSV -> stringified object
    $content = $null
    if ($obj.PSObject.Properties.Match('text').Count -gt 0 -and -not [string]::IsNullOrWhiteSpace($obj.text)) { $content = [string]$obj.text }
    elseif ($obj.PSObject.Properties.Match('content').Count -gt 0 -and -not [string]::IsNullOrWhiteSpace($obj.content)) { $content = [string]$obj.content }
    if ([string]::IsNullOrWhiteSpace($content)) {
        $md = $null
        if ($obj.PSObject.Properties.Match('metadata').Count -gt 0 -and $obj.metadata -ne $null) { $md = $obj.metadata | ConvertTo-Json -Depth 10 | ConvertFrom-Json }
        $csvFromMd = Get-TableCsvFromMetadata $md
        if (-not [string]::IsNullOrWhiteSpace($csvFromMd)) { $content = $csvFromMd }
    }
    if ([string]::IsNullOrWhiteSpace($content)) { $content = ($line.Trim()) }

    $etype = 'text'
    if ($obj.PSObject.Properties.Match('type').Count -gt 0 -and -not [string]::IsNullOrWhiteSpace($obj.type)) { $etype = [string]$obj.type }
    elseif ($obj.PSObject.Properties.Match('element_type').Count -gt 0 -and -not [string]::IsNullOrWhiteSpace($obj.element_type)) { $etype = [string]$obj.element_type }

    $eid = $null
    foreach ($k in @('element_id','id','elementId','uid')) { if ($eid -eq $null -and $obj.PSObject.Properties.Match($k).Count -gt 0) { $eid = [string]$obj.$k } }
    if ([string]::IsNullOrWhiteSpace($eid)) { $eid = "line-$lineNo" }

    $page = $null
    foreach ($k in @('page_number','page')) { if ($page -eq $null -and $obj.PSObject.Properties.Match($k).Count -gt 0) { $page = [int]$obj.$k } }

    $level = $null
    foreach ($k in @('hierarchy_level','level','section_level')) { if ($level -eq $null -and $obj.PSObject.Properties.Match($k).Count -gt 0) { $level = [int]$obj.$k } }

    $metadata = $null
    if ($obj.PSObject.Properties.Match('metadata').Count -gt 0 -and $obj.metadata -ne $null) {
        # Ensure metadata is a hashtable-like structure
        $metadata = $obj.metadata | ConvertTo-Json -Depth 12 | ConvertFrom-Json
    }

    $element = [ordered]@{
        element_id = $eid
        content = $content
        element_type = $etype
        page_number = $page
        hierarchy_level = $level
        metadata = $metadata
    }
    [void]$elements.Add($element)
}

if ($elements.Count -eq 0) { Write-Warn "No structured elements parsed from JSONL"; exit 2 }

Write-Info "Parsed $($elements.Count) structured elements (cap=$maxElements). Posting to graph-service for fact extraction..."

$docId = [System.IO.Path]::GetFileNameWithoutExtension($StructuredFile)
$payload = [ordered]@{
    document_id = $docId
    filename = $StructuredFile
    structured_elements = $elements
    processing_type = 'structured_extraction'
    extract_entities = $false
    extract_relationships = $false
}

$jsonBody = $payload | ConvertTo-Json -Depth 20

$factsUrl = "$graphUrl/api/graphs/projects/$ProjectId/structured/facts"
$corrId = "cli-" + [Guid]::NewGuid().ToString('N')
$postHeaders = $headers.Clone()
$postHeaders["Content-Type"] = 'application/json'
$postHeaders["X-Correlation-ID"] = $corrId

try {
    $resp = Invoke-RestMethod -Uri $factsUrl -Method Post -Headers $postHeaders -Body $jsonBody
    Write-Host ("`n=== Structured Facts Extraction Result ===") -ForegroundColor Green
    $resp | ConvertTo-Json -Depth 6
} catch {
    Write-Err "Failed to extract/store facts: $($_.Exception.Message)"
    if ($_.ErrorDetails -and $_.ErrorDetails.Message) { Write-Err $_.ErrorDetails.Message }
    exit 3
}

# Fetch discoveries as validation
$discoveriesUrl = "$graphUrl/api/graphs/projects/$ProjectId/discoveries"
try {
    $dresp = Invoke-RestMethod -Uri $discoveriesUrl -Method Get -Headers $headers
    Write-Host ("`n=== Discoveries (Facts) ===") -ForegroundColor Green
    $dresp | ConvertTo-Json -Depth 6
} catch {
    Write-Warn "Could not retrieve discoveries: $($_.Exception.Message)"
}

Write-Info "Done"
