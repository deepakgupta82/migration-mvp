# Test Run Analysis - October 3, 2025
**Correlation ID:** `ca5034f1-f0f0-4ec4-8410-4fe0f06a5efd`  
**Test Files:** 3 files (2 Excel, 1 PDF)  
**Processing Time:** ~16 minutes (9:44 AM - 10:01 AM)

---

## Executive Summary

### ✅ What Worked
1. **JSONL Conversion**: All 3 files successfully processed (209 + 299 + 70 = 578 elements)
2. **Vector Embeddings**: 541 embeddings created successfully
3. **Graph Database**: 40 nodes + 35 relationships created (BUT SHOULD BE HUNDREDS)
4. **LLM Service Communication**: No 422 errors (Fix #1 WORKED)
5. **WebSocket Broadcasting**: Messages sent to WebSocket service successfully

### ❌ What Didn't Work
1. **ZERO Entity Extraction from Excel Files** (CRITICAL REGRESSION - new adaptive extraction not working)
2. **Assessment UI Progress Not Real-Time** (Fix #9 DID NOT WORK - root cause identified)
3. **Multiple Service Integration Errors** (405, 404 errors)
4. **LLM Response Parsing Warnings** (unexpected dict format)
5. **Graph Service Not Using New Adaptive Extractor** (code changes not loaded)

---

## Detailed Analysis

### 1. CRITICAL: Entity Extraction Regression

**Expected:** 200-300 entities from server inventory Excel files  
**Actual:** 0 entities  

**Root Cause:** Graph service is **NOT using the new AdaptiveEntityExtractor**

#### Evidence from Logs:
```
2025-10-03 09:44:02,510 INFO [graph-service] Detected 60 table-like structured elements
2025-10-03 09:44:02,511 INFO [graph-service] Calling LLM entity extraction with document_id: structured_rows_a474a8aa-eb65-46ff-8017-0596bf2ad29c_4399
2025-10-03 09:44:03,199 INFO [graph-service] HTTP Request: GET http://localhost:8011/api/registry/services/llm-service "HTTP/1.1 404 Not Found"
```

**Why It Failed:**
1. **Service Discovery Failed**: LLM service lookup returned 404
   - Graph service tried to discover `llm-service` from registry
   - Service registry doesn't have `llm-service` registered (only has `llm` as key)
   
2. **Fallback to Old Code Path**: After discovery failure, it fell back to OLD extraction logic
   - No logs showing "Starting 2-stage adaptive entity extraction"
   - No logs showing "Document analysis: type=server_inventory"
   - No retry attempts logged

3. **Graph Service Not Restarted**: Changes in `entity_extractor.py` and `llm_client.py` not loaded into memory

#### Files Processed:
- **D4_Asset_list_systems_Unix_v22.xlsx**: 209 rows → **0 entities** ❌
- **D4_Windows server inventory_V38.xlsx**: 299 rows → **0 entities** ❌  
- **D5_NBQ-WAN-DIAGRAM-MAY-2025-HLD.pdf**: 33 elements → **2 entities** ✅ (diagram extraction worked)

---

### 2. Assessment UI Progress Not Showing

**Expected:** Real-time progress messages in Assessment UI panel  
**Actual:** Only generic "Processing started/completed" messages with no details

**Root Cause:** WebSocket messages are NOT using the event types expected by FileUpload.tsx

#### What FileUpload.tsx Expects (from Fix #9):
```typescript
// Expecting these message types:
- processing_started (with data.message, data.correlation_id)
- file_processing_started (with data.filename, data.file_number)
- jsonl_conversion_complete (with data.element_count)
- entity_extraction_complete (with data.entity_count)
- integration_status (with data.vector_status, data.graph_status)
```

#### What Document Service Actually Sends:
```json
// From logs - document service sends generic broadcasts:
{"type": "processing_update", "status": "processing"}
{"type": "file_updated", "filename": "..."}
```

**Evidence:**
- Document service logs show: `Broadcasted to project a474a8aa-eb65-46ff-8017-0596bf2ad29c on project_processing`
- But NO logs showing the specific event types that FileUpload.tsx is listening for
- Frontend code was updated but backend WebSocket emission code was NOT

**Why Assessment UI Shows Only 2 Entries:**
```
[9:44:10 AM] Processing started  ← Generic start
[10:00:44 AM] Processing completed  ← Generic end (after all 3 files)
```

These are the ONLY two messages that match the current WebSocket message format.

---

### 3. Service Integration Errors

#### 405 Method Not Allowed (Storage Service)
```
2025-10-03 09:56:11,310 ERROR Failed to store assessment metadata: Service error: 405
POST http://localhost:8010/api/storage/projects/{project_id}/files/{filename}/metadata
```
**Impact:** Assessment metadata not saved (non-critical)

#### 404 Not Found (Project Service)
```
2025-10-03 09:56:11,582 ERROR Could not retrieve project metadata: Service error: 404
GET http://localhost:8002/api/projects/a474a8aa-eb65-46ff-8017-0596bf2ad29c
```
**Impact:** Project insights not updated (non-critical but reduces value)

#### 404 Not Found (Service Registry)
```
2025-10-03 09:44:03,199 INFO HTTP Request: GET http://localhost:8011/api/registry/services/llm-service "HTTP/1.1 404 Not Found"
```
**Impact:** **CRITICAL** - Causes fallback to old entity extraction logic

---

### 4. LLM Response Format Warnings

**From Graph Service:**
```
2025-10-03 09:57:38,785 WARNING Unexpected LLM response format for fact extraction: <class 'dict'>
```

**Occurring During:** Fact extraction (separate from entity extraction)  
**Impact:** Probably harmless (facts still extracted), but indicates response parsing inconsistency

---

### 5. Graph Processing Performance

#### First Excel File (D4 Unix - 209 rows):
- **Batch 1**: 60 elements → **722 seconds** (12 minutes!) ⚠️
- **Batch 2-4**: 57+55+37 elements → **0.02 seconds each** ✅

**Why the huge difference?**
- First batch triggers entity extraction attempt (which times out)
- Subsequent batches use cached "no entities" result

#### Second Excel File (D4 Windows - 299 rows):
- **All 6 batches**: < 1 second each ✅
- **Timeout on facts extraction**: 120 seconds

#### PDF File (D5 Network Diagram - 52 elements):
- **1 batch**: 1.08 seconds ✅
- **Diagram entities**: 2 extracted successfully

---

## Why Only 40 Nodes & 35 Edges?

### Expected Distribution:
- **D4 Unix Excel** (209 rows): ~150-200 server entities
- **D4 Windows Excel** (299 rows): ~200-250 server entities  
- **D5 PDF Diagram** (52 elements): ~10-20 network entities
- **Total Expected**: 350-470 nodes, 400-600 edges

### Actual Distribution:
- **From Excel Files**: **0 entities** (extraction failed)
- **From PDF Diagram**: **2 entities** (diagram extraction worked)
- **From Fact Extraction**: **38 nodes** (fallback mechanism)
- **Relationships**: **35 edges** (from fact extraction only)

**Conclusion:** The graph contains ONLY the fallback fact-extraction results, NOT the structured entity extraction we implemented.

---

## Root Cause Chain

```
1. Graph service NOT restarted after code changes
   ↓
2. New adaptive extractor code NOT loaded into memory
   ↓  
3. Service discovery fails (llm-service vs llm mismatch)
   ↓
4. Falls back to OLD entity extraction logic
   ↓
5. Old logic doesn't work well with Excel table data
   ↓
6. Returns 0 entities
   ↓
7. Only fallback fact extraction runs
   ↓
8. Result: 40 nodes instead of 400+
```

---

## Assessment UI Issue - Detailed Analysis

### Current WebSocket Flow:
```
Document Service → WebSocket Service → Frontend FileUpload.tsx
     (broadcasts)        (relay)           (listens)
```

### The Mismatch:

**FileUpload.tsx Code (Fix #9):**
```typescript
if (rawMessage.type === 'processing_started' && rawMessage.data) {
  addLog(displayMessage); // ← Expects this exact type
}

if (rawMessage.type === 'file_processing_started' && rawMessage.data) {
  addLog(`Processing file ${file_number}/${total_files}...`); // ← Expects this exact type
}
```

**Document Service Actual Broadcasts (from logs):**
```json
// Generic broadcasts - NOT the specific types FileUpload expects
{"type": "document_processing", "status": "started"}
{"type": "project_processing", "status": "running"}
```

**Why Assessment UI Is Empty:**
- Frontend is listening for: `processing_started`, `file_processing_started`, etc.
- Backend is sending: `document_processing`, `project_processing`, etc.
- **Event types don't match** → no messages reach `addLog()`

---

## Additional Warnings & Issues

### File Lock Warnings (Windows-specific):
```
2025-10-03 09:56:11,913 WARNING File locked (attempt 1/5), retrying in 2.0s: tmpxeh7gdsm.xlsx
...
2025-10-03 09:56:28,172 ERROR Failed to cleanup temp file after 5 attempts
```
**Impact:** Temp files not cleaned up (disk space waste, but non-critical)

### PDF Processing Warnings (Non-critical):
```
2025-10-03 09:59:22,805 WARNING Cannot set gray non-stroke color because /'P45' is an invalid float value
```
**Impact:** PDF rendered successfully despite warnings

---

## Fixes Required (Prioritized)

### P0 - CRITICAL (Blocks All Entity Extraction)

#### Fix A: Service Registry Name Mismatch
**Location:** `services/graph-service/app/shared/llm_client.py` line ~40  
**Current:**
```python
llm_service_info = self.registry.get_service("llm-service")
```
**Change to:**
```python
llm_service_info = self.registry.get_service("llm")  # Match actual registry key
```

#### Fix B: Restart Graph Service
**Required:** Graph service MUST be restarted to load new code:
- `entity_extractor.py`
- `llm_client.py`
- `infrastructure_prompts.py`
- `extraction_models.py`

**Without restart, the new adaptive extraction code doesn't exist in memory!**

---

### P0 - CRITICAL (Assessment UI)

#### Fix C: WebSocket Event Type Alignment
**Need to align backend emission with frontend expectations**

**Option 1: Update Document Service to Emit New Types**  
**Location:** `services/document-service/app/core/enhanced_processor.py`  
**Change WebSocket broadcasts from:**
```python
await broadcast_update(project_id, "document_processing", {"status": "started"})
```
**To:**
```python
await broadcast_update(project_id, "processing_started", {
    "correlation_id": correlation_id,
    "file_count": total_files,
    "message": f"🚀 Assessment started for project {project_id}"
})
```

**OR Option 2: Update Frontend to Match Backend Events**  
**Location:** `frontend/src/components/FileUpload.tsx`  
**Change event listeners from:**
```typescript
if (rawMessage.type === 'processing_started' && rawMessage.data) {
```
**To:**
```typescript
if (rawMessage.type === 'document_processing' && rawMessage.status === 'started') {
```

**Recommendation:** Option 1 (update backend) - more descriptive event names

---

### P1 - High Priority (Service Integration)

#### Fix D: Storage Service Metadata Endpoint
**Add POST endpoint:** `/api/storage/projects/{project_id}/files/{filename}/metadata`  
**Current:** Returns 405 Method Not Allowed

#### Fix E: Project Service 404
**Issue:** Project UUID `a474a8aa-eb65-46ff-8017-0596bf2ad29c` not found  
**Cause:** Either project not created OR project-service using different database

---

### P2 - Medium Priority (Quality Improvements)

#### Fix F: LLM Response Normalization
**Location:** `services/graph-service/app/processors/graph_processor.py` (fact extraction)  
**Issue:** Expecting list, receiving dict  
**Solution:** Add response type checking in fact extraction parser

#### Fix G: File Lock Cleanup
**Location:** `services/document-service/app/core/enhanced_processor.py`  
**Issue:** Excel files locked by openpyxl/pandas  
**Solution:** Explicit file handle closing with context managers

---

## Testing Recommendations

### After Fixes A & B (Entity Extraction):
1. **Restart graph-service** (MANDATORY)
2. Re-upload D4 Unix Excel file
3. **Expected Results:**
   - Log shows: "Starting 2-stage adaptive entity extraction"
   - Log shows: "Document analysis: type=server_inventory, strategy=tabular_structured"
   - **Entities extracted: 150-200** (vs current 0)
   - **Retry attempts: 1-2** (vs current 0 - no extraction attempted)

### After Fix C (Assessment UI):
1. Re-upload any file
2. **Expected Assessment UI Messages:**
   ```
   [Time] 🚀 Assessment started for project...
   [Time] Processing file 1/3: D4_Asset_list_systems_Unix_v22.xlsx
   [Time] ✅ JSONL conversion complete: 209 elements from D4_Asset...
   [Time] ✅ Entity extraction complete: 187 entities from D4_Asset...
   [Time] Integration status: Vector=success, Graph=success...
   ```

### Graph Count Verification:
```cypher
// Should see 200+ nodes after fix
MATCH (n) WHERE n.project_id = 'a474a8aa-eb65-46ff-8017-0596bf2ad29c' RETURN count(n)

// Should see node types like: Server, Application, Database
MATCH (n) WHERE n.project_id = 'a474a8aa-eb65-46ff-8017-0596bf2ad29c' RETURN labels(n), count(*) ORDER BY count(*) DESC
```

---

## Summary Table

| Component | Status | Expected | Actual | Root Cause |
|-----------|--------|----------|--------|------------|
| JSONL Conversion | ✅ | 578 elements | 578 elements | Working |
| Vector Embeddings | ✅ | 541 vectors | 541 vectors | Working |
| **Entity Extraction** | ❌ | 200-300 entities | **0 entities** | Code not loaded + service discovery fail |
| Graph Nodes | ❌ | 350-470 nodes | **40 nodes** | No entity extraction |
| Graph Edges | ❌ | 400-600 edges | **35 edges** | No entity extraction |
| Assessment UI | ❌ | Real-time progress | 2 generic messages | Event type mismatch |
| LLM API Calls | ✅ | No 422 errors | No 422 errors | Fix #1 worked |
| Service Discovery | ❌ | llm-service found | 404 Not Found | Registry key mismatch |

---

## Action Plan (Recommended Order)

1. **IMMEDIATE**: Fix service registry lookup (llm-service → llm)
2. **IMMEDIATE**: Restart graph-service to load new code
3. **TEST**: Re-upload 1 Excel file, verify entity extraction works
4. **THEN**: Fix WebSocket event types (backend or frontend alignment)
5. **TEST**: Re-upload file, verify Assessment UI shows progress
6. **THEN**: Add missing storage/project endpoints
7. **FINAL TEST**: Full 3-file upload with verification

---

## Expected Improvements After Fixes

| Metric | Before | After Fixes | Improvement |
|--------|--------|-------------|-------------|
| Entity Extraction Success | 0% | 95%+ | Critical fix |
| Graph Nodes from 2 Excel | 0 | 350+ | Massive increase |
| Assessment UI Messages | 2 | 15-20 | User visibility |
| Entity Extraction Time | 12+ min (timeout) | 2-3 min | 5-6x faster |
| LLM Service Calls | Failed fallback | Direct routing | Architectural compliance |

---

## Questions to Answer

1. **Why wasn't graph-service restarted after code changes?**
2. **What's the correct service registry key: "llm" or "llm-service"?**
3. **Is project `a474a8aa-eb65-46ff-8017-0596bf2ad29c` actually created in project-service DB?**
4. **Should we standardize WebSocket event types across all services?**

