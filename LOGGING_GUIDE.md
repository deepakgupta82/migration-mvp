# 📊 Nagarro AgentiMigrate Platform - Logging Guide

## **🎯 Overview**

The platform implements comprehensive logging to help identify and fix issues quickly. All operations are logged with timestamps, levels, and component information.

## **⚙️ Logging Configuration**

The platform supports configurable logging levels across all services. You can set different log levels for global logging, file output, and console output.

### **Configuration Methods**

#### **1. Via Settings UI (Recommended)**
Navigate to **Settings → Environment Variables** in the frontend to configure logging levels:
- **LOG_LEVEL**: Global logging level (affects all handlers)
- **FILE_LOG_LEVEL**: Specific level for file logging
- **CONSOLE_LOG_LEVEL**: Specific level for console logging

Available levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

#### **2. Via config.local.json**
Add logging configuration to your `config.local.json` file:
```json
{
  "logging": {
    "global_level": "INFO",
    "file_level": "WARNING",
    "console_level": "DEBUG"
  }
}
```

#### **3. Via Environment Variables**
Set environment variables before starting services:
```bash
export LOG_LEVEL=DEBUG
export FILE_LOG_LEVEL=INFO
export CONSOLE_LOG_LEVEL=WARNING
```

### **Configuration Priority**
1. Environment variables (highest priority)
2. config.local.json settings
3. Default values (INFO level)

### **Service-Specific Overrides**
Individual services can have their own logging configurations by adding service-specific sections to config.local.json:
```json
{
  "logging": {
    "global_level": "INFO",
    "services": {
      "project-service": {
        "level": "DEBUG"
      },
      "llm-service": {
        "level": "WARNING"
      }
    }
  }
}
```

**Note:** Changes require service restart to take effect.

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

The platform uses JSON format for file logs (Loki-compatible) and human-readable format for console logs.

**File Log Format (JSON):**
```json
{
  "timestamp": "2025-01-24T14:30:15.123456",
  "level": "INFO",
  "service": "project-service",
  "correlation_id": "abc-123-def-456",
  "message": "User created new project",
  "extra": {
    "user_id": "user123",
    "project_id": "proj456"
  }
}
```

**Console Log Format:**
```
2025-01-24 14:30:15,123 [INFO] [project-service] [abc-123-def-456] User created new project
```

**Key Fields:**
- **timestamp**: ISO format with microseconds
- **level**: Standard Python logging level
- **service**: Service name (backend, project-service, llm-service, etc.)
- **correlation_id**: Request correlation ID for tracing
- **message**: Log message
- **extra**: Additional context data (optional)

## **🏷️ Log Levels**

| Level | Description | Use Case |
|-------|-------------|----------|
| **CRITICAL** | Critical errors that cause system failure | System crashes, unrecoverable errors |
| **ERROR** | Errors that prevent operation but don't crash system | Failed API calls, database connection issues |
| **WARNING** | Issues that may cause problems | Deprecated features, potential issues |
| **INFO** | General information about system operation | Service startup, successful operations |
| **DEBUG** | Detailed diagnostic information | Variable values, function calls, detailed traces |

**Default Configuration:**
- Global Level: INFO
- File Level: INFO
- Console Level: INFO

## **🔧 Services/Components**

| Service | Description | Log File |
|---------|-------------|----------|
| **backend** | Main API gateway and orchestration | `logs/backend.log` |
| **project-service** | Project management and data | `logs/project-service.log` |
| **reporting-service** | Report generation and analytics | `logs/reporting-service.log` |
| **document-service** | Document processing and parsing | `logs/document-service.log` |
| **vector-service** | Vector database operations | `logs/vector-service.log` |
| **graph-service** | Graph database operations | `logs/graph-service.log` |
| **llm-service** | Large language model operations | `logs/llm-service.log` |
| **ai-agent-service** | AI agent orchestration | `logs/ai-agent-service.log` |
| **storage-service** | File storage operations | `logs/storage-service.log` |
| **websocket-service** | Real-time communication | `logs/websocket-service.log` |
| **analytics-service** | Analytics and metrics | `logs/analytics-service.log` |
| **security-service** | Security and authentication | `logs/security-service.log` |
| **collaboration-service** | Collaboration features | `logs/collaboration-service.log` |
| **knowledge-service** | Knowledge base operations | `logs/knowledge-service.log` |
| **service-registry** | Service discovery | `logs/service-registry.log` |
| **cloud-tools-service** | Cloud integration tools | `logs/cloud-tools-service.log` |
| **stats-service** | Statistics and monitoring | `logs/stats-service.log` |

