from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional


class OntologyRegistry:
    """
    Simple versioned ontology registry backed by the local filesystem.

    - Stores versions as JSON files under storage_dir/ontology_*.json
    - Performs minimal structural validation: requires 'entities' and 'relationships' arrays
    - Exposes helpers to load the latest ontology and save a new version
    """

    def __init__(self, storage_dir: str):
        self.storage_path = Path(storage_dir)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def _latest_file(self) -> Optional[Path]:
        files = sorted(self.storage_path.glob("ontology_*.json"))
        return files[-1] if files else None

    def load_latest(self) -> Dict[str, Any]:
        f = self._latest_file()
        if not f:
            raise FileNotFoundError("No ontology versions saved yet")
        return json.loads(f.read_text(encoding="utf-8"))

    def _next_version(self, current: Optional[str]) -> str:
        if not current:
            return "0.1.0"
        try:
            maj, minr, pat = [int(x) for x in current.split(".")]
            return f"{maj}.{minr}.{pat+1}"
        except Exception:
            # Fallback if the current version isn't numeric
            return f"{current}.1"

    def _quick_validate(self, onto: Dict[str, Any]) -> None:
        if not isinstance(onto, dict):
            raise ValueError("Ontology must be a JSON object")
        ents = onto.get("entities")
        rels = onto.get("relationships")
        if not isinstance(ents, list):
            raise ValueError("Ontology.entities must be a list")
        if not isinstance(rels, list):
            raise ValueError("Ontology.relationships must be a list")

    def save_new(self, ontology_json: Dict[str, Any], version: Optional[str] = None) -> Dict[str, Any]:
        self._quick_validate(ontology_json)
        # determine next version
        current_version = None
        try:
            latest = self.load_latest()
            current_version = latest.get("version")
        except FileNotFoundError:
            current_version = None
        new_version = version or self._next_version(current_version)
        payload = {
            "version": new_version,
            "created_at": time.time(),
            "ontology_json": ontology_json,
        }
        out = self.storage_path / f"ontology_{new_version}.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        return payload
