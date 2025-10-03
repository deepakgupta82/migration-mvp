# Quick Start Guide - Testing the Fixes

## 🚀 3-Minute Quick Start

### Step 1: Restart Services (1 min)

Stop and restart these services via VS Code tasks or terminals:

```powershell
# Option A: Use VS Code task "start-all"
# Press Ctrl+Shift+P → "Tasks: Run Task" → "start-all"

# Option B: Restart individually (if services already running)
# Just restart the 4 affected services:
# - llm-service (port 8007)
# - graph-service (port 8006)
# - document-service (port 8003)
# - project-service (port 8002)
```

### Step 2: Upload Test File (1 min)

Use the frontend UI to upload:
- **File**: `D4_Asset_list_systems_Unix_v22.xlsx`
- **Extract Tables**: ✅ Yes
- **Extract Images**: Optional

### Step 3: Check Results (1 min)

**Console Logs** (llm-service):
```
✅ Look for: "Stripped markdown code blocks from LLM response"
✅ Look for: "Full LLM prompt for entity_extraction"
✅ Look for: "Full LLM response for entity_extraction"
```

**Database Check**:
```bash
cd project-service
.\.venv\Scripts\python.exe verify_migration.py
```

**Expected Results**:
- ✅ Entities: 200-500 (was 0)
- ✅ Relationships: 100-300 (was 0)
- ✅ LLM calls: 1 (was 2)
- ✅ Processing time: ~4 min (was 8 min)

---

## 🔍 Quick Verification Commands

### Check if services restarted with new code:
```powershell
# llm-service log should show the new helper function loaded
Get-Content logs/llm-service.log -Tail 20
```

### Check database migration:
```powershell
cd project-service
.\.venv\Scripts\python.exe verify_migration.py
```

### Check recent LLM calls have full data:
```powershell
# Run in project-service Python:
python -c "from database import engine; from sqlalchemy import text; 
with engine.connect() as c: 
    r = c.execute(text('SELECT correlation_id, LENGTH(prompt_text), LENGTH(response_text) FROM llm_calls ORDER BY created_at DESC LIMIT 5')); 
    print('\n'.join(str(row) for row in r.fetchall()))"
```

---

## 📊 What to Expect

### Console Output (llm-service logs)

**BEFORE** (truncated, no markdown stripping):
```
Response content (first 500 chars): ```json
{"entities": [...]}...
Extraction response not valid JSON: Expecting value: line 1 column 1
```

**AFTER** (full logging, markdown stripped):
```
Full LLM prompt for entity_extraction (corr_id=...):
[COMPLETE PROMPT - NOT TRUNCATED]
================================================================================

Stripped markdown code blocks from LLM response | original_len=5234 cleaned_len=5198

Full LLM response for entity_extraction:
{"entities": [...full response...], "relationships": [...]}
================================================================================

LLM extraction successful: 247 entities, 156 relationships
```

### Database Results

**Check llm_calls table**:
```sql
-- Recent calls should have full data
SELECT 
    correlation_id,
    LENGTH(prompt) as old_prompt_len,     -- Truncated
    LENGTH(prompt_text) as new_prompt_len, -- Full
    LENGTH(response) as old_resp_len,      -- Truncated  
    LENGTH(response_text) as new_resp_len, -- Full
    messages IS NOT NULL as has_messages
FROM llm_calls
WHERE created_at > NOW() - INTERVAL '10 minutes'
ORDER BY created_at DESC;
```

Expected:
- `old_prompt_len` ≈ 12000 (truncated)
- `new_prompt_len` ≈ 15000-20000 (full)
- `old_resp_len` ≈ 12000 (truncated)
- `new_resp_len` ≈ 5000-10000 (full)
- `has_messages` = NULL for now (can be used for multi-turn conversations)

### Graph Results (Neo4j)

**Query entities**:
```cypher
// Find recent entities
MATCH (e:Entity)
WHERE e.created_at > datetime() - duration('PT10M')
RETURN COUNT(e) as recent_entities;

// Should return 200-500 for the test file
```

**Query by correlation ID**:
```cypher
MATCH (e:Entity)
WHERE e.correlation_id = 'YOUR_CORRELATION_ID_HERE'
RETURN COUNT(e) as entity_count;

MATCH (e1:Entity)-[r]->(e2:Entity)
WHERE e1.correlation_id = 'YOUR_CORRELATION_ID_HERE'
RETURN COUNT(r) as relationship_count;
```

---

## ⚠️ Common Issues

### Issue: "Module not found" when running migration
**Solution**: Already migrated! Columns exist. Just restart services.

### Issue: Still seeing 0 entities
**Checklist**:
1. ✅ Did you restart llm-service? (Check logs for "Stripped markdown")
2. ✅ Is ENABLE_LLM_FALLBACK=false? (Check graph-service logs)
3. ✅ Are you seeing full logs? (Not truncated to 500 chars)
4. ✅ Check LLM response format hasn't changed

### Issue: Still seeing duplicate LLM calls
**Solution**: 
```bash
# Verify environment variable
echo $env:ENABLE_LLM_FALLBACK  # Should be empty or "false"

# Check graph-service logs for:
# "LLM fallback is DISABLED (set ENABLE_LLM_FALLBACK=true to enable)"
```

### Issue: Temp file locking errors
**Solution**: Already fixed with try/finally. Restart document-service.

---

## 📝 One-Liner Test

```powershell
# Quick test to verify everything works:
# 1. Restart services
# 2. Upload D4_Asset_list_systems_Unix_v22.xlsx via frontend
# 3. Check logs:

Get-Content logs/llm-service.log -Tail 50 | Select-String "Stripped markdown"
# Should return at least 1 match if processing happened
```

---

## ✅ Success Checklist

- [ ] Services restarted (llm, graph, document, project)
- [ ] Test file uploaded (D4_Asset_list_systems_Unix_v22.xlsx)
- [ ] Logs show "Stripped markdown code blocks" message
- [ ] Logs show full prompts (not truncated)
- [ ] Logs show full responses (not truncated)
- [ ] Database has prompt_text populated
- [ ] Database has response_text populated
- [ ] Graph has 200-500 entities (not 0)
- [ ] Only 1 LLM call per document (not 2)
- [ ] No temp file errors

---

## 🎯 TL;DR

1. ✅ Database already migrated (verified)
2. 🔄 Restart 4 services (llm, graph, document, project)
3. 📤 Upload test file
4. 👀 Check for "Stripped markdown" in logs
5. 🎉 Should see 200-500 entities (not 0)

**Time to test**: ~3 minutes  
**Expected improvement**: 0% → 95%+ entity extraction success

---

## 📞 Need Help?

**Check implementation details**: `FIXES_SUMMARY.md`  
**Check environment variables**: `ENV_VARS_QUICK_REF.md`  
**Check migration status**: Run `verify_migration.py`  
**Check commit message**: `COMMIT_MESSAGE.md`

**All fixes working?** → Commit and push! 🚀