## Viewing Logs

### **Via Frontend UI**
Navigate to the **Logs** page in the frontend to view real-time logs across all services with filtering and search capabilities.

### **Via API Endpoints**
- `GET /api/logs?service=all&tail=200` - Recent entries across all services
- `GET /api/logs?service=project-service&tail=200` - Specific service logs
- `GET /api/logs?level=ERROR&tail=100` - Filter by log level

### **Via Command Line**
```powershell
# View specific service logs
Get-Content logs\project-service.log -Tail 100 -Wait

# Search for errors across all logs
Get-ChildItem logs\*.log | Select-String "ERROR" -Context 2

# Monitor logs in real-time
Get-Content logs\backend.log -Tail 50 -Wait
```

### **Via Settings Panel**
Configure logging levels through **Settings → Environment Variables**:
- Search for "LOG_LEVEL" to find all logging configuration options
- Edit values directly in the UI
- Changes require service restart to take effect

## **🔍 Common Issues and Log Patterns**

### **Service Connection Issues**
```
[ERROR] [project-service] Connection refused to database
[ERROR] [llm-service] Failed to connect to OpenAI API
```
**Solution:** Check service URLs and credentials in Settings → Environment Variables

### **Configuration Issues**
```
[WARNING] [backend] Invalid log level 'INVALID', using default INFO
[ERROR] [vector-service] Configuration not found for required setting
```
**Solution:** Verify configuration in config.local.json or environment variables

### **Database Connection Issues**
```
[ERROR] [project-service] Database connection failed
[ERROR] [graph-service] Neo4j connection timeout
```
**Solution:** Check database credentials and connectivity in Settings panel

### **API Authentication Issues**
```
[ERROR] [llm-service] OpenAI API authentication failed
[WARNING] [ai-agent-service] Service token expired
```
**Solution:** Update API keys and tokens in Settings → Environment Variables

### **Resource Issues**
```
[ERROR] [vector-service] ChromaDB operation timeout
[WARNING] [document-service] Memory usage high
```
**Solution:** Check resource allocation and service-specific configurations

### **Debugging Tips**
1. **Enable Debug Logging**: Set `LOG_LEVEL=DEBUG` in environment or config to see detailed traces
2. **Check Service-Specific Logs**: Use the Logs UI to filter by specific service
3. **Correlate Requests**: Use correlation IDs to trace requests across services
4. **Monitor Performance**: Look for timeout and memory warnings in logs

## 📈 Log Monitoring Best Practices

### Regular Monitoring
- Use the Logs UI (LogsView) to inspect recent entries across services.
- For quick CLI checks on Windows: Get-Content logs\platform_master.log -Tail 200
- Filter for errors in PowerShell: Select-String "ERROR|CRITICAL" logs\*.log

### Troubleshooting Workflow
1. **Check Settings UI**: Verify configuration in Settings → Environment Variables
2. **Review Service Logs**: Use Logs UI to filter by service and time range
3. **Enable Debug Mode**: Temporarily set `LOG_LEVEL=DEBUG` for detailed traces
4. **Check Correlations**: Use correlation IDs to trace requests across services
5. **Verify Dependencies**: Ensure all required services and external APIs are accessible
6. **Review Configuration**: Check config.local.json for any misconfigurations

### **Configuration Troubleshooting**
- **Logs not appearing**: Check if service is running and LOG_LEVEL is set appropriately
- **Too many logs**: Increase FILE_LOG_LEVEL and CONSOLE_LOG_LEVEL to WARNING or ERROR
- **Missing debug info**: Set LOG_LEVEL=DEBUG for detailed diagnostic information
- **Service-specific issues**: Use service-specific log level overrides in config.local.json

## **🛠️ Advanced Log Analysis**

## **🛠️ Advanced Log Analysis**

### **PowerShell Log Analysis for JSON Logs**
```powershell
# Parse JSON logs and analyze by service
$logs = Get-Content logs\*.log | ConvertFrom-Json
$logs | Group-Object service | Sort-Object Count -Descending

# Find errors by service
$logs | Where-Object { $_.level -eq "ERROR" } | Group-Object service

# Analyze correlation IDs for request tracing
$logs | Where-Object { $_.correlation_id -eq "abc-123-def-456" } | Sort-Object timestamp

# Performance analysis - find slow operations
$logs | Where-Object { $_.message -match "took|duration|latency" } | Select-Object timestamp, service, message
```

