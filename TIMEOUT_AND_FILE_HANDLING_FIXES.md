# Timeout and File Handling Improvements

**Date:** October 2, 2025  
**Branch:** `enhance_doc_processing`  
**Status:** ✅ Implemented

---

## 📋 **Overview**

This document describes comprehensive fixes implemented to address timeout issues and file locking problems identified in document processing workflows.

### **Problems Solved**

1. ❌ **Timeout Issues**: LLM calls can take up to 15 minutes, but services had 2-3 minute timeouts
2. ❌ **File Locking**: Windows file locks on Excel files during cleanup (WinError 32)
3. ❌ **Poor Debuggability**: Random temp filenames like `tmpc7qtvyfo.xlsx` hard to track
4. ❌ **Hardcoded Timeouts**: No flexibility to adjust timeouts without code changes

---

## 🔧 **Fixes Implemented**

### **1. Configurable Timeout Environment Variables**

Added comprehensive timeout configuration to `.env.example`:

```bash
# HTTP Client Timeouts
HTTP_CLIENT_CONNECT_TIMEOUT=30
HTTP_CLIENT_READ_TIMEOUT=1000         # 16+ minutes for long LLM calls
HTTP_CLIENT_WRITE_TIMEOUT=300
HTTP_CLIENT_POOL_TIMEOUT=10

# LLM Service Timeouts
LLM_REQUEST_TIMEOUT=900               # 15 minutes for LLM responses
LLM_EXTRACTION_TIMEOUT=1000           # 16+ minutes for entity extraction

# Graph Service Timeouts
GRAPH_BASE_TIMEOUT_SECONDS=1000       # Base timeout increased from 120s
GRAPH_LLM_CALL_TIMEOUT=1000           # Graph->LLM call timeout
GRAPH_BATCH_TIMEOUT=1200              # Batch processing timeout

# Document Service Timeouts
DOCUMENT_GRAPH_TIMEOUT=1200           # Document->Graph integration
DOCUMENT_VECTOR_TIMEOUT=600           # Document->Vector integration
DOCUMENT_PROCESSING_TIMEOUT=1800      # Overall document processing

# File Operation Timeouts
FILE_CLEANUP_RETRY_ATTEMPTS=5         # Max retry attempts for locked files
FILE_CLEANUP_RETRY_DELAY=2            # Initial delay between retries
FILE_CLEANUP_MAX_DELAY=10             # Max delay between retries
```

**Files Modified:**
- `.env.example`

---

### **2. Smart Temporary File Naming**

**Old Behavior:**
```python
with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
    tmp.write(content)
    temp_path = tmp.name  # Returns: tmpc7qtvyfo.xlsx ❌
```

**New Behavior:**
```python
from app.utils.file_utils import create_temp_file_with_actual_name

temp_path = create_temp_file_with_actual_name(
    original_filename="D4_Asset_list_systems_Unix_v22.xlsx",
    content=file_content,
    project_id=project_id,
    prefix="download_"
)
# Returns: download_D4_Asset_list_systems_Unix_v22_20251002_173045_abc123.xlsx ✅
```

**Benefits:**
- ✅ Easy to identify file in logs
- ✅ Timestamp prevents conflicts
- ✅ Project-specific temp directories
- ✅ Better compatibility with processing libraries
- ✅ Easier debugging and tracking

**Files Created:**
- `services/document-service/app/utils/file_utils.py`

**Files Modified:**
- `services/document-service/app/core/enhanced_processor.py`
- `services/document-service/app/routers/documents.py`

---

### **3. Retry Logic for File Cleanup**

Implemented exponential backoff retry mechanism to handle Windows file locks:

```python
from app.utils.file_utils import cleanup_temp_file_with_retry

# Automatically handles:
# - Windows file locks (PermissionError)
# - Exponential backoff (2s, 3s, 4.5s, 6.75s, 10s)
# - Up to 5 retry attempts by default
# - Configurable via environment variables

success = cleanup_temp_file_with_retry(temp_file_path)
```

**Why Files Get Locked:**
1. **Unstructured library** opens Excel files for parsing
2. **openpyxl/xlrd** may keep file handles open briefly
3. **Windows file locking** prevents deletion until handle released
4. **Cleanup happens too quickly** before libraries release handles

**Solution:**
- Wait and retry with increasing delays
- Log warnings on retry attempts
- Succeed when file eventually unlocks
- Fail gracefully after max attempts

