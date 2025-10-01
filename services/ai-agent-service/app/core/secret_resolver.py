"""
Minimal SecretRef resolver for MCP auth and process environments.

Supports provider="env" by reading from environment variables. For AWS/Azure/GCP,
we accept JSON blobs in the referenced env var and map them into well-known envs.

AWS:  {"access_key_id":"...","secret_access_key":"...","session_token":"..."}
Azure:{"tenant_id":"...","client_id":"...","client_secret":"..."}
GCP:  Entire service account JSON string; we write it to a temp file and set GOOGLE_APPLICATION_CREDENTIALS.

Other providers (keyvault, aws-sm, gcp-sm) are TODO for later integration.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from typing import Dict, Optional, Tuple

from .mcp_models import SecretRef, MCPServerConfig

logger = logging.getLogger("secret-resolver")


def _read_env_json(ref: SecretRef) -> Optional[Dict]:
    if not ref or not ref.ref:
        return None
    value = os.getenv(ref.ref)
    if not value:
        logger.warning(f"SecretRef env '{ref.ref}' not set")
        return None
    try:
        return json.loads(value)
    except Exception:
        logger.warning(f"SecretRef env '{ref.ref}' does not contain valid JSON; skipping JSON parse")
        return None


def build_env_for_mcp(cfg: MCPServerConfig) -> Tuple[Dict[str, str], Optional[str]]:
    """Return a copy of os.environ merged with cfg.env and any resolved secrets.

    Returns (env, temp_gcp_keyfile_path) so caller can clean up temp file if needed.
    """
    env = os.environ.copy()
    env.update(cfg.env or {})
    temp_gcp_path: Optional[str] = None

    # AWS creds via env JSON
    if cfg.auth and cfg.auth.aws and cfg.auth.aws.credentials and (cfg.auth.aws.credentials.provider or "env") == "env":
        data = _read_env_json(cfg.auth.aws.credentials)
        if data:
            ak = data.get("access_key_id") or data.get("aws_access_key_id")
            sk = data.get("secret_access_key") or data.get("aws_secret_access_key")
            st = data.get("session_token") or data.get("aws_session_token")
            if ak and sk:
                env["AWS_ACCESS_KEY_ID"] = ak
                env["AWS_SECRET_ACCESS_KEY"] = sk
            if st:
                env["AWS_SESSION_TOKEN"] = st
    if cfg.auth and cfg.auth.aws and cfg.auth.aws.region:
        env["AWS_REGION"] = cfg.auth.aws.region

    # Azure Managed Identity or creds via env JSON
    if cfg.auth and cfg.auth.azure:
        if getattr(cfg.auth.azure, "useManagedIdentity", False):
            # With MSI, client ID may be provided for user-assigned identity
            if cfg.auth.azure.clientId:
                env.setdefault("AZURE_CLIENT_ID", cfg.auth.azure.clientId)
        elif cfg.auth.azure.secret and (cfg.auth.azure.secret.provider or "env") == "env":
            data = _read_env_json(cfg.auth.azure.secret)
            if data:
                ten = data.get("tenant_id") or data.get("tenantId")
                cid = data.get("client_id") or data.get("clientId")
                sec = data.get("client_secret") or data.get("secret")
                if ten:
                    env["AZURE_TENANT_ID"] = ten
                if cid:
                    env["AZURE_CLIENT_ID"] = cid
                if sec:
                    env["AZURE_CLIENT_SECRET"] = sec
    # Pass through tenantId/clientId if set directly
    if cfg.auth and cfg.auth.azure:
        if cfg.auth.azure.tenantId:
            env.setdefault("AZURE_TENANT_ID", cfg.auth.azure.tenantId)
        if cfg.auth.azure.clientId:
            env.setdefault("AZURE_CLIENT_ID", cfg.auth.azure.clientId)

    # GCP ADC or service account: write to temp file and point GOOGLE_APPLICATION_CREDENTIALS
    if cfg.auth and cfg.auth.gcp:
        if getattr(cfg.auth.gcp, "useADC", False):
            # Rely on host ADC; nothing to set
            pass
        elif cfg.auth.gcp.serviceAccountKey and (cfg.auth.gcp.serviceAccountKey.provider or "env") == "env":
            raw = os.getenv(cfg.auth.gcp.serviceAccountKey.ref)
            if raw:
                try:
                    # Validate that it's JSON
                    json.loads(raw)
                    fd, path = tempfile.mkstemp(prefix="mcp-gcp-", suffix=".json")
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        f.write(raw)
                    env["GOOGLE_APPLICATION_CREDENTIALS"] = path
                    temp_gcp_path = path
                except Exception as e:
                    logger.warning(f"Invalid GCP service account JSON in env '{cfg.auth.gcp.serviceAccountKey.ref}': {e}")

    return env, temp_gcp_path
