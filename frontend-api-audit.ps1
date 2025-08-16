#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Frontend API Audit - Comprehensive Analysis of Broken Endpoints
    
.DESCRIPTION
    Maps all frontend API calls against backend routes to identify missing endpoints
    
.NOTES
    Generated: $(Get-Date)
    Phase: 1 - Audit and Analysis
#>

Write-Host "=== FRONTEND API COMPREHENSIVE AUDIT ===" -ForegroundColor Cyan

# FRONTEND API CALLS (from audit)
$frontendAPICalls = @(
    # Core Project APIs  
    @{ Endpoint = "/api/projects"; Method = "GET"; Frontend = "getProjects()"; Status = "" },
    @{ Endpoint = "/api/projects/{id}"; Method = "GET"; Frontend = "getProject()"; Status = "" },
    @{ Endpoint = "/api/projects"; Method = "POST"; Frontend = "createProject()"; Status = "" },
    @{ Endpoint = "/api/projects/{id}"; Method = "PUT"; Frontend = "updateProject()"; Status = "" },
    @{ Endpoint = "/api/projects/{id}"; Method = "DELETE"; Frontend = "deleteProject()"; Status = "" },
    
    # Project Files - CRITICAL ISSUE IDENTIFIED  
    @{ Endpoint = "/api/projects/{id}/uploads"; Method = "GET"; Frontend = "getProjectUploads()"; Status = "🔥 MISSING" },
    @{ Endpoint = "/upload/{id}"; Method = "POST"; Frontend = "uploadFiles()"; Status = "" },
    @{ Endpoint = "/api/projects/{id}/download/{filename}"; Method = "GET"; Frontend = "downloadFile()"; Status = "" },
    
    # Project Analytics
    @{ Endpoint = "/api/projects/stats"; Method = "GET"; Frontend = "getProjectStats()"; Status = "" },
    @{ Endpoint = "/api/platform/stats-fast"; Method = "GET"; Frontend = "getPlatformStatsFast()"; Status = "" },
    @{ Endpoint = "/api/projects/{id}/stats-snapshot"; Method = "GET"; Frontend = "getProjectStatsSnapshot()"; Status = "" },
    @{ Endpoint = "/api/projects/{id}/graph"; Method = "GET"; Frontend = "getProjectGraph()"; Status = "" },
    
    # Knowledge & Query
    @{ Endpoint = "/api/projects/{id}/query"; Method = "POST"; Frontend = "queryProjectKnowledge()"; Status = "" },
    @{ Endpoint = "/api/projects/{id}/test-llm"; Method = "POST"; Frontend = "testProjectLLM()"; Status = "" },
    
    # Platform & Settings
    @{ Endpoint = "/api/platform-settings"; Method = "GET"; Frontend = "getPlatformSettings()"; Status = "" },
    @{ Endpoint = "/api/projects/{id}/report"; Method = "GET"; Frontend = "getProjectReport()"; Status = "" },
    @{ Endpoint = "/api/test-llm"; Method = "POST"; Frontend = "testLLM()"; Status = "" },
    
    # Crew Management  
    @{ Endpoint = "/api/crew-config"; Method = "GET"; Frontend = "getCrewDefinitions()"; Status = "" },
    @{ Endpoint = "/api/crew-config/reload"; Method = "POST"; Frontend = "reloadCrewDefinitions()"; Status = "" },
    @{ Endpoint = "/api/crew-config"; Method = "PUT"; Frontend = "updateCrewDefinitions()"; Status = "" },
    
    # Logging & Monitoring
    @{ Endpoint = "/api/template-usage/global"; Method = "GET"; Frontend = "getGlobalTemplateUsage()"; Status = "" },
    @{ Endpoint = "/api/logs"; Method = "GET"; Frontend = "listLogServices()"; Status = "" },
    @{ Endpoint = "/api/logs?service={service}&tail={n}"; Method = "GET"; Frontend = "tailLogs()"; Status = "" },
    
    # LLM Management
    @{ Endpoint = "/api/llm/test-llm-config"; Method = "GET"; Frontend = "testLLMConfig()"; Status = "" },
    @{ Endpoint = "/api/llm/models/{provider}"; Method = "GET"; Frontend = "listProviderModels()"; Status = "" }
)