**Files Modified:**
- `services/document-service/app/core/enhanced_processor.py` (batch processing cleanup)
- `services/document-service/app/routers/documents.py` (T1 endpoint cleanup)

---

### **4. Service Client Timeout Configuration**

Updated shared `ServiceClient` to use environment-based timeouts:

**Old Configuration:**
```python
self.timeout = httpx.Timeout(30.0, connect=5.0)  # ❌ Hardcoded 30s
```

**New Configuration:**
```python
connect_timeout = float(os.getenv("HTTP_CLIENT_CONNECT_TIMEOUT", "30"))
read_timeout = float(os.getenv("HTTP_CLIENT_READ_TIMEOUT", "1000"))     # ✅ 16+ mins
write_timeout = float(os.getenv("HTTP_CLIENT_WRITE_TIMEOUT", "300"))
pool_timeout = float(os.getenv("HTTP_CLIENT_POOL_TIMEOUT", "10"))

self.timeout = httpx.Timeout(
    timeout=read_timeout,
    connect=connect_timeout,
    read=read_timeout,
    write=write_timeout,
    pool=pool_timeout
)
```

**Impact:**
- All service-to-service calls now support long timeouts
- No code changes needed to adjust timeouts
- Logged at startup for verification

**Files Modified:**
- `services/shared/service_client.py`

---

### **5. Graph Service LLM Call Timeout**

Increased timeout for graph service calls to LLM service:

**Old Configuration:**
```python
self.http = httpx.AsyncClient(
    timeout=httpx.Timeout(900.0, connect=60.0, read=900.0, write=60.0),  # ❌ Hardcoded
    ...
)
```

**New Configuration:**
```python
llm_timeout = float(os.getenv("LLM_REQUEST_TIMEOUT", "900"))  # ✅ Configurable
connect_timeout = float(os.getenv("HTTP_CLIENT_CONNECT_TIMEOUT", "60"))
write_timeout = float(os.getenv("HTTP_CLIENT_WRITE_TIMEOUT", "60"))

self.http = httpx.AsyncClient(
    timeout=httpx.Timeout(
        timeout=llm_timeout,
        connect=connect_timeout,
        read=llm_timeout,
        write=write_timeout
    ),
    ...
)
logger.info(f"HTTP client configured with LLM timeout: {llm_timeout}s")
```

**Files Modified:**
- `services/graph-service/app/core/graph_processor.py`

---

### **6. Document Service Graph Integration Timeout**

Increased default timeouts for document service calls to graph service:

**Old Configuration:**
```python
base_timeout = float(os.getenv("GRAPH_BASE_TIMEOUT_SECONDS", "120"))    # ❌ 2 mins
max_timeout = float(os.getenv("GRAPH_MAX_TIMEOUT_SECONDS", "300"))      # ❌ 5 mins
```

**New Configuration:**
```python
base_timeout = float(os.getenv("GRAPH_BASE_TIMEOUT_SECONDS", "1000"))   # ✅ 16+ mins
max_timeout = float(os.getenv("GRAPH_MAX_TIMEOUT_SECONDS", "1200"))     # ✅ 20 mins
```

**Files Modified:**
- `services/document-service/app/core/enhanced_processor.py`

---

## 📊 **Timeout Configuration Summary**

| Service Call Path | Old Timeout | New Default | Max Timeout | Configurable Via |
|------------------|-------------|-------------|-------------|------------------|
| **Document → Graph** | 120s | 1000s | 1200s | `GRAPH_BASE_TIMEOUT_SECONDS` |
| **Graph → LLM** | 900s | 900s | 1000s | `LLM_REQUEST_TIMEOUT` |
| **ServiceClient Default** | 30s | 1000s | - | `HTTP_CLIENT_READ_TIMEOUT` |
| **LLM Processing** | N/A | 900s | - | `LLM_REQUEST_TIMEOUT` |

---

## 🔄 **Data Flow Verification**

### **Confirmed: Services Use JSONL, Not Temp Files**

After the initial processing, **all services use structured JSONL files**, not temporary Excel files:

1. **Document Service** downloads Excel → Creates temp file with actual name
2. **Unstructured processes** temp file → Generates elements
3. **Document Service** creates JSONL: `D4_Asset_list_systems_Unix_v22_structured.jsonl`
4. **JSONL uploaded** to storage service with actual filename
5. **Graph Service** downloads JSONL (not Excel) for entity extraction
6. **LLM Service** processes JSONL data (not Excel)
7. **Vector Service** uses JSONL data (not Excel)
8. **Temp Excel file** cleaned up with retry logic

