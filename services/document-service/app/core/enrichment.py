"""
Lightweight document enrichment utilities.

Functions:
- detect_language(text): Best-effort language detection using langdetect.
- extract_keyphrases(text, top_n): Naive keyphrase extraction via n-grams and stopword filtering.
- enrich_text(text, project_id, corr_id): End-to-end enrichment with optional LLM-assisted keywords/summary.

No hard dependency on external LLM. If ENABLE_LLM_ENRICHMENT=true, it will call the LLM service
with process_type 'rag_synthesis' and a prompt to extract JSON keyphrases and an optional summary.
"""

from __future__ import annotations

import os
import re
import json
from typing import List, Dict, Any, Optional

_BASIC_STOPWORDS = set(
    [
        'the','a','an','and','or','of','to','in','for','on','at','by','with','from','as','is','it','this','that','these','those',
        'are','were','was','be','been','being','not','no','but','if','then','than','so','we','you','they','he','she','them','his','her',
        'their','our','us','i','me','my','mine','your','yours','its','also','can','could','should','would','may','might','will','just',
        'into','over','under','between','within','without','per','each','such','via','etc','eg','ie','vs'
    ]
)


def detect_language(text: str) -> Optional[str]:
    try:
        from langdetect import detect
        return detect(text[:5000]) if text else None
    except Exception:
        return None


def _tokenize(text: str) -> List[str]:
    # Simple word tokenizer; keep alphanumerics and dashes/underscores
    return re.findall(r"[A-Za-z][A-Za-z0-9_\-]{1,}\b", text or "")


def extract_keyphrases(text: str, top_n: int = 15) -> List[str]:
    # Very simple n-gram based keyphrase extraction
    if not text:
        return []
    words = [w.lower() for w in _tokenize(text) if w]
    words = [w for w in words if w not in _BASIC_STOPWORDS and len(w) > 2]
    if not words:
        return []

    from collections import Counter
    # Unigrams
    uni = Counter(words)
    # Bigrams
    bigrams = Counter([f"{words[i]} {words[i+1]}" for i in range(len(words)-1)])
    # Trigrams
    trigrams = Counter([f"{words[i]} {words[i+1]} {words[i+2]}" for i in range(len(words)-2)])

    # Weight longer n-grams more
    for k in bigrams:
        bigrams[k] *= 2
    for k in trigrams:
        trigrams[k] *= 3

    combined = uni + bigrams + trigrams
    # Prefer multi-word phrases by sorting key length desc as tie-breaker
    ranked = sorted(combined.items(), key=lambda kv: (kv[1], len(kv[0])), reverse=True)
    phrases: List[str] = []
    for phrase, _ in ranked:
        # Deduplicate by substring overlap (greedy)
        if any(phrase in p or p in phrase for p in phrases):
            continue
        phrases.append(phrase)
        if len(phrases) >= top_n:
            break
    return phrases


async def _llm_keywords_and_summary(text: str, project_id: Optional[str], corr_id: Optional[str]) -> Dict[str, Any]:
    """Call LLM service to extract keyphrases and an optional summary.
    Returns {'keywords': [...], 'summary': '...'} when successful, else {}.
    """
    try:
        import httpx
        headers = {"Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"}
        if corr_id:
            headers["X-Correlation-ID"] = corr_id
        prompt = (
            "You will be given a document content. Identify the top 15 domain-relevant key phrases (not generic stop words), "
            "prefer technology, product, service, vendor, system, integration names, and important nouns. Also produce a 2-3 sentence summary. "
            "Return strict JSON with keys: keywords (array of strings), summary (string). Do not include any extra text.\n\n"
            f"CONTENT:\n{text[:6000]}"
        )
        payload = {
            "process_type": "rag_synthesis",
            "prompt": prompt,
            "project_id": project_id,
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post("http://localhost:8007/api/llm/process", json=payload, headers=headers)
            if r.status_code >= 400:
                return {}
            data = r.json()
            result_text = data.get("response") or data.get("result") or ""
            try:
                parsed = json.loads(result_text) if isinstance(result_text, str) else result_text
                if isinstance(parsed, dict):
                    kws = parsed.get("keywords")
                    sm = parsed.get("summary")
                    if isinstance(kws, list) or isinstance(sm, str):
                        return {"keywords": kws or [], "summary": sm or ""}
            except Exception:
                # Non-JSON; attempt to heuristically extract lines starting with - or bullet
                lines = [ln.strip("- •\t ") for ln in (result_text or "").splitlines() if ln.strip()]
                keywords = [ln for ln in lines if 2 <= len(ln) <= 80][:15]
                return {"keywords": keywords, "summary": ""}
    except Exception:
        return {}
    return {}


async def enrich_text(text: str, project_id: Optional[str] = None, corr_id: Optional[str] = None) -> Dict[str, Any]:
    if not text or len(text.strip()) < 20:
        return {}
    lang = detect_language(text) or "unknown"
    local_kws = extract_keyphrases(text, top_n=15)
    enrichment: Dict[str, Any] = {
        "language": lang,
        "keywords": local_kws,
        "provider": "local",
    }
    if os.getenv("ENABLE_LLM_ENRICHMENT", "false").lower() in ("1", "true", "yes"):
        llm_out = await _llm_keywords_and_summary(text, project_id, corr_id)
        if llm_out:
            # Merge with preference to LLM outputs
            enrichment.update({
                "keywords": llm_out.get("keywords") or enrichment.get("keywords") or [],
                "summary": llm_out.get("summary") or "",
                "provider": "llm+local",
            })
    return enrichment
