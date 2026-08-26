"""Explicit, content-addressed uploads to NCP Object Storage.

This module is intentionally not called by the request path.  It is for
versioned datasets, manifests, evaluation reports, and release metadata after
their local freeze gates have passed.  It never uploads raw corpus files
implicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import mimetypes
import os
from pathlib import Path
from typing import Any


def _enabled(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ObjectStorageSettings:
    enabled: bool = False
    endpoint: str = ""
    access_key: str = ""
    secret_key: str = ""
    bucket: str = ""

    @classmethod
    def from_env(cls) -> "ObjectStorageSettings":
        settings = cls(
            enabled=_enabled(os.getenv("NCP_OBJECT_STORAGE_ENABLED")),
            endpoint=os.getenv("NCP_OBJECT_ENDPOINT", "").strip(),
            access_key=os.getenv("NCP_ACCESS_KEY", "").strip(),
            secret_key=os.getenv("NCP_SECRET_KEY", "").strip(),
            bucket=os.getenv("NCP_OBJECT_BUCKET", "").strip(),
        )
        if settings.enabled:
            missing = [
                name for name, value in {
                    "NCP_OBJECT_ENDPOINT": settings.endpoint,
                    "NCP_ACCESS_KEY": settings.access_key,
                    "NCP_SECRET_KEY": settings.secret_key,
                    "NCP_OBJECT_BUCKET": settings.bucket,
                }.items() if not value
            ]
            if missing:
                raise RuntimeError(f"NCP Object Storage is enabled but missing: {', '.join(missing)}")
        return settings


@dataclass(frozen=True)
class ArtifactReceipt:
    bucket: str
    key: str
    sha256: str
    size_bytes: int
    uploaded: bool


class ArtifactConflictError(RuntimeError):
    """A key was already occupied by different content."""


class NcpObjectStorageArtifacts:
    """Upload an explicit immutable artifact, never a directory tree."""

    def __init__(self, settings: ObjectStorageSettings, client: Any | None = None):
        if not settings.enabled:
            raise RuntimeError("NCP Object Storage is disabled")
        self.settings = settings
        self._client = client

    @property
    def client(self):
        if self._client is None:
            try:
                import boto3
            except ImportError as error:  # pragma: no cover - deployment configuration boundary
                raise RuntimeError("boto3 is required for NCP Object Storage uploads") from error
            self._client = boto3.client(
                "s3",
                endpoint_url=self.settings.endpoint,
                aws_access_key_id=self.settings.access_key,
                aws_secret_access_key=self.settings.secret_key,
            )
        return self._client

    @staticmethod
    def _digest(path: Path) -> tuple[str, int]:
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
                size += len(block)
        return digest.hexdigest(), size

    @staticmethod
    def _not_found(error: Exception) -> bool:
        response = getattr(error, "response", None)
        code = str((response or {}).get("Error", {}).get("Code", ""))
        return code in {"404", "NoSuchKey", "NotFound"}

    def upload_if_absent(self, local_path: str | Path, key: str) -> ArtifactReceipt:
        """Upload a file once, or verify the existing key has the same SHA-256."""
        path = Path(local_path)
        if not path.is_file():
            raise FileNotFoundError(path)
        if not key or key.startswith("/") or ".." in Path(key).parts:
            raise ValueError("Object Storage key must be a relative artifact key")

        sha256, size = self._digest(path)
        try:
            existing = self.client.head_object(Bucket=self.settings.bucket, Key=key)
        except Exception as error:
            if not self._not_found(error):
                raise
        else:
            stored_sha = (existing.get("Metadata") or {}).get("sha256")
            if stored_sha == sha256:
                return ArtifactReceipt(self.settings.bucket, key, sha256, size, uploaded=False)
            raise ArtifactConflictError(f"Object Storage key already exists with a different SHA-256: {key}")

        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        with path.open("rb") as handle:
            self.client.put_object(
                Bucket=self.settings.bucket,
                Key=key,
                Body=handle,
                ContentType=content_type,
                Metadata={"sha256": sha256},
            )
        return ArtifactReceipt(self.settings.bucket, key, sha256, size, uploaded=True)
