# 📊 Nagarro AgentiMigrate Platform - Logging Guide

## **🎯 Overview**

The platform implements comprehensive logging to help identify and fix issues quickly. All operations are logged with timestamps, levels, and component information.

## **📁 Log File Structure**

```
logs/
├── platform_master.log          # Master log with all entries
├── setup_YYYY-MM-DD_HH-mm-ss.log    # Setup session logs
├── platform_run_YYYY-MM-DD_HH-mm-ss.log  # Platform run logs
└── build_YYYY-MM-DD_HH-mm-ss.log    # Build session logs
```

## **📝 Log Entry Format**

```
[YYYY-MM-DD HH:mm:ss] [LEVEL] [COMPONENT] Message
```

**Example:**
```
[2025-01-24 14:30:15] [ERROR] [RUN-MVP] Docker not available through Rancher Desktop
[2025-01-24 14:30:20] [SUCCESS] [BUILD] All services built successfully
[2025-01-24 14:30:25] [INFO] [SETUP] Checking for Rancher Desktop installation...
```

## **🏷️ Log Levels**

| Level | Description | Color |
|-------|-------------|-------|
| **ERROR** | Critical issues that prevent operation | Red |
| **WARNING** | Issues that may cause problems | Yellow |
| **SUCCESS** | Successful operations | Green |
| **INFO** | General information | White |

## **🔧 Components**

| Component | Description |
|-----------|-------------|
| **SETUP** | Environment setup operations |
| **RUN-MVP** | Platform startup operations |
| **BUILD** | Docker build operations |
| **DOCKER** | Docker/container operations |
| **SERVICE** | Individual service operations |

## **📊 Log Analysis Tools**

### **Quick Analysis**
```powershell
# Analyze recent issues
.\analyze-logs.ps1

# Show only errors
.\analyze-logs.ps1 -ShowErrors

# Show only warnings
.\analyze-logs.ps1 -ShowWarnings

# Show all entries
.\analyze-logs.ps1 -ShowAll

# Show last 6 hours only
.\analyze-logs.ps1 -LastHours 6
```

### **Manual Log Review**
```powershell
# View master log
Get-Content logs\platform_master.log -Tail 50

# Search for errors
Select-String "ERROR" logs\platform_master.log

# Search for specific component
Select-String "RUN-MVP" logs\platform_master.log
```

## **🔍 Common Issues and Log Patterns**

### **Rancher Desktop Issues**
```
[ERROR] [SETUP] Rancher Desktop not found at expected path
[ERROR] [RUN-MVP] Docker not available through Rancher Desktop
```
**Solution:** Install/start Rancher Desktop, ensure 'dockerd (moby)' is selected

### **OpenAI API Key Issues**
```
[WARNING] [SETUP] OpenAI API key not configured in .env file
[ERROR] [SERVICE] OpenAI API authentication failed
```
**Solution:** Configure valid OpenAI API key in .env file

### **Docker Build Issues**
```
[ERROR] [BUILD] Build failed for service: backend
[ERROR] [BUILD] Docker daemon not responding
```
**Solution:** Check Rancher Desktop status, restart if needed

### **Service Startup Issues**
```
[ERROR] [RUN-MVP] Failed to start platform. Check logs with: docker compose logs
[WARNING] [SERVICE] Service not responding on expected port
```
**Solution:** Check individual service logs with `docker compose logs [service]`

## **📈 Log Monitoring Best Practices**

### **Regular Monitoring**
```powershell
# Daily health check
.\analyze-logs.ps1 -LastHours 24

# After platform startup
.\analyze-logs.ps1 -ShowErrors

# Before important operations
.\analyze-logs.ps1 -ShowWarnings
```

### **Troubleshooting Workflow**
1. **Check recent errors:** `.\analyze-logs.ps1 -ShowErrors`
2. **Review component activity:** Look at component breakdown
3. **Check Docker logs:** `docker compose logs [service]`
4. **Verify prerequisites:** Rancher Desktop, API keys, etc.
5. **Review full context:** `.\analyze-logs.ps1 -ShowAll -LastHours 2`

## **🛠️ Advanced Log Analysis**

### **PowerShell Log Analysis**
```powershell
# Count errors by component
$logs = Get-Content logs\platform_master.log
$errors = $logs | Select-String "ERROR"
$errors | ForEach-Object { ($_ -split '\[')[3] } | Group-Object | Sort-Object Count -Descending

# Find recent failures
$logs | Select-String "failed|error" -Context 2, 2 | Select-Object -Last 10

# Timeline of issues
$logs | Select-String "ERROR|WARNING" | ForEach-Object {
    if ($_ -match '\[(.*?)\].*?\[(.*?)\].*?\[(.*?)\] (.*)') {
        [PSCustomObject]@{
            Time = $matches[1]
            Level = $matches[2]
            Component = $matches[3]
            Message = $matches[4]
        }
    }
} | Sort-Object Time | Format-Table -AutoSize
```

### **Docker Container Logs**
```powershell
# View all service logs
docker compose logs

# View specific service logs
docker compose logs backend
docker compose logs frontend
docker compose logs project-service

# Follow logs in real-time
docker compose logs -f backend

# View last 100 lines
docker compose logs --tail=100 backend
```

## **🚨 Critical Error Patterns**

### **Platform Won't Start**
Look for these patterns:
```
[ERROR] [RUN-MVP] Rancher Desktop not found
[ERROR] [BUILD] Docker daemon not responding
[ERROR] [SERVICE] Port already in use
```

### **Services Failing**
Look for these patterns:
```
[ERROR] [SERVICE] Connection refused
[ERROR] [SERVICE] Authentication failed
[ERROR] [SERVICE] Database connection failed
```

### **Build Failures**
Look for these patterns:
```
[ERROR] [BUILD] Build failed for service
[ERROR] [BUILD] No space left on device
[ERROR] [BUILD] Network timeout
```

## **📋 Log Maintenance**

### **Log Rotation**
Logs are automatically rotated:
- **Docker logs:** Max 10MB per file, 3 files retained
- **Session logs:** New file per session
- **Master log:** Continuous, manual cleanup needed

### **Cleanup Commands**
```powershell
# Clean old session logs (keep last 10)
Get-ChildItem logs\setup_*.log | Sort-Object CreationTime -Descending | Select-Object -Skip 10 | Remove-Item
Get-ChildItem logs\platform_run_*.log | Sort-Object CreationTime -Descending | Select-Object -Skip 10 | Remove-Item
Get-ChildItem logs\build_*.log | Sort-Object CreationTime -Descending | Select-Object -Skip 10 | Remove-Item

# Archive master log if too large (>50MB)
if ((Get-Item logs\platform_master.log).Length -gt 50MB) {
    $timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
    Move-Item logs\platform_master.log "logs\platform_master_archive_$timestamp.log"
}
```

## **💡 Tips for Effective Logging**

1. **Check logs immediately after issues** - Fresh logs contain the most relevant information
2. **Use component filtering** - Focus on specific components when troubleshooting
3. **Look for patterns** - Recurring errors often indicate configuration issues
4. **Check timestamps** - Correlate log entries with user actions
5. **Review context** - Look at entries before and after errors for full picture

## **🆘 When to Share Logs**

Share logs when requesting support:
- **Recent errors:** `.\analyze-logs.ps1 -ShowErrors -LastHours 2`
- **Full context:** `.\analyze-logs.ps1 -ShowAll -LastHours 1`
- **Specific session:** Share the relevant session log file
- **Docker logs:** `docker compose logs > docker_logs.txt`

This comprehensive logging system ensures that any issues can be quickly identified and resolved! 🚀
