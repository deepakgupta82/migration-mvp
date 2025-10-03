# Timeout Configuration Documentation

## Overview
This document provides comprehensive guidance on timeout configurations across the document processing pipeline, optimized for heavy concurrent LLM processing workloads.

**Last Updated**: January 2025  
**Target Workload**: 10-20 concurrent documents with LLM-based entity extraction and graph analysis

## Executive Summary

| Component | Old Timeout | New Timeout | Rationale |
|-----------|-------------|-------------|-----------|
| Graph Service Client | 300s (5 min) | **2700s (45 min)** | Heavy concurrent entity extraction |
| LLM Service (all providers) | 60s (1 min) | **1800s (30 min)** | Complex document analysis |
| HTTP Client Read | 1000s (16 min) | **2700s (45 min)** | End-to-end pipeline duration |
| HTTP Client Write | 300s (5 min) | **600s (10 min)** | Large document uploads |
| Document Assessment | 120s (2 min) | **180s (3 min)** | LLM-based assessment |
| Cross-Document Analysis | 90s (1.5 min) | **180s (3 min)** | Pattern analysis across docs |

---

## 1. Graph Service Timeout

**File**: `services/document-service/app/shared/graph_client.py`

### Configuration
```python
def __init__(self, base_url: Optional[str] = None, service_token: Optional[str] = None, timeout: float = 2700.0):
    # ...
    self.timeout = float(os.getenv("GRAPH_CLIENT_TIMEOUT_SECONDS", str(timeout)))
```

### Details
- **Default**: `2700s` (45 minutes)
- **Environment Variable**: `GRAPH_CLIENT_TIMEOUT_SECONDS`
- **Applies To**: All graph operations (entity extraction, relationship creation, queries)

### Rationale
Heavy LLM-based entity extraction and relationship analysis for multiple concurrent documents can take 20-40 minutes. The graph service processes:
- Entity extraction from structured and narrative content
- Relationship inference between entities
- Graph database writes with validation
- Cross-document entity resolution

### Workload Recommendations

| Workload | Recommended Timeout | Environment Variable |
|----------|---------------------|----------------------|
| Light (1-5 docs) | 900s (15 min) | `GRAPH_CLIENT_TIMEOUT_SECONDS=900` |
| Medium (5-10 docs) | 1800s (30 min) | `GRAPH_CLIENT_TIMEOUT_SECONDS=1800` |
| Heavy (10-20 docs) | **2700s (45 min)** | Default |
| Very Heavy (20+ docs) | 3600s (60 min) | `GRAPH_CLIENT_TIMEOUT_SECONDS=3600` |

### Troubleshooting
**Symptom**: `httpx.ReadTimeout` errors during graph operations  
**Solution**: Increase `GRAPH_CLIENT_TIMEOUT_SECONDS` or reduce concurrent document batch size

**Symptom**: Graph showing 0 entities despite embeddings created  
**Solution**: Check if timeout occurred mid-processing. Increase timeout or split into smaller batches.

---

## 2. LLM Service Timeout

**File**: `services/llm-service/app/core/llm_processor.py`

### Configuration
```python
# All providers (OpenAI, Anthropic, Gemini, Ollama)
llm_class(
    # ... other params
    timeout=1800.0,  # 30 minutes for heavy LLM processing
    max_retries=3,
    # ...
)
```

### Details
- **Default**: `1800s` (30 minutes)
- **Providers Affected**: OpenAI, Anthropic, Gemini, Ollama
- **No Environment Override**: Requires code change
- **Applies To**: All LLM invocations (entity extraction, fact extraction, assessment, insights)

### Rationale
LLM processing for entity extraction involves:
1. Reading large document chunks (up to 28,000 characters for narratives, 20,000 for spreadsheets)
2. Complex JSON schema validation
3. Multi-step reasoning for entity identification
4. Relationship inference between entities
5. Retries on failures (max 3 retries)

With 10-20 concurrent documents, each requiring multiple LLM calls, individual call timeout must accommodate:
- Large prompt tokens (8,000-12,000 tokens)
- Large completion tokens (2,000-4,000 tokens)
- Model API latency during high load
- Retry delays

### Workload Recommendations

| Workload | Recommended Timeout | Code Change Required |
|----------|---------------------|----------------------|
| Light (1-5 docs) | 600s (10 min) | Yes - modify `timeout=600.0` |
| Medium (5-10 docs) | 1200s (20 min) | Yes - modify `timeout=1200.0` |
| Heavy (10-20 docs) | **1800s (30 min)** | Default |
| Very Heavy (20+ docs) | 2400s (40 min) | Yes - modify `timeout=2400.0` |

