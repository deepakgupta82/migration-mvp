import os
import json
import tempfile
from typing import Dict, List, Optional
from .git_utils import _repo_root


PROMPT_ROOT = os.path.join(_repo_root(), "services")


def _service_prompt_dir(service_name: str) -> str:
    return os.path.join(PROMPT_ROOT, service_name, "prompts")


def list_services() -> List[str]:
    try:
        names = []
        for name in os.listdir(PROMPT_ROOT):
            d = os.path.join(PROMPT_ROOT, name)
            if os.path.isdir(d) and os.path.isdir(os.path.join(d, "prompts")):
                names.append(name)
        return sorted(names)
    except Exception:
        return []


def list_prompts(service_name: str) -> List[Dict]:
    out: List[Dict] = []
    pdir = _service_prompt_dir(service_name)
    if not os.path.isdir(pdir):
        return out
    for fname in os.listdir(pdir):
        if not fname.lower().endswith(".json"):
            continue
        try:
            with open(os.path.join(pdir, fname), "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    # normalize id from filename if missing
                    data.setdefault("id", os.path.splitext(fname)[0])
                    data.setdefault("service", service_name)
                    out.append(data)
        except Exception:
            # ignore malformed
            continue
    return out


def get_prompt(service_name: str, prompt_id: str) -> Optional[Dict]:
    pdir = _service_prompt_dir(service_name)
    path = os.path.join(pdir, f"{prompt_id}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                data.setdefault("id", prompt_id)
                data.setdefault("service", service_name)
                return data
    except Exception:
        return None
    return None


def validate_prompt(doc: Dict) -> List[str]:
    errors: List[str] = []
    required = ["id", "service", "text"]
    for k in required:
        if not doc.get(k):
            errors.append(f"missing required field: {k}")
    # allowed fields
    allowed = {"id", "service", "purpose", "description", "variables", "text", "version", "updated_by", "updated_at", "metadata"}
    for k in doc.keys():
        if k not in allowed:
            errors.append(f"unknown field: {k}")
    # variables array of strings
    if "variables" in doc and not isinstance(doc["variables"], list):
        errors.append("variables must be a list of strings")
    return errors


def save_prompt(doc: Dict) -> str:
    """Atomically save prompt JSON based on doc['service'] and doc['id'].
    Returns absolute file path written.
    """
    service = doc.get("service")
    pid = doc.get("id")
    if not service or not pid:
        raise ValueError("prompt must include 'service' and 'id'")
    out_dir = _service_prompt_dir(service)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{pid}.json")

    # Ensure stable ordering
    payload = json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True)
    # Atomic write via temp file then replace
    dir_name = os.path.dirname(path)
    fd, tmp_path = tempfile.mkstemp(prefix=f".{pid}.", suffix=".json", dir=dir_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.write(payload)
        # Windows: os.replace works atomically when on same volume
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
    return path
