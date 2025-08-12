import os
import io
import logging
from typing import Optional, Iterable, Tuple, List

from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)


class ObjectStorage:
    """
    Pluggable object storage service. Current provider: MinIO (S3 compatible).
    Folder layout (keys):
      projects/{project_id}/uploads/raw/{filename}
      projects/{project_id}/uploads/parsed/{filename}
      projects/{project_id}/uploads/canonical/{filename}
      projects/{project_id}/generated/reports/{filename}
      projects/{project_id}/logs/processing/{filename}
      projects/{project_id}/metadata/{filename}
    """

    def __init__(self):
        # Provider selection
        provider = os.getenv("STORAGE_PROVIDER") or os.getenv("OBJECT_STORAGE_PROVIDER") or "minio"
        self.provider = provider.lower()
        if self.provider not in ("minio", "s3", "azure", "filesystem"):
            logger.warning(f"Unknown STORAGE_PROVIDER={self.provider}, defaulting to minio")
            self.provider = "minio"

        # Bucket name with fallbacks; default to commonly used value in this repo
        bucket = (
            os.getenv("STORAGE_BUCKET")
            or os.getenv("OBJECT_STORAGE_BUCKET")
            or os.getenv("MINIO_BUCKET_NAME")
            or "agentimigrate"
        )
        self.bucket = bucket.strip().lower()
        if "-" in self.bucket:
            # User asked to avoid hyphens in container names; warn if present.
            logger.warning("STORAGE_BUCKET contains hyphens; consider removing them to comply with naming rules across providers.")

        if self.provider in ("minio", "s3"):
            # Endpoint and credentials fallbacks
            endpoint = os.getenv("STORAGE_ENDPOINT") or os.getenv("OBJECT_STORAGE_ENDPOINT") or os.getenv("MINIO_ENDPOINT") or "localhost:9000"
            access_key = (
                os.getenv("STORAGE_ACCESS_KEY")
                or os.getenv("OBJECT_STORAGE_ACCESS_KEY")
                or os.getenv("MINIO_ACCESS_KEY")
                or os.getenv("MINIO_ROOT_USER")
                or "minioadmin"
            )
            secret_key = (
                os.getenv("STORAGE_SECRET_KEY")
                or os.getenv("OBJECT_STORAGE_SECRET_KEY")
                or os.getenv("MINIO_SECRET_KEY")
                or os.getenv("MINIO_ROOT_PASSWORD")
                or "minioadmin"
            )
            secure_env = (
                os.getenv("STORAGE_SECURE")
                or os.getenv("OBJECT_STORAGE_SECURE")
                or os.getenv("MINIO_SECURE")
                or "false"
            )
            secure = str(secure_env).lower() in ("1", "true", "yes")
            self.client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
            self._ensure_bucket()
        else:
            # For other providers, implement adapters later. For now, raise to surface misconfig.
            if self.provider != "filesystem":
                logger.warning(f"Provider {self.provider} not yet implemented; falling back to filesystem for dev use.")
            self.client = None
            self.local_root = os.getenv("UPLOAD_ROOT_TMP") or os.getcwd()
            os.makedirs(self.local_root, exist_ok=True)

    def _ensure_bucket(self):
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info(f"Created bucket '{self.bucket}'")
        except Exception as e:
            logger.error(f"Failed ensuring bucket '{self.bucket}': {e}")
            raise

    def _key(self, project_id: str, category: str, filename: str) -> str:
        base = f"projects/{project_id}"
        mapping = {
            "uploads_raw": f"{base}/uploads/raw/",
            "uploads_parsed": f"{base}/uploads/parsed/",
            "uploads_canonical": f"{base}/uploads/canonical/",
            "generated_reports": f"{base}/generated/reports/",
            "logs_processing": f"{base}/logs/processing/",
            "metadata": f"{base}/metadata/",
        }
        prefix = mapping.get(category)
        if not prefix:
            raise ValueError(f"Unknown storage category: {category}")
        return prefix + filename

    def upload_bytes(self, project_id: str, category: str, filename: str, data: bytes, content_type: Optional[str] = None) -> str:
        if self.client:
            data_stream = io.BytesIO(data)
            size = len(data)
            ct = content_type or "application/octet-stream"
            key = self._key(project_id, category, filename)
            self.client.put_object(self.bucket, key, data_stream, size=size, content_type=ct)
            return key
        # filesystem fallback
        target = os.path.join(self.local_root, f"project_{project_id}", category)
        os.makedirs(target, exist_ok=True)
        fpath = os.path.join(target, filename)
        with open(fpath, "wb") as f:
            f.write(data)
        return fpath

    def upload_text(self, project_id: str, category: str, filename: str, text: str, content_type: Optional[str] = None) -> str:
        data = text.encode("utf-8")
        ct = content_type or "text/plain; charset=utf-8"
        return self.upload_bytes(project_id, category, filename, data, content_type=ct)

    def download(self, project_id: str, category: str, filename: str):
        if self.client:
            key = self._key(project_id, category, filename)
            try:
                response = self.client.get_object(self.bucket, key)
                stat = self.client.stat_object(self.bucket, key)
                return response, stat.content_type or "application/octet-stream", stat.size
            except S3Error as e:
                logger.error(f"Failed to download {key}: {e}")
                raise
        # filesystem fallback
        path = os.path.join(self.local_root, f"project_{project_id}", category, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        return open(path, "rb"), "application/octet-stream", os.path.getsize(path)

    def list_files(self, project_id: str, category: str, suffix_filters: Optional[Tuple[str, ...]] = None) -> List[str]:
        if self.client:
            prefix = self._key(project_id, category, "")
            objects = self.client.list_objects(self.bucket, prefix=prefix, recursive=True)
            result = []
            for obj in objects:
                name = obj.object_name[len(prefix):]
                if not name:
                    continue
                if suffix_filters and not name.lower().endswith(tuple(s.lower() for s in suffix_filters)):
                    continue
                result.append(name)
            return result
        # filesystem fallback
        root = os.path.join(self.local_root, f"project_{project_id}", category)
        if not os.path.exists(root):
            return []
        files = []
        for f in os.listdir(root):
            if os.path.isfile(os.path.join(root, f)):
                if suffix_filters and not f.lower().endswith(tuple(s.lower() for s in suffix_filters)):
                    continue
                files.append(f)
        return files


_storage_instance: Optional[ObjectStorage] = None


def get_storage() -> ObjectStorage:
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = ObjectStorage()
    return _storage_instance