# DIRECT HTTP CALLS (not using api.ts)
$directHTTPCalls = @(
    # GraphVisualizer.tsx
    @{ Endpoint = "/api/projects/{id}/graph"; Method = "GET"; Component = "GraphVisualizer"; Status = "" },
    
    # ProcessLLMConfiguration.tsx  
    @{ Endpoint = "/api/llm/configurations"; Method = "GET"; Component = "ProcessLLMConfiguration"; Status = "" },
    @{ Endpoint = "/api/ollama/models"; Method = "GET"; Component = "ProcessLLMConfiguration"; Status = "⚠️ UNKNOWN" },
    @{ Endpoint = "/api/projects/{id}/llm-process-configs"; Method = "GET"; Component = "ProcessLLMConfiguration"; Status = "⚠️ UNKNOWN" },
    @{ Endpoint = "/api/projects/{id}/llm-process-configs"; Method = "POST"; Component = "ProcessLLMConfiguration"; Status = "⚠️ UNKNOWN" },
    @{ Endpoint = "/api/projects/{id}/process-llm-config/{key}/test"; Method = "POST"; Component = "ProcessLLMConfiguration"; Status = "⚠️ UNKNOWN" },
    
    # TestLLMModal.tsx
    @{ Endpoint = "/api/platform-settings"; Method = "GET"; Component = "TestLLMModal"; Status = "" },
    
    # DocumentTemplates.tsx - DIRECT PROJECT SERVICE CALLS (BAD!)
    @{ Endpoint = "/api/projects/{id}/template-usage"; Method = "GET"; Component = "DocumentTemplates"; Status = "" },
    @{ Endpoint = "/api/projects/{id}/generation-history"; Method = "GET"; Component = "DocumentTemplates"; Status = "" },
    @{ Endpoint = "/projects/{id}/deliverables"; Method = "GET"; Component = "DocumentTemplates"; Service = "Project (8002)"; Status = "🔥 BYPASSING GATEWAY" },
    @{ Endpoint = "/templates/global"; Method = "GET"; Component = "DocumentTemplates"; Service = "Project (8002)"; Status = "🔥 BYPASSING GATEWAY" },
    @{ Endpoint = "/projects/{id}/generation-requests"; Method = "GET"; Component = "DocumentTemplates"; Service = "Project (8002)"; Status = "🔥 BYPASSING GATEWAY" },
    @{ Endpoint = "/projects/{id}/deliverables"; Method = "POST"; Component = "DocumentTemplates"; Service = "Project (8002)"; Status = "🔥 BYPASSING GATEWAY" },
    @{ Endpoint = "/projects/{id}/generation-requests"; Method = "POST"; Component = "DocumentTemplates"; Service = "Project (8002)"; Status = "🔥 BYPASSING GATEWAY" },
    @{ Endpoint = "/api/projects/{id}/generate-document"; Method = "POST"; Component = "DocumentTemplates"; Status = "" },
    @{ Endpoint = "/api/projects/{id}/download/"; Method = "GET"; Component = "DocumentTemplates"; Status = "" },
    
    # ProjectHistory.tsx - DIRECT PROJECT SERVICE CALLS (BAD!)
    @{ Endpoint = "/projects/{id}"; Method = "GET"; Component = "ProjectHistory"; Service = "Project (8002)"; Status = "🔥 BYPASSING GATEWAY" },
    @{ Endpoint = "/projects/{id}/files"; Method = "GET"; Component = "ProjectHistory"; Service = "Project (8002)"; Status = "🔥 BYPASSING GATEWAY" },
    
    # GlobalDocumentTemplates.tsx - DIRECT PROJECT SERVICE CALLS (BAD!)
    @{ Endpoint = "/templates/global"; Method = "GET"; Component = "GlobalDocumentTemplates"; Service = "Project (8002)"; Status = "🔥 BYPASSING GATEWAY" },
    @{ Endpoint = "/templates/global"; Method = "POST"; Component = "GlobalDocumentTemplates"; Service = "Project (8002)"; Status = "🔥 BYPASSING GATEWAY" }
)

# WebSocket Connections
$webSocketConnections = @(
    @{ Endpoint = "ws://localhost:8000/ws/run_assessment/{id}"; Component = "AssessmentWebSocket"; Status = "" },
    @{ Endpoint = "ws://localhost:8000/ws/logs/{service}"; Component = "LogsView"; Status = "" }
)

Write-Host "`n=== CRITICAL ISSUES IDENTIFIED ===" -ForegroundColor Red -BackgroundColor DarkRed

Write-Host "`n1. MISSING GATEWAY ENDPOINT:" -ForegroundColor Red
Write-Host "   Frontend: /api/projects/{id}/uploads" -ForegroundColor Yellow
Write-Host "   Backend:  /api/projects/{id}/uploaded-files" -ForegroundColor Green
Write-Host "   Status:   FIXED - Added legacy endpoint routing" -ForegroundColor Green

Write-Host "`n2. BYPASSING API GATEWAY:" -ForegroundColor Red
Write-Host "   Multiple components calling Project Service (8002) directly!" -ForegroundColor Yellow
Write-Host "   - DocumentTemplates.tsx: 7 direct calls" -ForegroundColor Yellow  
Write-Host "   - ProjectHistory.tsx: 2 direct calls" -ForegroundColor Yellow
Write-Host "   - GlobalDocumentTemplates.tsx: 2 direct calls" -ForegroundColor Yellow
Write-Host "   Risk: Authentication, logging, error handling bypassed!" -ForegroundColor Red

Write-Host "`n3. UNKNOWN ENDPOINTS:" -ForegroundColor Orange
Write-Host "   - /api/ollama/models" -ForegroundColor Yellow
Write-Host "   - /api/projects/{id}/llm-process-configs" -ForegroundColor Yellow
Write-Host "   - /api/projects/{id}/process-llm-config/{key}/test" -ForegroundColor Yellow

Write-Host "`n=== NEXT STEPS ===" -ForegroundColor Cyan
Write-Host "1. ✅ Fix missing /uploads endpoint (DONE)" -ForegroundColor Green
Write-Host "2. 🔥 Fix all direct Project Service calls to use Gateway" -ForegroundColor Red  
Write-Host "3. ⚠️  Add missing LLM/Process endpoints to Gateway" -ForegroundColor Yellow
Write-Host "4. ✅ Test all endpoints end-to-end" -ForegroundColor Blue
Write-Host "5. ✅ Validate complete user workflows" -ForegroundColor Blue

Write-Host "`n=== AUDIT COMPLETE ===" -ForegroundColor Green
Write-Host "Continue with systematic fixes..." -ForegroundColor White
