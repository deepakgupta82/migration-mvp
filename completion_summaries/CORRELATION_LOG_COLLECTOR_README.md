# Correlation Log Collector

This PowerShell script collects logs from all services based on a correlation ID and time range, making it easy to debug issues across the entire microservices platform.

## Usage

```powershell
.\collect_correlation_logs.ps1 -CorrelationId "your-correlation-id-here" [options]
```

## Parameters

- **`-CorrelationId`** (Required): The correlation ID to search for across all service logs
- **`-TimeRangeMinutes`** (Optional): Number of minutes to look back from now (default: 30)
- **`-OutputFile`** (Optional): Custom output filename (default: auto-generated with timestamp)

## Configuration

Edit the **CONFIGURATION SECTION** at the top of the script to customize which services to search:

```powershell
# Default services to search (modify this list as needed)
$servicesToSearch = @(
    "document-service",
    "vector-service",
    "graph-service",
    "llm-service"
    # Add more services here as needed, e.g.:
    # "storage-service",
    # "project-service",
    # "ai-agent-service"
)

# Also search backend logs (set to $false to exclude)
$includeBackendLogs = $true
```

## Examples

```powershell
# Basic usage - search last 30 minutes for correlation ID
.\collect_correlation_logs.ps1 -CorrelationId "5e00aa2d-4e65-45ed-8f99-b1103543803d"

# Search last 2 hours
.\collect_correlation_logs.ps1 -CorrelationId "5e00aa2d-4e65-45ed-8f99-b1103543803d" -TimeRangeMinutes 120

# Custom output file
.\collect_correlation_logs.ps1 -CorrelationId "5e00aa2d-4e65-45ed-8f99-b1103543803d" -OutputFile "debug_session_001.txt"
```

## What it does

1. **Scans configured log files** in:
   - Specified services' `logs/` directories
   - Backend `logs/` directory (if enabled)

2. **Supports multiple log formats**:
   - JSON format (newer services): `{"ts": "...", "corr_id": "..."}`
   - Legacy format: `[corr_id=UUID]`
   - Storage format: `[corr_id=UUID req_id=UUID]`

3. **Filters by**:
   - Correlation ID (exact match)
   - Time range (within specified minutes)

4. **Outputs** a text file with:
   - Service and file information
   - All matching log lines
   - Organized by service/file

## Output Format

The output file contains:
```
==================================================================================
SERVICE: llm-service/llm-service.log
FILE: C:\path\to\logs\llm-service.log
MATCHING LINES: 15
==================================================================================
2025-08-21T07:42:17.726568 INFO [llm-service] [corr_id=5e00aa2d-4e65-45ed-8f99-b1103543803d] Getting LLM for process: entity_extraction
... more lines ...
```

## Use with GitHub Copilot

After collecting the logs:

1. Open the generated `.txt` file
2. Copy the content
3. Paste into GitHub Copilot chat with a query like:
   - "Analyze these logs for errors related to correlation ID xyz"
   - "Help me understand what's happening in this request flow"
   - "Find performance issues in these service logs"

## Tips

- **Correlation IDs** are typically UUIDs generated for each request
- **Time range** defaults to 30 minutes - increase if needed
- **Large files** are handled efficiently (reads line by line)
- **Multiple services** - logs from all configured services are included if they contain the correlation ID
- **Easy configuration** - just edit the services list at the top of the script

## Finding Correlation IDs

You can find correlation IDs in:
- Service logs (search for `corr_id=`)
- Request headers (`X-Correlation-ID`)
- Application logs
- Error messages

## Troubleshooting

If no logs are found:
- Check the correlation ID is correct
- Try increasing the time range
- Verify the services are running and logging
- Check if the correlation ID format matches (some services use different formats)
- Verify the services you want are listed in the configuration section