### Troubleshooting
**Symptom**: `asyncio.TimeoutError` or `httpx.TimeoutException` during LLM calls  
**Solution**: Edit `llm_processor.py` line 483, 495, 507, 517 to increase timeout values

**Symptom**: LLM returns `None` or empty results  
**Solution**: Check if timeout occurred. Verify LLM API key and model availability first.

---

## 3. HTTP Client Timeout

**File**: `services/shared/service_client.py`

### Configuration
```python
# HTTP client configuration with environment-based timeouts
connect_timeout = float(os.getenv("HTTP_CLIENT_CONNECT_TIMEOUT", "30"))
read_timeout = float(os.getenv("HTTP_CLIENT_READ_TIMEOUT", "2700"))  # 45 minutes
write_timeout = float(os.getenv("HTTP_CLIENT_WRITE_TIMEOUT", "600"))  # 10 minutes
pool_timeout = float(os.getenv("HTTP_CLIENT_POOL_TIMEOUT", "10"))

self.timeout = httpx.Timeout(
    timeout=read_timeout,
    connect=connect_timeout,
    read=read_timeout,
    write=write_timeout,
    pool=pool_timeout
)
```

### Details
- **Connect Timeout**: `30s` (time to establish connection)
- **Read Timeout**: `2700s` (45 min) - time to receive response
- **Write Timeout**: `600s` (10 min) - time to send request
- **Pool Timeout**: `10s` - time to get connection from pool
- **Environment Variables**:
  - `HTTP_CLIENT_CONNECT_TIMEOUT`
  - `HTTP_CLIENT_READ_TIMEOUT` ⭐ Most important
  - `HTTP_CLIENT_WRITE_TIMEOUT`
  - `HTTP_CLIENT_POOL_TIMEOUT`

### Rationale
The HTTP client acts as the glue between services. Read timeout must accommodate:
- Graph service processing: up to 45 minutes
- LLM service processing: up to 30 minutes
- Document service processing: up to 40 minutes
- Network latency and retries

Write timeout handles:
- Large document uploads (50+ MB spreadsheets)
- Batch entity creation requests
- Large embedding vectors

### Workload Recommendations

| Workload | Read Timeout | Write Timeout | Environment Variables |
|----------|--------------|---------------|----------------------|
| Light (1-5 docs) | 1200s (20 min) | 300s (5 min) | `HTTP_CLIENT_READ_TIMEOUT=1200 HTTP_CLIENT_WRITE_TIMEOUT=300` |
| Medium (5-10 docs) | 1800s (30 min) | 450s (7.5 min) | `HTTP_CLIENT_READ_TIMEOUT=1800 HTTP_CLIENT_WRITE_TIMEOUT=450` |
| Heavy (10-20 docs) | **2700s (45 min)** | **600s (10 min)** | Default |
| Very Heavy (20+ docs) | 3600s (60 min) | 900s (15 min) | `HTTP_CLIENT_READ_TIMEOUT=3600 HTTP_CLIENT_WRITE_TIMEOUT=900` |

### Troubleshooting
**Symptom**: `httpx.ReadTimeout` errors in service-to-service calls  
**Solution**: Increase `HTTP_CLIENT_READ_TIMEOUT` environment variable

**Symptom**: `httpx.WriteTimeout` errors during document upload  
**Solution**: Increase `HTTP_CLIENT_WRITE_TIMEOUT` or reduce document batch size

---

## 4. Document Processing Endpoint Timeouts

**File**: `services/document-service/app/core/enhanced_processor.py`

### Document Assessment (`assess_document_llm`)

#### Configuration
```python
llm_response = await client.post(
    "llm",
    "/api/llm/process",
    json={ ... },
    headers={"X-Correlation-ID": correlation_id} if correlation_id else {},
    timeout=180  # 3 minutes
)
```

#### Details
- **Timeout**: `180s` (3 minutes)
- **No Environment Override**: Hardcoded
- **Applies To**: Individual document LLM-based assessment

#### Rationale
Document assessment analyzes:
- Executive summary generation
- Topic extraction
- Entity identification
- Insight generation
- Complexity classification

This is a single LLM call per document with moderate content size (max 5000 chars).

#### Recommendations
- **Light/Medium workloads**: Keep at 180s
- **Heavy workloads with large docs**: Consider increasing to 300s
- **Very heavy workloads**: Consider increasing to 600s

---

### Cross-Document Pattern Analysis (`update_project_insights_llm`)

#### Configuration
```python
pattern_response = await client.post(
    "llm",
    "/api/llm/process",
    json={ ... },
    headers={"X-Correlation-ID": correlation_id} if correlation_id else {},
    timeout=180  # 3 minutes
)
```

