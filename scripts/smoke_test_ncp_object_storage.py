"""Explicit NCP Object Storage smoke test; it never prints credentials.

Run only after setting NCP_OBJECT_STORAGE_ENABLED=true in the server's .env.
The script writes one small, uniquely named JSON artifact under the selected
prefix and verifies its remote SHA-256 metadata.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from uuid import uuid4

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.integrations.ncp_object_storage import NcpObjectStorageArtifacts, ObjectStorageSettings


def _safe_error(error: Exception) -> dict[str, str | None]:
    """Return provider diagnostics without exception text or configuration."""
    response = getattr(error, "response", None) or {}
    provider_error = response.get("Error") or {}
    return {
        "exception_type": type(error).__name__,
        "provider_error_code": provider_error.get("Code"),
        "provider_operation": getattr(error, "operation_name", None),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", default="smoke/ncp-1", help="relative Object Storage key prefix")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    settings = ObjectStorageSettings.from_env()
    if not settings.enabled:
        raise SystemExit("Set NCP_OBJECT_STORAGE_ENABLED=true before running this explicit upload test.")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    key = f"{args.prefix.strip('/')}/{timestamp}-{uuid4().hex}.json"
    try:
        with TemporaryDirectory(prefix="pension-agent-ncp-smoke-") as temp_dir:
            path = Path(temp_dir) / "object_storage_smoke.json"
            path.write_text(
                json.dumps({"kind": "ncp_object_storage_smoke", "created_at": timestamp}, ensure_ascii=False),
                encoding="utf-8",
            )
            store = NcpObjectStorageArtifacts(settings)
            receipt = store.upload_if_absent(path, key)
            repeated = store.upload_if_absent(path, key)
            remote = store.client.head_object(Bucket=receipt.bucket, Key=receipt.key)
    except Exception as error:
        print(json.dumps({"ok": False, "stage": "object_storage_upload", **_safe_error(error)}, ensure_ascii=False))
        return 1

    if (remote.get("Metadata") or {}).get("sha256") != receipt.sha256:
        raise RuntimeError("Uploaded artifact SHA-256 metadata did not round-trip")
    if not receipt.uploaded or repeated.uploaded or repeated.sha256 != receipt.sha256:
        raise RuntimeError("Object Storage immutable-key idempotence check failed")
    print(json.dumps({
        "ok": True,
        "bucket": receipt.bucket,
        "key": receipt.key,
        "sha256": receipt.sha256,
        "size_bytes": receipt.size_bytes,
        "first_upload_created": receipt.uploaded,
        "same_key_second_upload_created": repeated.uploaded,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
