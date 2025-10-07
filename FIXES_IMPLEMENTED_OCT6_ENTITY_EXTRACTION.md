# Entity Extraction Fixes Implementation Summary
**Date**: October 6, 2025  
**Issue**: Excel entity extraction only getting 31/299 entities (10.4% success rate)  
**Root Cause**: Format mismatch - sending massive JSON blob to LLM instead of clean tabular text

---

## 🔍 Root Cause Analysis

### The Problem
When processing `D4_Windows server inventory_V38.xlsx`:
- **Expected**: ~284 server entities (299 rows - ~15 metadata rows)
- **Actual**: 31 entities extracted (10.4% success rate)
- **Batch 1**: 54 rows → **1 entity** (should be ~47 entities)

### Why It Failed
The graph-service was sending structured JSONL elements to the LLM as:
```python
document_content = json.dumps(elements_as_dicts)  # 154KB JSON blob
```

This created a massive, noisy JSON array like:
```json
[
  {"type": "element", "data": {"element_id": "6dbad7dc...", "type": "table_row", 
   "text": "...", "metadata": {"columns": [...], "row_data": {...}, 
   "column_types": {...semantic_indicators...}}}},
  ... 53 more similar objects ...
]
```

**Problems**:
1. 154KB of metadata noise (column_types, semantic_indicators, confidence scores)
2. No clear tabular structure - LLM sees JSON array, not rows
3. Metadata rows ("Last Update", "Version") look identical to data rows ("EIDASRV")
4. Prompt says "process each row" but content is JSON objects
5. LLM reasonably treated it as **one inventory document** → created **1 entity**

### What Was Actually Correct
- ✅ **Document-service JSONL output**: Excellent structure with rich metadata
- ✅ **LLM judgment**: Correctly interpreted ambiguous input as a single inventory/collection
- ✅ **Graph storage logic**: Properly stored the entities LLM returned

---

## 🛠️ Fixes Implemented

### **FIX #1: Transform JSONL to Clean Tabular Format** 🔴 CRITICAL
**File**: `services/graph-service/app/core/graph_processor.py`

**Added Function**: `_format_structured_elements_for_llm()`
- Converts 154KB JSON blob → ~20KB clean tabular text
- Extracts `row_data` dict from each element
- Formats as: `Row N: server_name=X, ip_address=Y, os=Z, ...`
- Groups by sheet name for multi-tab Excel files
- **Removes metadata noise** completely

**Before**:
```json
[{"type": "element", "data": {"element_id": "...", "metadata": {...}}}]
```

**After**:
```
Sheet: PR Servers
Rows: 47

Row 9: Prepaid by=EIDASRV, Windows system Team=10.1.134.25, col_3=Windows Server 2016 Standard, col_4=UAQ DC, ...
Row 10: Prepaid by=EPVMSRV, Windows system Team=10.1.121.53, col_3=Windows server 2016 Datacenter, ...
```

---

### **FIX #2: Add Metadata Row Filtering** 🟡 MEDIUM
**File**: Same function in `graph_processor.py`

**Logic Added**:
- Detects metadata patterns: `last update`, `version`, `classification`, `updated by`, `verified by`
- Detects header patterns: `server name`, `ip address`, `hostname`
- Skips rows matching these patterns before sending to LLM
- Logs skipped rows for debugging

**Result**: Only actual data rows sent to LLM (e.g., 47 server rows instead of 54 total rows)

---

### **FIX #3: Update SERVER_INVENTORY_PROMPT** 🟡 MEDIUM
**File**: `services/graph-service/app/prompts/infrastructure_prompts.py`

