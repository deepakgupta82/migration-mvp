# Production Run Monitoring Guide

## 🎯 PURPOSE

This guide helps you monitor the production run of D4 Excel file to validate the cache collision fix is working correctly.

## 📋 PRE-RUN CHECKLIST

Before running production test, verify:

- [ ] All services are running (check VS Code tasks panel)
- [ ] Backend service accessible at http://localhost:8000
- [ ] Document service accessible at http://localhost:8003
- [ ] Graph service accessible at http://localhost:8006
- [ ] LLM service accessible at http://localhost:8007

## 🚀 RUNNING THE TEST

```powershell
# Basic run (no scatter delays)
.\run_production_test.ps1

# With scatter delays (recommended for LLM quota protection)
.\run_production_test.ps1 -EnableScatter -ScatterMinSeconds 5 -ScatterMaxSeconds 15
```

## 📊 MONITORING CHECKLIST

### 1. Document Service Logs

**Look for**: `[CACHE_FIX]` tags showing unique batch document IDs

**Expected Output**:
```log
[CACHE_FIX] Batch 1 using document_id=D4_Asset_list_systems_Unix_v22.xlsx_batch_1
[CACHE_FIX] Batch 2 using document_id=D4_Asset_list_systems_Unix_v22.xlsx_batch_2
[CACHE_FIX] Batch 3 using document_id=D4_Asset_list_systems_Unix_v22.xlsx_batch_3
[CACHE_FIX] Batch 4 using document_id=D4_Asset_list_systems_Unix_v22.xlsx_batch_4
[CACHE_FIX] Batch 5 using document_id=D4_Asset_list_systems_Unix_v22.xlsx_batch_5
[CACHE_FIX] Batch 6 using document_id=D4_Asset_list_systems_Unix_v22.xlsx_batch_6
```

**How to Check**:
- Open VS Code Terminal panel
- Click "document" task output
- Search for `[CACHE_FIX]`

**Success Criteria**: ✅ Each batch has unique `_batch_N` suffix

---

### 2. Graph Service Logs

**Look for**: Cache collision warnings (should NOT appear)

**Expected**: NO occurrences of:
```log
[CACHE] Returning cached result for correlation_id:xxx document_id:xxx
```

**Expected**: Each batch processes successfully:
```log
Successfully extracted and stored X entities with types: {...}
Structured processing completed: X entities, Y relationships
```

**How to Check**:
- Open VS Code Terminal panel
- Click "graph" task output
- Search for `[CACHE]` - should see cache checks but NO cache returns
- Search for "Successfully extracted" - should see 6 occurrences

**Success Criteria**: 
- ✅ 6 successful "Successfully extracted" logs
- ❌ 0 "Returning cached result" logs

---

### 3. Entity Count Verification

**Expected Counts** (based on D4 Excel structure):

| Batch | Expected Entities | Notes |
|-------|------------------|-------|
| Batch 1 | ~18 servers | First chunk of Excel data |
| Batch 2 | ~17 servers | Second chunk |
| Batch 3 | ~16 servers | Third chunk |
| Batch 4 | ~17 servers | Fourth chunk |
| Batch 5 | ~17 servers | Fifth chunk |
| Batch 6 | ~14 servers | Final chunk |
| **TOTAL** | **~99 entities** | **vs 0 before fix** |

**How to Check**:
- Graph service logs should show entity counts for each batch
- Look for `Successfully extracted and stored X entities`
- Sum all entity counts across 6 batches

**Success Criteria**: ✅ Total entities ≥ 90 (some variance expected)

---

### 4. Diagnostic Logging Verification

**Look for**: `[EXTRACT]` tags showing prompts and responses

**Expected Output** (per batch):
```log
[EXTRACT] PHASE: prepare_entities
[EXTRACT] PROMPT (1000 char preview): 
You are a cloud migration expert...

[EXTRACT] RESPONSE (2000 char preview):
{
  "entities": [...],
  "relationships": [...]
}

[EXTRACT] ENTITY_COUNT: X entities parsed from response
```

**How to Check**:
- Search graph service logs for `[EXTRACT]`
- Should see 6 sets of logs (one per batch)
- Each set should show prompt → response → entity count

**Success Criteria**: 
- ✅ All batches show [EXTRACT] logs
- ✅ All responses contain valid JSON
- ✅ Entity counts match successful extraction

---

### 5. Scatter Delay Verification (If Enabled)

**Look for**: `[SCATTER]` tags showing delays between batches

**Expected Output**:
```log
[SCATTER] Delaying batch 2 by X seconds
[SCATTER] Delaying batch 3 by X seconds
[SCATTER] Delaying batch 4 by X seconds
[SCATTER] Delaying batch 5 by X seconds
[SCATTER] Delaying batch 6 by X seconds
```

**How to Check**:
- Search document service logs for `[SCATTER]`
- Should see 5 delay logs (batches 2-6)

**Success Criteria**: ✅ Delays applied before each batch (if enabled)

---

## 🔍 TROUBLESHOOTING

### Problem: "Returning cached result" warnings appear

**Diagnosis**: Cache collision still occurring

**Check**:
1. Verify [CACHE_FIX] logs show unique document IDs
2. Check if document_id includes `_batch_N` suffix
3. Verify fix was applied correctly to `enhanced_processor.py`

**Solution**: Review `CACHE_COLLISION_FIX_VALIDATED.md` for fix details

---

### Problem: Entity count is 0 or very low

**Diagnosis**: Extraction pipeline failure

**Check**:
1. Search for `[EXTRACT]` logs - are prompts/responses visible?
2. Check LLM service logs for errors
3. Verify JSONL file exists and contains structured data

**Solution**: Check `DIAGNOSTIC_LOGGING_VALIDATION_RESULTS.md`