**Key Insight:** The Excel file lock issue only affects the initial processing phase. Subsequent operations use the JSONL, which has proper filename and doesn't get locked.

---

## 🧪 **Testing Recommendations**

1. **Test Long LLM Calls:**
   ```bash
   # Process a large document that will trigger 10+ minute LLM calls
   # Verify no timeout errors occur
   ```

2. **Test File Cleanup:**
   ```bash
   # Process Excel file and check logs for cleanup retry messages
   # Verify temp files are eventually deleted
   ```

3. **Test Concurrent Processing:**
   ```bash
   # Process same file multiple times concurrently
   # Verify timestamp prevents file conflicts
   ```

4. **Verify Environment Variables:**
   ```bash
   # Check service logs at startup
   # Should see: "HTTP client configured with LLM timeout: 900s"
   ```

---

## 🎯 **Expected Outcomes**

### **Before Fixes:**
```
❌ Timeout calling graph service after 180s
❌ [WinError 32] The process cannot access the file tmpc7qtvyfo.xlsx
❌ Hard to debug which file caused issues
❌ Need code changes to adjust timeouts
```

### **After Fixes:**
```
✅ Graph service completes after 240s (no timeout)
✅ Temp file cleanup retries and succeeds on attempt 3
✅ Logs show: "Cleaned up download_report_20251002_173045_abc123.xlsx"
✅ Can adjust timeouts via .env without code changes
```

---

## 📝 **Configuration Example**

Add to your `.env` file:

```bash
# Timeout Configuration for Long-Running Operations
HTTP_CLIENT_CONNECT_TIMEOUT=30
HTTP_CLIENT_READ_TIMEOUT=1000
HTTP_CLIENT_WRITE_TIMEOUT=300
HTTP_CLIENT_POOL_TIMEOUT=10

LLM_REQUEST_TIMEOUT=900
GRAPH_BASE_TIMEOUT_SECONDS=1000
GRAPH_MAX_TIMEOUT_SECONDS=1200
DOCUMENT_GRAPH_TIMEOUT=1200

# File Cleanup Configuration
FILE_CLEANUP_RETRY_ATTEMPTS=5
FILE_CLEANUP_RETRY_DELAY=2
FILE_CLEANUP_MAX_DELAY=10
```

---

## 🔍 **Monitoring & Debugging**

### **Log Messages to Watch For:**

**Success Indicators:**
```
✅ "HTTP client configured with LLM timeout: 900s"
✅ "File downloaded to temporary location: download_report_20251002_173045.xlsx"
✅ "Cleaned up temp file: ..."
✅ "Graph service response: 200 (took 240.00s)"
```

**Retry Messages (Normal):**
```
⚠️ "File locked (attempt 2/5), retrying in 2s: ..."
⚠️ "Successfully cleaned up temp file on attempt 3: ..."
```

**Error Messages (Action Required):**
```
❌ "Failed to cleanup temp file after 5 attempts (file locked): ..."
❌ "Timeout calling graph service: ..."
```

---

## 📚 **Related Documentation**

- `.env.example` - Full configuration reference
- `services/document-service/app/utils/file_utils.py` - File utility functions
- Log correlation files for debugging specific runs

---

## ✅ **Verification Checklist**

- [x] Timeout environment variables added to `.env.example`
- [x] File utility module created with retry logic
- [x] Enhanced processor using new file utilities
- [x] Router endpoints using new file utilities
- [x] ServiceClient configured for long timeouts
- [x] Graph processor configured for long timeouts
- [x] Document-to-graph timeouts increased
- [x] All changes logged for debugging
- [ ] **TODO:** Run end-to-end test with large document
- [ ] **TODO:** Verify no timeout errors in production

---

## 🚀 **Deployment Notes**

1. **Update Environment Variables**: Copy new variables from `.env.example` to production `.env`
2. **Restart Services**: All services need restart to pick up new timeout configurations
3. **Monitor Logs**: Watch for timeout configuration messages at startup
4. **Test Incrementally**: Test one service at a time if possible

---

**Implementation Status:** ✅ **COMPLETE**  
**Next Steps:** Testing and validation in development environment
