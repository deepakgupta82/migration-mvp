# Test All MCP Servers Script
# This script tests each MCP server by triggering discovery

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "MCP SERVER DISCOVERY TEST" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$baseUrl = "http://localhost:8008/api/mcp"

# Get all servers
Write-Host "Fetching all MCP servers..." -ForegroundColor Yellow
$servers = Invoke-RestMethod -Uri "$baseUrl/servers" -Method Get

Write-Host "Found $($servers.Count) MCP servers`n" -ForegroundColor Green

# Test each server
$results = @()

foreach ($server in $servers) {
    Write-Host "----------------------------------------" -ForegroundColor Gray
    Write-Host "Testing: $($server.name)" -ForegroundColor White
    Write-Host "  ID: $($server.id)" -ForegroundColor Gray
    Write-Host "  Provider: $($server.provider)" -ForegroundColor Gray
    Write-Host "  Transport: $($server.connection.transport)" -ForegroundColor Gray
    Write-Host "  Command: $($server.connection.stdio.command) $($server.connection.stdio.args -join ' ')" -ForegroundColor Gray
    Write-Host "  Enabled: $($server.is_enabled)" -ForegroundColor $(if ($server.is_enabled) { "Green" } else { "Red" })
    Write-Host "  Health: $($server.health_status)" -ForegroundColor Gray
    
    # Try discovery
    Write-Host "`n  Running discovery..." -ForegroundColor Yellow
    
    try {
        $tools = Invoke-RestMethod -Uri "$baseUrl/servers/$($server.id)/discover" -Method Post
        
        $result = [PSCustomObject]@{
            Name = $server.name
            ID = $server.id
            Provider = $server.provider
            Command = "$($server.connection.stdio.command) $($server.connection.stdio.args -join ' ')"
            Enabled = $server.is_enabled
            HealthStatus = $server.health_status
            ToolsDiscovered = $tools.Count
            Status = "✅ SUCCESS"
            Tools = ($tools | Select-Object -First 5 -ExpandProperty name) -join ", "
            Error = ""
        }
        
        Write-Host "  ✅ SUCCESS: Discovered $($tools.Count) tools" -ForegroundColor Green
        
        if ($tools.Count -gt 0) {
            Write-Host "`n  Tools found:" -ForegroundColor Cyan
            $tools | Select-Object -First 5 | ForEach-Object {
                Write-Host "    • $($_.name)" -ForegroundColor White
            }
            if ($tools.Count -gt 5) {
                Write-Host "    ... and $($tools.Count - 5) more" -ForegroundColor Gray
            }
        } else {
            Write-Host "  ⚠️  No tools discovered (server may be disabled or not responding)" -ForegroundColor Yellow
        }
        
    } catch {
        $errorMsg = $_.Exception.Message
        
        $result = [PSCustomObject]@{
            Name = $server.name
            ID = $server.id
            Provider = $server.provider
            Command = "$($server.connection.stdio.command) $($server.connection.stdio.args -join ' ')"
            Enabled = $server.is_enabled
            HealthStatus = $server.health_status
            ToolsDiscovered = 0
            Status = "❌ FAILED"
            Tools = ""
            Error = $errorMsg
        }
        
        Write-Host "  ❌ FAILED: $errorMsg" -ForegroundColor Red
    }
    
    $results += $result
    Write-Host ""
}

# Summary table
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "SUMMARY" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$results | Format-Table -Property Name, Enabled, ToolsDiscovered, Status -AutoSize

Write-Host "`nDetailed Results:" -ForegroundColor Yellow
$results | Format-List

# Statistics
$totalServers = $results.Count
$successfulServers = ($results | Where-Object { $_.Status -eq "✅ SUCCESS" -and $_.ToolsDiscovered -gt 0 }).Count
$failedServers = ($results | Where-Object { $_.Status -eq "❌ FAILED" }).Count
$disabledServers = ($results | Where-Object { $_.Enabled -eq $false }).Count
$totalTools = ($results | Measure-Object -Property ToolsDiscovered -Sum).Sum

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "STATISTICS" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Total Servers:       $totalServers" -ForegroundColor White
Write-Host "Successful:          $successfulServers" -ForegroundColor Green
Write-Host "Failed:              $failedServers" -ForegroundColor Red
Write-Host "Disabled:            $disabledServers" -ForegroundColor Yellow
Write-Host "Total Tools Found:   $totalTools" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Export results
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outputFile = "mcp_test_results_$timestamp.json"
$results | ConvertTo-Json -Depth 10 | Out-File $outputFile
Write-Host "Results exported to: $outputFile" -ForegroundColor Green
