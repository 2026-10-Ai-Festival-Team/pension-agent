"""Create exactly one immutable HCX-005 PEFT baseline tuning task.

The Final Acceptance export is intentionally never rewritten.  CLOVA Studio's
upload schema requires a different CSV column order and zero-based C_ID/T_ID,
so this script produces a transport-only mirror after proving that the 600
training payloads are byte-for-byte equivalent at the field level.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
EXPORT = ROOT / "evaluation/fine_tuning/p49_hcx005_training_export_v1.csv"
EXPORT_MANIFEST = ROOT / "evaluation/fine_tuning/p49_hcx005_training_export_manifest_v1.json"
PROMPT = ROOT / "evaluation/fine_tuning/generator_prompt_final_v1.json"
TRANSPORT = ROOT / "evaluation/fine_tuning/p49_hcx005_training_export_ncp_transport_v1.csv"
TRANSPORT_MANIFEST = ROOT / "evaluation/fine_tuning/p49_hcx005_training_export_ncp_transport_manifest_v1.json"
TASK_ARTIFACT = ROOT / "evaluation/fine_tuning/p49_hcx005_tuning_task_v1.json"

SOURCE_COLUMNS = ["C_ID", "T_ID", "System_Prompt", "Text", "Completion"]
NCP_COLUMNS = ["System_Prompt", "C_ID", "T_ID", "Text", "Completion"]
PAYLOAD_COLUMNS = ["System_Prompt", "Text", "Completion"]
PROMPT_SHA256 = "6c364cfc41367b7a5f4f4d521e4c2adaf1bd320182fb80bce69624c7625bb10a"
EXPORT_SHA256 = "a625c4f5771b50c8796e0ddba93826be18930ca76cb99bd53a52e8dfa381748a"
TUNING_URL = "https://clovastudio.stream.ntruss.com/tuning/v2/tasks"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_payload_hash(rows: list[dict[str, str]]) -> str:
    """Hash only model-visible strings, independent of provider CSV metadata."""
    content = "".join(
        json.dumps({key: row[key] for key in PAYLOAD_COLUMNS}, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in rows
    ).encode("utf-8")
    return digest(content)


def read_source_rows() -> list[dict[str, str]]:
    if digest(EXPORT.read_bytes()) != EXPORT_SHA256:
        raise RuntimeError("frozen training export SHA-256 mismatch")
    with EXPORT.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != SOURCE_COLUMNS:
            raise RuntimeError("frozen training export header drift")
        rows = list(reader)
    if len(rows) != 600:
        raise RuntimeError("frozen training export record count drift")
    for index, row in enumerate(rows, start=1):
        if row["C_ID"] != str(index) or row["T_ID"] != str(index):
            raise RuntimeError("frozen training export source IDs drift")
        if any(not row.get(column) for column in PAYLOAD_COLUMNS):
            raise RuntimeError("frozen training export has an empty required field")
    return rows


def ncp_rows(source_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "System_Prompt": source["System_Prompt"],
            "C_ID": str(index),
            "T_ID": str(index),
            "Text": source["Text"],
            "Completion": source["Completion"],
        }
        for index, source in enumerate(source_rows)
    ]


def csv_bytes(rows: list[dict[str, str]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=NCP_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    # CLOVA reports non-UTF-8-sig data as unsupported, so this intentionally has
    # a UTF-8 BOM without changing any row's strings.
    return stream.getvalue().encode("utf-8-sig")


def write_once_or_verify(path: Path, content: bytes) -> str:
    expected = digest(content)
    if path.exists():
        if digest(path.read_bytes()) != expected:
            raise RuntimeError(f"immutable artifact collision: {path.name}")
        return expected
    path.write_bytes(content)
    return expected


def make_transport_artifacts() -> dict[str, Any]:
    source_rows = read_source_rows()
    delivery_rows = ncp_rows(source_rows)
    source_payload_hash = canonical_payload_hash(source_rows)
    delivery_payload_hash = canonical_payload_hash(delivery_rows)
    if source_payload_hash != delivery_payload_hash:
        raise RuntimeError("transport mirror changed a model-visible training payload")
    data = csv_bytes(delivery_rows)
    transport_hash = write_once_or_verify(TRANSPORT, data)
    # Re-read the immutable mirror to make the on-disk check explicit.
    with TRANSPORT.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != NCP_COLUMNS:
            raise RuntimeError("NCP transport header mismatch")
        persisted = list(reader)
    if len(persisted) != 600 or canonical_payload_hash(persisted) != source_payload_hash:
        raise RuntimeError("NCP transport integrity check failed")
    if [(row["C_ID"], row["T_ID"]) for row in persisted] != [(str(i), str(i)) for i in range(600)]:
        raise RuntimeError("NCP transport IDs are not contiguous zero-based values")
    manifest = {
        "stage": "P49 HCX-005 CLOVA transport preflight",
        "kind": "schema_transport_mirror_not_a_new_training_dataset",
        "source_export": EXPORT.name,
        "source_export_sha256": EXPORT_SHA256,
        "records": 600,
        "source_columns": SOURCE_COLUMNS,
        "ncp_required_columns": NCP_COLUMNS,
        "source_id_range": "1..600",
        "ncp_id_range": "0..599",
        "encoding": "UTF-8-SIG",
        "model_visible_payload_sha256": source_payload_hash,
        "transport_csv": TRANSPORT.name,
        "transport_csv_sha256": transport_hash,
        "payload_changed": False,
        "transport_preflight_go": True,
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    manifest_hash = write_once_or_verify(TRANSPORT_MANIFEST, manifest_bytes)
    return {**manifest, "transport_manifest": TRANSPORT_MANIFEST.name, "transport_manifest_sha256": manifest_hash}


def redact(value: str) -> str:
    for variable in ("HCX_API_KEY", "NCP_ACCESS_KEY", "NCP_SECRET_KEY"):
        secret = os.getenv(variable, "")
        if secret:
            value = value.replace(secret, "<redacted>")
    return value[:800]


def safe_failure(stage: str, error: Exception) -> dict[str, Any]:
    response = getattr(error, "response", None) or {}
    detail: dict[str, Any] = {"stage": stage, "exception_type": type(error).__name__}
    if response:
        provider = response.get("Error") or {}
        detail["provider_error_code"] = provider.get("Code")
        detail["provider_operation"] = getattr(error, "operation_name", None)
    if isinstance(error, HTTPError):
        detail["http_status"] = error.code
        try:
            raw = error.read().decode("utf-8", errors="replace")
            parsed = json.loads(raw)
            status = parsed.get("status") if isinstance(parsed, dict) else None
            detail["provider_status_code"] = status.get("code") if isinstance(status, dict) else None
            detail["provider_message"] = redact(str(status.get("message", ""))) if isinstance(status, dict) else redact(raw)
        except Exception:
            detail["provider_message"] = "unavailable"
    elif isinstance(error, URLError):
        detail["network_reason"] = redact(str(error.reason))
    return detail


def api_json(method: str, url: str, api_key: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-NCP-CLOVASTUDIO-REQUEST-ID": str(uuid4()),
        "Content-Type": "application/json",
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request = Request(url, data=body, headers=headers, method=method)
    with urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def task_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("result") if isinstance(payload, dict) else None
    if not isinstance(result, dict):
        return {"provider_status": payload.get("status") if isinstance(payload, dict) else None}
    status_info = result.get("statusInfo") if isinstance(result.get("statusInfo"), dict) else {}
    return {
        "task_id": result.get("id"), "task_name": result.get("name"), "model": result.get("model"),
        "task_type": result.get("taskType"), "status": result.get("status"),
        "train_epochs": result.get("trainEpochs"), "learning_rate": result.get("learningRate"),
        "created_timestamp": result.get("createdDate"), "updated_timestamp": result.get("updatedDate"),
        "status_info": {key: status_info.get(key) for key in (
            "dataRows", "numOfTokens", "currStep", "totalTrainSteps", "currEpoch", "totalTrainEpochs",
            "estimatedTime", "trainLoss", "failureReason", "message", "endDatetime",
        )},
    }


def write_task_artifact(payload: dict[str, Any]) -> None:
    content = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    write_once_or_verify(TASK_ARTIFACT, content)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Required before Object Storage or CLOVA calls.")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    transport = make_transport_artifacts()
    prompt = json.loads(PROMPT.read_text(encoding="utf-8"))
    if prompt.get("prompt_sha256") != PROMPT_SHA256:
        raise RuntimeError("frozen generator prompt SHA-256 mismatch")
    if not args.execute:
        print(json.dumps({"preflight": "pass", "external_calls": 0, "transport": transport}, ensure_ascii=False))
        return 0
    if TASK_ARTIFACT.exists():
        raise SystemExit("refusing a second tuning task attempt: immutable task artifact already exists")
    from src.integrations.ncp_object_storage import NcpObjectStorageArtifacts, ObjectStorageSettings
    try:
        storage = NcpObjectStorageArtifacts(ObjectStorageSettings.from_env())
        object_key = f"tuning/p49-hcx005/{transport['transport_csv_sha256']}/p49_hcx005_training_export_ncp_transport_v1.csv"
        receipt = storage.upload_if_absent(TRANSPORT, object_key)
    except Exception as error:
        artifact = {
            "stage": "P49 HCX-005 tuning task creation", "outcome": "blocked_before_task_creation",
            "created_at": datetime.now(timezone.utc).isoformat(), "model": "HCX-005", "tuning_type": "PEFT",
            "prompt_sha256": PROMPT_SHA256, "dataset": transport,
            "object_storage": safe_failure("object_storage_upload", error), "secrets_recorded": False,
        }
        write_task_artifact(artifact)
        print(json.dumps({"outcome": artifact["outcome"], "object_storage": artifact["object_storage"]}, ensure_ascii=False))
        return 2
    api_key = os.getenv("HCX_API_KEY", "").strip()
    if not api_key:
        artifact = {
            "stage": "P49 HCX-005 tuning task creation", "outcome": "blocked_before_task_creation",
            "created_at": datetime.now(timezone.utc).isoformat(), "model": "HCX-005", "tuning_type": "PEFT",
            "prompt_sha256": PROMPT_SHA256, "dataset": transport,
            "object_storage": {"bucket": receipt.bucket, "key": receipt.key, "sha256": receipt.sha256, "size_bytes": receipt.size_bytes},
            "credential_blocker": "HCX_API_KEY missing", "secrets_recorded": False,
        }
        write_task_artifact(artifact)
        print(json.dumps({"outcome": artifact["outcome"], "credential_blocker": artifact["credential_blocker"]}, ensure_ascii=False))
        return 2
    submitted = {
        "name": "p49-hcx005-peft-600-v1", "model": "HCX-005", "tuningType": "PEFT",
        "trainEpochs": 8, "learningRate": 1.0e-4, "validationSplitRatio": 0.0, "loraR": 8, "loraAlpha": 64,
        "trainingDatasetFilePath": receipt.key, "trainingDatasetBucket": receipt.bucket,
        "trainingDatasetAccessKey": os.environ["NCP_ACCESS_KEY"], "trainingDatasetSecretKey": os.environ["NCP_SECRET_KEY"],
    }
    public_hyperparameters = {key: value for key, value in submitted.items() if "Key" not in key and key != "trainingDatasetFilePath" and key != "trainingDatasetBucket"}
    try:
        created = api_json("POST", TUNING_URL, api_key, submitted)
    except Exception as error:
        artifact = {
            "stage": "P49 HCX-005 tuning task creation", "outcome": "task_creation_failed",
            "created_at": datetime.now(timezone.utc).isoformat(), "model": "HCX-005", "tuning_type": "PEFT",
            "prompt_sha256": PROMPT_SHA256, "dataset": transport,
            "object_storage": {"bucket": receipt.bucket, "key": receipt.key, "sha256": receipt.sha256, "size_bytes": receipt.size_bytes},
            "submitted_hyperparameters": public_hyperparameters, "api_failure": safe_failure("create_tuning_task", error),
            "retry_count": 0, "secrets_recorded": False,
        }
        write_task_artifact(artifact)
        print(json.dumps({"outcome": artifact["outcome"], "api_failure": artifact["api_failure"]}, ensure_ascii=False))
        return 2
    snapshot = task_snapshot(created)
    task_id = snapshot.get("task_id")
    status_failure = None
    if task_id:
        try:
            snapshot["status_check"] = task_snapshot(api_json("GET", f"{TUNING_URL}/{task_id}", api_key))
        except Exception as error:
            status_failure = safe_failure("get_tuning_task", error)
    artifact = {
        "stage": "P49 HCX-005 tuning task creation", "outcome": "task_created",
        "created_at": datetime.now(timezone.utc).isoformat(), "model": "HCX-005", "tuning_type": "PEFT",
        "prompt_sha256": PROMPT_SHA256, "dataset": transport,
        "object_storage": {"bucket": receipt.bucket, "key": receipt.key, "sha256": receipt.sha256, "size_bytes": receipt.size_bytes},
        "submitted_hyperparameters": public_hyperparameters, "task": snapshot,
        "status_check_failure": status_failure, "retry_count": 0, "secrets_recorded": False,
    }
    write_task_artifact(artifact)
    print(json.dumps({"outcome": artifact["outcome"], "task": snapshot, "status_check_failure": status_failure}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