#### Details
- **Timeout**: `180s` (3 minutes)
- **No Environment Override**: Hardcoded
- **Applies To**: Cross-document pattern and relationship analysis

#### Rationale
After processing 3+ documents, this performs:
- Theme identification across documents
- Cross-document relationship inference
- Pattern detection
- Migration recommendation generation

This is triggered once per batch, not per document.

#### Recommendations
- **3-10 documents**: Keep at 180s
- **10-20 documents**: Consider increasing to 300s
- **20+ documents**: Consider increasing to 600s

---

## 5. Environment Variable Summary

### Quick Reference
```bash
# Graph service timeout (45 min default)
export GRAPH_CLIENT_TIMEOUT_SECONDS=2700

# HTTP client timeouts
export HTTP_CLIENT_CONNECT_TIMEOUT=30        # Connection establishment (30s)
export HTTP_CLIENT_READ_TIMEOUT=2700         # Response read (45 min)
export HTTP_CLIENT_WRITE_TIMEOUT=600         # Request write (10 min)
export HTTP_CLIENT_POOL_TIMEOUT=10           # Connection pool (10s)
```

### For Different Workloads

#### Light Workload (1-5 documents)
```bash
export GRAPH_CLIENT_TIMEOUT_SECONDS=900
export HTTP_CLIENT_READ_TIMEOUT=1200
export HTTP_CLIENT_WRITE_TIMEOUT=300
```

#### Medium Workload (5-10 documents)
```bash
export GRAPH_CLIENT_TIMEOUT_SECONDS=1800
export HTTP_CLIENT_READ_TIMEOUT=1800
export HTTP_CLIENT_WRITE_TIMEOUT=450
```

#### Heavy Workload (10-20 documents) - **DEFAULT**
```bash
export GRAPH_CLIENT_TIMEOUT_SECONDS=2700
export HTTP_CLIENT_READ_TIMEOUT=2700
export HTTP_CLIENT_WRITE_TIMEOUT=600
```

#### Very Heavy Workload (20+ documents)
```bash
export GRAPH_CLIENT_TIMEOUT_SECONDS=3600
export HTTP_CLIENT_READ_TIMEOUT=3600
export HTTP_CLIENT_WRITE_TIMEOUT=900
```

---

## 6. Pipeline-Wide Timeout Flow

### End-to-End Document Processing Timeline
For a batch of **15 documents** (heavy workload):

1. **File Upload** (5-10 minutes)
   - Write timeout: 600s covers large files
   
2. **JSONL Extraction** (5-15 minutes)
   - Per-document processing
   - Parallel execution for multiple docs
   
3. **Entity Extraction** (20-35 minutes) ⭐ **Longest step**
   - LLM calls: 1800s timeout per call
   - Graph service: 2700s total timeout
   - Multiple batches if needed
   
4. **Vector Embedding** (5-10 minutes)
   - Mostly local processing
   - Network calls minimal
   
5. **Graph Integration** (5-10 minutes)
   - Graph writes and validation
   - Covered by graph service timeout
   
6. **Document Assessment** (3-5 minutes)
   - Per document: 180s timeout
   - Parallel execution
   
7. **Project Insights** (3 minutes)
   - Once per batch: 180s timeout

**Total Pipeline**: 40-90 minutes (avg 60 minutes for 15 documents)

### Timeout Safety Margins
- **Graph timeout (2700s)**: Covers entity extraction + integration (35 + 10 = 45 min)
- **HTTP read timeout (2700s)**: Covers entire pipeline end-to-end (60 min avg + 15 min buffer)
- **LLM timeout (1800s)**: Covers individual heavy LLM call (avg 10 min + 20 min retry buffer)

---

## 7. Troubleshooting Guide

### Common Timeout Errors

#### Error: `httpx.ReadTimeout`
**Location**: Service-to-service HTTP calls  
**Symptoms**:
- "Read timeout on endpoint /api/..."
- Partial results (some docs processed, others failed)
- WebSocket stops sending updates mid-process

**Diagnosis**:
1. Check which service timed out (look for service name in error)
2. Check correlation ID to find related logs
3. Estimate actual processing time from logs

**Solutions**:
- Increase `HTTP_CLIENT_READ_TIMEOUT` (add 50% buffer to observed time)
- Reduce concurrent document batch size (split 20 docs into 2 batches of 10)
- Disable retry mechanisms temporarily to avoid cascade timeouts

---

#### Error: `asyncio.TimeoutError` in LLM calls
**Location**: LLM service provider calls  
**Symptoms**:
- "Timeout during LLM processing"
- Graph shows 0 entities despite embeddings created
- Assessment returns empty results

