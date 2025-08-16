#!/usr/bin/env pwsh
<#!
.SYNOPSIS
  Start all microservices locally in separate integrated terminals
.DESCRIPTION
  Uses VS Code tasks to open each service in its own terminal tab
  Requires: Python env set up, npm installed, and infra (Postgres/Neo4j/MinIO/Redis) running
#>

param(
  [switch]$Frontend,
  [switch]$Gateway
)

Write-Host "Starting services via VS Code tasks..." -ForegroundColor Cyan

$workspace = Split-Path -Parent $MyInvocation.MyCommand.Path

# Helpful reminder about infra
Write-Host "Ensure Docker infra is up (postgres, neo4j, minio, redis) before running services." -ForegroundColor Yellow

# Kick off the compound task
try {
  code --reuse-window "$workspace" 2>$null | Out-Null
} catch {}

Write-Host "Triggering 'Start All Services' task..." -ForegroundColor Green

# NOTE: VS Code does not expose a CLI to run tasks directly; prompt the user
Write-Host "Open the Command Palette → 'Tasks: Run Task' → Select 'Start All Services'" -ForegroundColor Yellow

# Fallback: Print manual commands as optional reference
Write-Host "\nOptional manual starts (copy/paste into terminals):" -ForegroundColor Gray
Write-Host "- Backend:    cd backend; python -m app.main" -ForegroundColor Gray
Write-Host "- Project:    cd project-service; python .\\main.py" -ForegroundColor Gray
Write-Host "- Reporting:  cd reporting-service; python .\\main.py" -ForegroundColor Gray
Write-Host "- Document:   cd services\\document-service; python .\\main.py" -ForegroundColor Gray
Write-Host "- Vector:     cd services\\vector-service; python .\\main.py" -ForegroundColor Gray
Write-Host "- Graph:      cd services\\graph-service; python .\\main.py" -ForegroundColor Gray
Write-Host "- LLM:        cd services\\llm-service; python .\\main.py" -ForegroundColor Gray
Write-Host "- AI Agent:   cd services\\ai-agent-service; python .\\main.py" -ForegroundColor Gray
Write-Host "- WebSocket:  cd services\\websocket-service; python .\\main.py" -ForegroundColor Gray
Write-Host "- Storage:    cd services\\storage-service; python .\\main.py" -ForegroundColor Gray
Write-Host "- Frontend:   cd frontend; npm start" -ForegroundColor Gray
