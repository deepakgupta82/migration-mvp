param(
  [string]$BaseUrl = "http://localhost:8000"
)

# Requires PowerShell 7+ for better JSON formatting; works on Windows PowerShell too
function Section($title) { Write-Host "`n=== $title ===" -ForegroundColor Cyan }
function Show-Error($msg) { Write-Host "ERROR: $msg" -ForegroundColor Red }
function Show-Ok($msg) { Write-Host $msg -ForegroundColor Green }

function Get-Json($uri) {
  try {
    return Invoke-RestMethod -Uri $uri -Method GET -TimeoutSec 30 -ErrorAction Stop
  } catch {
    Show-Error "Request failed: $uri"
    Write-Host $_
    return $null
  }
}

Section "1) Check backend health"
$health = Get-Json "$BaseUrl/health"
if ($health) { Show-Ok "Health: $($health.status)" } else { Show-Error "Health endpoint not reachable" }

Section "2) List available log services"
$svcResp = Get-Json "$BaseUrl/api/logs/services"
if ($svcResp -and $svcResp.services) {
  Show-Ok "Found $($svcResp.services.Count) services"
  $svcResp.services | ForEach-Object { Write-Host " - $_" }
} else {
  Show-Error "No services returned from /api/logs/services"
}

Section "3) Tail backend logs (last 50)"
$tailResp = Get-Json "$BaseUrl/api/logs?service=backend&tail=50"
if ($tailResp -and $tailResp.entries) {
  Show-Ok "Entries: $($tailResp.entries.Count)"
  $tailResp.entries | Select-Object -First 5 | ForEach-Object {
    $ts = if ($_.timestamp) { $_.timestamp } else { '-' }
    Write-Host "[$($_.level)] $ts backend - $($_.message)"
  }
} else {
  Show-Error "No entries returned for backend tail"
}

Section "4) Search by correlation id (cid=corr_123)"
$cidResp = Get-Json "$BaseUrl/api/logs/search?cid=corr_123&limit=50"
if ($cidResp -and $cidResp.entries) {
  Show-Ok "Matches: $($cidResp.entries.Count)"
  $cidResp.entries | Select-Object -First 5 | ForEach-Object {
    Write-Host "[$($_.service)] $($_.timestamp) $($_.level) - $($_.message)"
  }
} else {
  Show-Error "No matches for cid=corr_123"
}

Section "5) Search across services in last 1h (limit 30)"
$fromIso = (Get-Date).ToUniversalTime().AddHours(-1).ToString("o")
$allResp = Get-Json "$BaseUrl/api/logs/search?from=$([uri]::EscapeDataString($fromIso))&limit=30"
if ($allResp -and $allResp.entries) {
  Show-Ok "Entries in last hour: $($allResp.entries.Count)"
  $allResp.entries | Select-Object -First 5 | ForEach-Object {
    Write-Host "[$($_.service)] $($_.timestamp) $($_.level) - $($_.message)"
  }
} else {
  Show-Error "No entries found in last hour"
}

Section "6) Search specific services (backend,project-service) level>=INFO"
$svcList = "backend,project-service"
$svcResp2 = Get-Json "$BaseUrl/api/logs/search?services=$svcList&level=INFO&limit=50"
if ($svcResp2 -and $svcResp2.entries) {
  Show-Ok "Matches: $($svcResp2.entries.Count)"
  $svcResp2.entries | Select-Object -First 5 | ForEach-Object {
    Write-Host "[$($_.service)] $($_.timestamp) $($_.level) - $($_.message)"
  }
} else {
  Show-Error "No matches for services=$svcList"
}

Section "Summary"
$ok = 1
if (-not $svcResp -or -not $svcResp.services -or $svcResp.services.Count -eq 0) { $ok = 0 }
if (-not $tailResp -or -not $tailResp.entries -or $tailResp.entries.Count -eq 0) { $ok = 0 }
if (-not $cidResp -or -not $cidResp.entries -or $cidResp.entries.Count -eq 0) { $ok = 0 }
if ($ok -eq 1) { Show-Ok "HTTP logs API looks healthy." } else { Show-Error "HTTP logs API needs attention; check errors above." }
