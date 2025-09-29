param(
    [Parameter(Mandatory=$true)][string]$ProjectId,
    [string]$BaseUrl = 'http://localhost:8006/api/graphs',
    [string]$OutFile = ''
)

$ErrorActionPreference = 'Stop'

function Write-Section($title) {
    Write-Host "`n=== $title ==="
}

$projectBase = "$BaseUrl/projects/$ProjectId"
$graphUrl = "$projectBase/graph"

# Fetch full graph
$g = Invoke-RestMethod -Uri $graphUrl -Method Get

# Prepare optional file sink
if ($OutFile) {
    $outDir = Split-Path -Parent $OutFile
    if ($outDir -and -not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }
}

$sb = New-Object System.Text.StringBuilder

function Add-Line($text) {
    if ($OutFile) { $null = $sb.AppendLine($text) }
    Write-Host $text
}

Write-Section 'Node Types'
$nodeGroups = $g.nodes | Group-Object -Property type | Sort-Object -Property Count -Descending
foreach ($grp in $nodeGroups) {
    Add-Line ('{0,6} {1}' -f $grp.Count, $grp.Name)
}

Write-Section 'Relationship Types'
$relGroups = $g.relationships | Group-Object -Property type | Sort-Object -Property Count -Descending
foreach ($grp in $relGroups) {
    Add-Line ('{0,6} {1}' -f $grp.Count, $grp.Name)
}

Write-Section 'All Entities (id | name | type)'
foreach ($n in $g.nodes) {
    $nm = if ($n.name) { $n.name } else { '' }
    Add-Line ('{0} | {1} | {2}' -f $n.id, $nm, $n.type)
}

Write-Section 'All Connections (sourceName[type]) --TYPE--> (targetName[type])'
$byId = @{}
foreach ($n in $g.nodes) { $byId[$n.id] = $n }
foreach ($e in $g.relationships) {
    $s = $byId[$e.source_id]
    $t = $byId[$e.target_id]
    $sname = if($s -and $s.name){$s.name} else {$e.source_id}
    $tname = if($t -and $t.name){$t.name} else {$e.target_id}
    $stype = if($s){$s.type}else{''}
    $ttype = if($t){$t.type}else{''}
    Add-Line ('{0} [{1}] --{2}--> {3} [{4}]' -f $sname, $stype, $e.type, $tname, $ttype)
}

if ($OutFile) {
    $sb.ToString() | Out-File -FilePath $OutFile -Encoding UTF8
    Write-Host "`nSaved to: $OutFile"
}