"""Continue P49 tuning only after the credential-rotation blocker is resolved."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.create_p49_hcx005_tuning_task import (
    PROMPT_SHA256,
    TASK_ARTIFACT as BLOCKER_ARTIFACT,
    TRANSPORT,
    TUNING_URL,
    api_json,
    digest,
    make_transport_artifacts,
    safe_failure,
    task_snapshot,
    write_once_or_verify,
)
from src.integrations.ncp_object_storage import NcpObjectStorageArtifacts, ObjectStorageSettings

TASK_ARTIFACT = ROOT / "evaluation/fine_tuning/p49_hcx005_tuning_task_v2.json"


def write_task_artifact(payload: dict) -> None:
    write_once_or_verify(TASK_ARTIFACT, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def receipt_payload(receipt) -> dict:
    return {"bucket": receipt.bucket, "key": receipt.key, "sha256": receipt.sha256, "size_bytes": receipt.size_bytes, "uploaded": receipt.uploaded}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Required before all external calls.")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    if not args.execute:
        print(json.dumps({"external_calls": 0, "ready": True}, ensure_ascii=False))
        return 0
    if TASK_ARTIFACT.exists():
        raise SystemExit("refusing a second post-rotation tuning task attempt")
    if not BLOCKER_ARTIFACT.exists() or (ROOT / ".env").stat().st_mtime_ns <= BLOCKER_ARTIFACT.stat().st_mtime_ns:
        raise SystemExit("credential rotation is not attested by a post-blocker .env update")
    required = ("HCX_API_KEY", "NCP_ACCESS_KEY", "NCP_SECRET_KEY")
    if any(not os.getenv(name, "").strip() for name in required):
        raise SystemExit("new credential environment is incomplete")

    transport = make_transport_artifacts()
    settings = ObjectStorageSettings.from_env()
    storage = NcpObjectStorageArtifacts(settings)
    smoke_key = f"tuning/p49-hcx005/smoke/{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex}.json"
    smoke_bytes = json.dumps({"kind": "p49_hcx005_post_rotation_putobject_smoke"}, separators=(",", ":")).encode("utf-8")
    smoke_sha = digest(smoke_bytes)
    try:
        storage.client.put_object(
            Bucket=settings.bucket, Key=smoke_key, Body=smoke_bytes, ContentType="application/json", Metadata={"sha256": smoke_sha},
        )
        remote = storage.client.head_object(Bucket=settings.bucket, Key=smoke_key)
        if (remote.get("Metadata") or {}).get("sha256") != smoke_sha:
            raise RuntimeError("smoke SHA-256 metadata did not round-trip")
        storage.client.delete_object(Bucket=settings.bucket, Key=smoke_key)
    except Exception as error:
        artifact = {
            "stage": "P49 HCX-005 post-rotation continuation", "outcome": "blocked_before_dataset_upload",
            "created_at": datetime.now(timezone.utc).isoformat(), "smoke": {"key": smoke_key, "sha256": smoke_sha, "deleted": False},
            "failure": safe_failure("putobject_smoke", error), "secrets_recorded": False,
        }
        write_task_artifact(artifact)
        print(json.dumps({"outcome": artifact["outcome"], "failure": artifact["failure"]}, ensure_ascii=False))
        return 2

    dataset_key = f"tuning/p49-hcx005/{transport['transport_csv_sha256']}/{TRANSPORT.name}"
    try:
        receipt = storage.upload_if_absent(TRANSPORT, dataset_key)
        remote = storage.client.head_object(Bucket=receipt.bucket, Key=receipt.key)
        if (remote.get("Metadata") or {}).get("sha256") != receipt.sha256 or receipt.sha256 != transport["transport_csv_sha256"]:
            raise RuntimeError("uploaded frozen transport hash did not round-trip")
    except Exception as error:
        artifact = {
            "stage": "P49 HCX-005 post-rotation continuation", "outcome": "blocked_before_task_creation",
            "created_at": datetime.now(timezone.utc).isoformat(), "smoke": {"key": smoke_key, "sha256": smoke_sha, "deleted": True},
            "dataset": transport, "failure": safe_failure("frozen_dataset_upload", error), "secrets_recorded": False,
        }
        write_task_artifact(artifact)
        print(json.dumps({"outcome": artifact["outcome"], "failure": artifact["failure"]}, ensure_ascii=False))
        return 2

    submitted = {
        "name": "p49-hcx005-peft-600-v1", "model": "HCX-005", "tuningType": "PEFT",
        "trainEpochs": 8, "learningRate": 1.0e-4, "validationSplitRatio": 0.0, "loraR": 8, "loraAlpha": 64,
        "trainingDatasetFilePath": receipt.key, "trainingDatasetBucket": receipt.bucket,
        "trainingDatasetAccessKey": os.environ["NCP_ACCESS_KEY"], "trainingDatasetSecretKey": os.environ["NCP_SECRET_KEY"],
    }
    public_hyperparameters = {key: value for key, value in submitted.items() if key not in {
        "trainingDatasetFilePath", "trainingDatasetBucket", "trainingDatasetAccessKey", "trainingDatasetSecretKey",
    }}
    try:
        created = api_json("POST", TUNING_URL, os.environ["HCX_API_KEY"], submitted)
    except Exception as error:
        artifact = {
            "stage": "P49 HCX-005 post-rotation continuation", "outcome": "task_creation_failed",
            "created_at": datetime.now(timezone.utc).isoformat(), "model": "HCX-005", "tuning_type": "PEFT",
            "prompt_sha256": PROMPT_SHA256, "dataset": transport, "object_storage": receipt_payload(receipt),
            "submitted_hyperparameters": public_hyperparameters, "failure": safe_failure("create_tuning_task", error),
            "retry_count": 0, "secrets_recorded": False,
        }
        write_task_artifact(artifact)
        print(json.dumps({"outcome": artifact["outcome"], "failure": artifact["failure"]}, ensure_ascii=False))
        return 2
    task = task_snapshot(created)
    status_failure = None
    if task.get("task_id"):
        try:
            task["status_check"] = task_snapshot(api_json("GET", f"{TUNING_URL}/{task['task_id']}", os.environ["HCX_API_KEY"]))
        except Exception as error:
            status_failure = safe_failure("get_tuning_task", error)
    artifact = {
        "stage": "P49 HCX-005 post-rotation continuation", "outcome": "task_created",
        "created_at": datetime.now(timezone.utc).isoformat(), "model": "HCX-005", "tuning_type": "PEFT",
        "prompt_sha256": PROMPT_SHA256, "dataset": transport, "object_storage": receipt_payload(receipt),
        "submitted_hyperparameters": public_hyperparameters, "task": task,
        "status_check_failure": status_failure, "retry_count": 0, "secrets_recorded": False,
    }
    write_task_artifact(artifact)
    print(json.dumps({"outcome": artifact["outcome"], "task": task, "status_check_failure": status_failure}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