---

### Problem: JSON parsing errors

**Diagnosis**: LLM response format issues

**Check**:
1. Search for `[JSON_EXTRACT]` logs (if document assessment triggered)
2. Look for "Trying strategy" logs showing extraction attempts
3. Check if response has markdown wrappers (```json)

**Solution**: Bulletproof JSON extraction should handle this automatically

---

## 📈 SUCCESS METRICS

After production run completes, verify:

| Metric | Target | Status |
|--------|--------|--------|
| Total Entities Extracted | ≥ 90 (expected ~99) | ⬜ |
| Cache Collisions | 0 | ⬜ |
| Batches Processed | 6/6 | ⬜ |
| Unique Document IDs | 6 unique | ⬜ |
| [CACHE_FIX] Logs | 6 entries | ⬜ |
| [EXTRACT] Logs | 6 sets | ⬜ |
| "Returning cached" Warnings | 0 | ⬜ |

**Production Run Status**: 
- ✅ PASS: All metrics met
- ⚠️ PARTIAL: Some metrics failed (investigate)
- ❌ FAIL: Major issues detected (review logs)

---

## 📝 LOGGING COMMANDS

### Quick Log Searches

**Search document service logs**:
```powershell
# View entire document service output
Get-Content -Path "C:\path\to\document-service-logs.txt" -Wait

# Search for cache fix logs
Select-String -Path "C:\path\to\document-service-logs.txt" -Pattern "\[CACHE_FIX\]"

# Search for scatter delays
Select-String -Path "C:\path\to\document-service-logs.txt" -Pattern "\[SCATTER\]"
```

**Search graph service logs**:
```powershell
# Search for extraction logs
Select-String -Path "C:\path\to\graph-service-logs.txt" -Pattern "\[EXTRACT\]"

# Search for cache warnings (should be empty)
Select-String -Path "C:\path\to\graph-service-logs.txt" -Pattern "Returning cached result"

# Count successful extractions
(Select-String -Path "C:\path\to\graph-service-logs.txt" -Pattern "Successfully extracted").Count
```

**Using VS Code Terminal Panel**:
1. Open Terminal panel (Ctrl + `)
2. Click dropdown to select service task
3. Use Ctrl + F to search logs
4. Common searches:
   - `[CACHE_FIX]` - Verify unique batch IDs
   - `[EXTRACT]` - Check extraction logging
   - `[CACHE]` - Monitor cache behavior
   - `Successfully extracted` - Count extractions

---

## 🎯 EXPECTED TIMELINE

Based on validation test (6 batches, 72.9 seconds total):

| Phase | Duration | Notes |
|-------|----------|-------|
| Structured Processing | ~30-60 seconds | JSONL extraction from Excel |
| Batch 1 Processing | ~50-60 seconds | First entity extraction |
| Batch 2 Processing | ~50-60 seconds | (+ scatter delay if enabled) |
| Batch 3 Processing | ~50-60 seconds | (+ scatter delay if enabled) |
| Batch 4 Processing | ~50-60 seconds | (+ scatter delay if enabled) |
| Batch 5 Processing | ~50-60 seconds | (+ scatter delay if enabled) |
| Batch 6 Processing | ~50-60 seconds | (+ scatter delay if enabled) |
| **TOTAL** | **~6-8 minutes** | **Without scatter delays** |
| **TOTAL** | **~8-12 minutes** | **With scatter delays (5-15s each)** |

---

## 📚 REFERENCE DOCUMENTS

- **Cache Collision Fix Details**: `CACHE_COLLISION_FIX_VALIDATED.md`
- **Production Readiness**: `PRODUCTION_READY_JAN2025.md`
- **Diagnostic Logging**: `DIAGNOSTIC_LOGGING_VALIDATION_RESULTS.md`
- **All Fixes Summary**: `COMPREHENSIVE_FIXES_JAN2025.md`
- **Quick Reference**: `CACHE_COLLISION_SUMMARY.md`

---

## ✅ POST-RUN VALIDATION

After production run completes:

1. **Check Total Entity Count**:
   - Expected: ~99 servers
   - Compare to before: 0 entities
   - Status: ⬜ PASS / ⬜ FAIL

2. **Verify No Cache Collisions**:
   - Search: "Returning cached result"
   - Expected: 0 occurrences for different batch IDs
   - Status: ⬜ PASS / ⬜ FAIL

3. **Confirm All Batches Processed**:
   - Count: "Successfully extracted" logs
   - Expected: 6 occurrences
   - Status: ⬜ PASS / ⬜ FAIL

4. **Review [CACHE_FIX] Logs**:
   - Check: All batch IDs have unique `_batch_N` suffix
   - Expected: 6 unique document IDs
   - Status: ⬜ PASS / ⬜ FAIL

5. **Validate Entity Distribution**:
   - Check: Entity counts per batch (~18, ~17, ~16, ~17, ~17, ~14)
   - Variance: ±3 entities acceptable
   - Status: ⬜ PASS / ⬜ FAIL

**Overall Production Run Status**: ⬜ SUCCESS / ⬜ NEEDS REVIEW / ⬜ FAILED

---

## 🎉 SUCCESS CONFIRMATION

If all checks pass, you should see:

✅ **~99 servers extracted** (vs 0 before)  
✅ **6 batches processed independently**  
✅ **0 cache collisions detected**  
✅ **All [CACHE_FIX] logs show unique IDs**  
✅ **All [EXTRACT] logs show successful extraction**  

**Cache collision bug is ELIMINATED! 🎊**

---

**Date**: January 2025  
**Fix Status**: ✅ VALIDATED  
**Production Status**: ✅ READY  
**Next Run**: Expected ~99 servers extracted  