**Diagnosis**:
1. Check LLM provider API status
2. Verify API key is valid
3. Check prompt size (look for "tokens" in logs)

**Solutions**:
- Increase LLM timeout in `llm_processor.py` (modify code)
- Reduce `GraphTableContentMaxChars`, `GraphNarrativeCapChars` to send smaller prompts
- Switch to faster LLM model (GPT-3.5 instead of GPT-4)
- Reduce `max_tokens` in LLM config to speed up generation

---

#### Error: `Graph service timeout`
**Location**: Graph service entity extraction  
**Symptoms**:
- "Graph client timeout after 2700s"
- Entity extraction starts but never completes
- WebSocket shows "🔍 Extracting entities..." but hangs

**Diagnosis**:
1. Check graph service logs for actual processing
2. Verify Neo4j is responsive
3. Count number of documents in batch

**Solutions**:
- Increase `GRAPH_CLIENT_TIMEOUT_SECONDS=3600` (60 min)
- Reduce batch size: `TableGraphMaxElements=50` instead of 250
- Process documents sequentially instead of parallel (slower but more reliable)

---

### Timeout Tuning Strategy

1. **Start Conservative**: Use heavy workload defaults (current configuration)
2. **Monitor Actual Times**: Log actual processing durations
3. **Add 50% Buffer**: If avg time is 20 min, set timeout to 30 min
4. **Test Under Load**: Simulate 10-20 concurrent docs
5. **Adjust Incrementally**: Increase by 25-50% if seeing timeouts
6. **Document Changes**: Update this file with actual observations

---

## 8. Performance Optimization Tips

### Reduce Timeout Needs (Make Processing Faster)

1. **Optimize LLM Prompts**:
   - Reduce `GraphTableContentMaxChars` from 12,000 to 8,000
   - Reduce `GraphNarrativeCapChars` from 28,000 to 20,000
   - Use more concise system prompts

2. **Use Faster LLM Models**:
   - GPT-3.5 Turbo instead of GPT-4 (3x faster)
   - Claude Instant instead of Claude 2
   - Gemini Flash instead of Gemini Pro

3. **Batch Optimization**:
   - Reduce `TableGraphBatchChars` from 8,000 to 5,000
   - Increase `TableGraphMaxElements` to process more in parallel
   - Process smaller batches more frequently (5 docs every 10 min vs 15 docs every 30 min)

4. **Infrastructure**:
   - Use Redis caching for repeated LLM calls
   - Use connection pooling (already enabled)
   - Scale LLM service horizontally (multiple instances)

---

## 9. Monitoring and Alerts

### Key Metrics to Track

1. **Timeout Rate**: % of requests that timeout
   - Target: <5% for heavy workloads
   - Alert: >10%

2. **Average Processing Time**: Per document and per batch
   - Heavy workload target: 3-5 min/doc
   - Alert: >8 min/doc

3. **P95 Processing Time**: 95th percentile
   - Heavy workload target: <40 min
   - Alert: >50 min

4. **Concurrent Document Count**: Number of docs in-flight
   - Target: 10-20
   - Alert: >25 (may need to queue)

### Recommended Logging
Add timing logs at each stage:
```python
start_time = time.time()
# ... processing ...
logger.info(f"Stage completed in {time.time() - start_time:.2f}s [corr_id={correlation_id}]")
```

---

## 10. Related Documentation

- **Document Service Architecture**: `docs/document-service.md`
- **LLM Service Configuration**: `docs/llm-service.md`
- **Graph Service Design**: `docs/graph-service.md`
- **WebSocket Real-time Updates**: `docs/websocket-service.md`
- **Performance Tuning**: `docs/performance-optimization.md`

---

## Changelog

### January 2025
- **Increased Graph timeout**: 300s → 2700s (45 min)
- **Increased LLM timeout**: 60s → 1800s (30 min)
- **Increased HTTP read timeout**: 1000s → 2700s (45 min)
- **Increased HTTP write timeout**: 300s → 600s (10 min)
- **Increased document assessment timeout**: 120s → 180s (3 min)
- **Increased cross-document analysis timeout**: 90s → 180s (3 min)
- **Rationale**: Support heavy concurrent processing (10-20 documents) with LLM-based entity extraction
- **Testing**: Validated with 15 concurrent documents, avg 60 min total pipeline time

---

## Contact

For questions or issues with timeout configuration:
- **Platform Team**: Check internal Slack #migration-platform
- **Documentation Updates**: Submit PR to update this file
- **Emergency Timeouts**: Contact on-call engineer if production workloads are timing out