### **Cross-Service Request Tracing**
```powershell
# Trace a request across all services using correlation ID
$correlationId = "abc-123-def-456"
Get-ChildItem logs\*.log | Select-String $correlationId -Context 2
```

### **Log Level Analysis**
```powershell
# Count log levels across all services
$logs = Get-Content logs\*.log | ConvertFrom-Json
$logs | Group-Object level | Sort-Object Count -Descending

# Find services with most warnings/errors
$logs | Where-Object { $_.level -in @("ERROR", "WARNING") } | Group-Object service | Sort-Object Count -Descending
```

### **Time-Based Analysis**
```powershell
# Logs from last hour
$oneHourAgo = (Get-Date).AddHours(-1)
$logs | Where-Object { [DateTime]::Parse($_.timestamp) -gt $oneHourAgo }

# Error spike detection
$logs | Where-Object { $_.level -eq "ERROR" } | Group-Object { [DateTime]::Parse($_.timestamp).Hour } | Sort-Object Name
```

### Docker Container Logs (optional)
- docker compose logs -f backend
- docker compose logs --tail=100 project-service

Note: The backend also persists container logs (neo4j/postgresql/minio/megaparse) into the logs/ directory for later review.

## **🚨 Critical Error Patterns**

## **🚨 Critical Error Patterns**

### **Service Startup Failures**
Look for these patterns:
```
[ERROR] [backend] Failed to bind to port 8000
[ERROR] [project-service] Database connection failed
[ERROR] [llm-service] API key not configured
```

### **Inter-Service Communication Issues**
Look for these patterns:
```
[ERROR] [ai-agent-service] Connection refused to llm-service:8007
[ERROR] [document-service] Timeout connecting to vector-service
[WARNING] [backend] Service health check failed
```

### **Configuration Errors**
Look for these patterns:
```
[ERROR] [backend] Invalid configuration for logging.global_level
[WARNING] [vector-service] Using default configuration
[ERROR] [graph-service] Required environment variable missing
```

### **Resource Exhaustion**
Look for these patterns:
```
[ERROR] [vector-service] ChromaDB operation timeout
[WARNING] [document-service] Memory usage critical
[ERROR] [llm-service] Rate limit exceeded
```

### **Authentication/Authorization Issues**
Look for these patterns:
```
[ERROR] [security-service] JWT token expired
[ERROR] [backend] Service authentication failed
[WARNING] [ai-agent-service] Insufficient permissions
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

1. **Use Appropriate Log Levels**: Set production levels to INFO/WARNING, use DEBUG only for troubleshooting
2. **Leverage Correlation IDs**: Use correlation IDs to trace requests across microservices
3. **Configure Per Environment**: Use DEBUG in development, INFO/WARNING in production
4. **Monitor Service Health**: Check logs for inter-service communication issues
5. **Use Settings UI**: Configure logging levels through the web interface for easy management
6. **Check Structured Data**: Use the `extra` field in logs for searchable metadata
7. **Set Up Alerts**: Monitor for ERROR/CRITICAL levels in production environments
8. **Archive Old Logs**: Regularly clean up old log files to manage disk space

## **🔧 Configuration Examples**

### **Development Environment**
```json
{
  "logging": {
    "global_level": "DEBUG",
    "file_level": "INFO",
    "console_level": "DEBUG"
  }
}
```

### **Production Environment**
```json
{
  "logging": {
    "global_level": "WARNING",
    "file_level": "INFO",
    "console_level": "ERROR",
    "services": {
      "security-service": {
        "level": "INFO"
      }
    }
  }
}
```

### **Troubleshooting Mode**
```json
{
  "logging": {
    "global_level": "DEBUG",
    "file_level": "DEBUG",
    "console_level": "DEBUG"
  }
}
```

## **🆘 When to Share Logs**

Share logs when requesting support:
- Recent errors: attach logs/platform_master.log tail (e.g., last 200 lines)
- Full context: attach the relevant service logs from logs/ directory
- Specific session: include timestamps and the service-specific log files
- Docker logs: docker compose logs > docker_logs.txt

This comprehensive logging system ensures that any issues can be quickly identified and resolved! 🚀
