# 📊 Nagarro AgentiMigrate Platform - Logging Guide

## **🎯 Overview**

The platform implements comprehensive logging to help identify and fix issues quickly. All operations are logged with timestamps, levels, and component information.

## Log File Structure

```
logs/
├── platform_master.log           # Master platform log (also see platform.log)
├── platform.log                  # Backend platform log
├── agents.log                    # Agents/crews/tools interactions
├── database.log                  # Database SQL and app-level DB ops
├── project-service.log           # Project service log
├── reporting-service.log         # Reporting service log
├── neo4j.log                     # Neo4j container/service log (persisted)
├── postgresql.log                # PostgreSQL container/service log (persisted)
├── minio.log                     # MinIO container/service log (persisted)
└── megaparse-service.log         # MegaParse service log (persisted)
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

## Viewing Logs

- Tail backend logs (Windows):
  PowerShell: Get-Content logs\platform_master.log -Tail 100
- Tail service logs (examples):
  - Get-Content logs\project-service.log -Tail 100
  - Get-Content logs\reporting-service.log -Tail 100
  - Get-Content logs\neo4j.log -Tail 100
  - Get-Content logs\megaparse-service.log -Tail 100

From the frontend, the Logs page fetches recent entries via the backend API:
- GET /api/logs?service=all&tail=200 returns recent entries across all services.
- GET /api/logs?service=project-service&tail=200 to view one service.

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

## 📈 Log Monitoring Best Practices

### Regular Monitoring
- Use the Logs UI (LogsView) to inspect recent entries across services.
- For quick CLI checks on Windows: Get-Content logs\platform_master.log -Tail 200
- Filter for errors in PowerShell: Select-String "ERROR|CRITICAL" logs\*.log

### Troubleshooting Workflow
1. Check recent errors: Select-String "ERROR|CRITICAL" logs\platform_master.log
2. Review specific service logs via GET /api/logs?service={name}&tail=200
3. Check Docker logs: docker compose logs [service] or docker compose logs -f backend
4. Verify prerequisites: Rancher Desktop, API keys, env vars
5. Review full context: open specific log files in your editor or use Select-String with -Context

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

### Docker Container Logs (optional)
- docker compose logs -f backend
- docker compose logs --tail=100 project-service

Note: The backend also persists container logs (neo4j/postgresql/minio/megaparse) into the logs/ directory for later review.

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
- Recent errors: attach logs/platform_master.log tail (e.g., last 200 lines)
- Full context: attach the relevant service logs from logs/ directory
- Specific session: include timestamps and the service-specific log files
- Docker logs: docker compose logs > docker_logs.txt

This comprehensive logging system ensures that any issues can be quickly identified and resolved! 🚀