**Updated Prompt**:
- Explicitly describes new `Row N: key=value` format
- Maps column names to entity attributes (e.g., `server_name` → `attributes.hostname`)
- Includes validation instruction: "Count entities MUST match row count"
- Shows concrete example matching new format
- Removes ambiguous "process each row/line/entry" (which didn't work with JSON)

**Key Addition**:
```
VALIDATION CHECK:
Before returning, verify:
- Count of entities = Count of "Row N:" lines in input
- Each entity has type="server"
```

---

### **FIX #4: Add Enhanced Logging Throughout Pipeline** 🔵 ENHANCEMENT
**Files**: 
- `services/graph-service/app/core/graph_processor.py`
- `services/graph-service/app/core/entity_extractor.py`

**Logging Added**:

1. **graph_processor.py**:
   - Log correlation_id generation
   - Log sample raw element structure
   - Log formatted content preview (first 20 lines)
   - Log output statistics (rows, sheets, chars skipped)

2. **entity_extractor.py**:
   - Log content sample (first 500 chars)
   - Log prompt sample (first 800 chars)
   - Log LLM request details (content_length, prompt_length, timeout)
   - Log LLM response structure and sample entity
   - Log extraction rate calculation with warnings

**Example Enhanced Log Output**:
```
[corr-id] Formatted structured elements: 300 elements → 284 data rows across 7 sheets (skipped 16 metadata rows) | Output length: 18432 chars
[corr-id] Formatted content preview (first 20 lines): ...
[corr-id] Sending to LLM | content_length=18432 chars, prompt_length=3200 chars, timeout=120s
[corr-id] LLM response received: type=dict, keys=['entities', 'relationships']
[corr-id] Sample entity: id=server_eidasrv, type=server, name=EIDASRV
[corr-id] Extraction rate: 284/284 rows = 100.0%
```

---

### **FIX #5: Fix Batch Processing Detection Logic** 🔵 OPTIMIZATION
**File**: `services/graph-service/app/core/entity_extractor.py`

**Changed**:
```python
# OLD (BROKEN):
row_count = content.count('\n')  # Counts newlines in JSON string!

# NEW (CORRECT):
row_count = content.count('Row ') if 'Row ' in content else content.count('\n')
```

**Impact**: Now correctly detects tabular data and enables batch processing for large spreadsheets

---

### **FIX #6: Add Post-Extraction Validation** 🟢 MONITORING
**File**: `services/graph-service/app/core/entity_extractor.py`

**Logic Added**:
- After LLM returns entities, count expected rows (`Row ` markers)
- Calculate extraction rate: `entities / expected_rows`
- Log **WARNING** if rate < 80%
- Alert message explains the likely issue (grouping vs. row-by-row)

**Example Warning**:
```
[corr-id] ⚠️ LOW EXTRACTION RATE: Only 1/47 entities extracted (2.1%). 
Expected ~1 entity per row for tabular data. 
This suggests the LLM may be grouping rows instead of extracting individually.
```

---

## 📊 Expected Results After Fixes

### Before Fixes:
| Batch | Rows | Entities Extracted | Rate |
|-------|------|-------------------|------|
| 1 | 54 | 1 | 1.9% |
| 2 | 50 | 7 | 14.0% |
| 3 | 49 | 7 | 14.3% |
| 4 | 51 | 8 | 15.7% |
| 5 | 52 | 8 | 15.4% |
| 6 | 43 | timeout | - |
| **Total** | **299** | **31** | **10.4%** |

### After Fixes (Expected):
| Batch | Rows | Data Rows | Expected Entities | Rate |
|-------|------|-----------|------------------|------|
| 1 | 54 | ~47 | ~47 | ~100% |
| 2 | 50 | ~50 | ~50 | ~100% |
| 3 | 49 | ~49 | ~49 | ~100% |
| 4 | 51 | ~51 | ~51 | ~100% |
| 5 | 52 | ~52 | ~52 | ~100% |
| 6 | 43 | ~35 | ~35 | ~100% |
| **Total** | **299** | **~284** | **~284** | **~100%** |

---

## 🔄 Testing Instructions

### 1. Restart Graph Service
```powershell
# Stop current task
# Restart the graph service task to load new code
```

### 2. Reprocess the Same Document
```powershell
$headers = @{ 
    'X-Correlation-ID' = [guid]::NewGuid().Guid
    'Authorization' = 'Bearer service-backend-token' 
}
$body = @{ 
    extract_images = $true
    extract_tables = $true
    include_coordinates = $true 
} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8003/api/documents/a474a8aa-eb65-46ff-8017-0596bf2ad29c/structured-process/D4_Windows%20server%20inventory_V38.xlsx" -Method Post -Headers $headers -Body $body -ContentType 'application/json'
```

### 3. Collect New Correlation Logs
```powershell
.\collect_correlation_logs.ps1 -CorrelationId <new-correlation-id>
```

### 4. Analyze Results
Look for in the logs:
- ✅ "Formatted structured elements: X elements → Y data rows" (should show metadata filtering)
- ✅ "Formatted content preview" showing clean `Row N: key=value` format
- ✅ "Extraction rate: X/Y rows = Z%" (should be ~100%)
- ✅ No "LOW EXTRACTION RATE" warnings
- ✅ Entity count ≈ 284 entities

---

## 📝 Key Log Patterns to Search For

### Success Indicators:
```bash
# Format transformation
grep "Formatted structured elements" correlation_logs*.txt

# Metadata filtering
grep "skipped.*metadata rows" correlation_logs*.txt

# Clean format preview
grep "Formatted content preview" correlation_logs*.txt -A 20

# Extraction rate
grep "Extraction rate:" correlation_logs*.txt

# Final entity count
grep "Extraction complete: entities=" correlation_logs*.txt
```

### Failure Indicators:
```bash
# Low extraction warnings
grep "LOW EXTRACTION RATE" correlation_logs*.txt

# JSON blob format (should NOT appear anymore)
grep "json.dumps" correlation_logs*.txt  # Should be 0 results

# Batch processing detection issues
grep "Large spreadsheet detected" correlation_logs*.txt
```

---

## 🎯 Success Criteria

1. ✅ **Extraction Rate**: ≥ 95% (≥270 entities from 284 data rows)
2. ✅ **Clean Format**: Logs show `Row N: key=value` format, not JSON blobs
3. ✅ **Metadata Filtering**: Logs show ~15-20 metadata rows skipped
4. ✅ **No Warnings**: No "LOW EXTRACTION RATE" warnings
5. ✅ **Processing Time**: Same or faster (cleaner format = faster LLM)
6. ✅ **Graph Visualization**: 284+ server nodes in Neo4j graph view

---

## 🔧 Files Modified

1. **`services/graph-service/app/core/graph_processor.py`**
   - Added `_format_structured_elements_for_llm()` method
   - Added correlation_id generation
   - Added enhanced logging
   - Replaced `json.dumps()` with clean formatter

2. **`services/graph-service/app/core/entity_extractor.py`**
   - Fixed row count detection logic
   - Added content preview logging
   - Added prompt sample logging
   - Added LLM response logging
   - Added post-extraction validation
   - Added extraction rate warnings

3. **`services/graph-service/app/prompts/infrastructure_prompts.py`**
   - Completely rewrote `SERVER_INVENTORY_PROMPT`
   - Added format description for `Row N: key=value`
   - Added attribute mapping guide
   - Added validation checklist
   - Removed ambiguous instructions

---

## 🚀 Next Steps

1. **Test with current document** (`D4_Windows server inventory_V38.xlsx`)
2. **Verify logs** show all expected improvements
3. **Check Neo4j graph** for ~284 server entities
4. **Test with other Excel files** to ensure robustness
5. **Monitor extraction rates** across different document types

---

## 📚 Technical Debt Resolved

- ❌ **Before**: JSON blob with 154KB of metadata noise
- ✅ **After**: Clean 18KB tabular text format

- ❌ **Before**: No metadata row filtering
- ✅ **After**: Automatic detection and filtering

- ❌ **Before**: Generic prompts not matching format
- ✅ **After**: Format-specific prompts with validation

- ❌ **Before**: No visibility into extraction pipeline
- ✅ **After**: Comprehensive logging with correlation tracking

- ❌ **Before**: No detection of poor extraction
- ✅ **After**: Automatic warnings for <80% extraction rate
