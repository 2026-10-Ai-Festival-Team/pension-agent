"""One allowed retry after v4's provider-reported task-name format failure."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.create_p49_hcx005_tuning_task import PROMPT_SHA256, TUNING_URL, api_json, digest, safe_failure, task_snapshot, write_once_or_verify

TRANSPORT = ROOT / "evaluation/fine_tuning/p49_hcx005_training_export_ncp_transport_v2.csv"
TASK_ARTIFACT = ROOT / "evaluation/fine_tuning/p49_hcx005_tuning_task_v5.json"
V4_ARTIFACT = ROOT / "evaluation/fine_tuning/p49_hcx005_tuning_task_v4.json"
BUCKET = "pension-agent"
PATH = "tuning/p49-hcx005/p49_hcx005_training_export_ncp_transport_v2.csv"
HASH = "595ae54200a6226ba50df81ded1f7f29ae6a85e514563625a47d3baf03326462"


def record(payload: dict) -> None:
    write_once_or_verify(TASK_ARTIFACT, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def main() -> int:
    load_dotenv(ROOT / ".env")
    v4 = json.loads(V4_ARTIFACT.read_text(encoding="utf-8"))
    if v4.get("failure", {}).get("provider_message") != "Invalid parameter: name" or TASK_ARTIFACT.exists():
        raise SystemExit("v5 retry is authorized only once after the recorded v4 name failure")
    if digest(TRANSPORT.read_bytes()) != HASH:
        raise RuntimeError("frozen v2 transport hash mismatch")
    payload = {
        "name": "p49-hcx005-peft-600-v2", "model": "HCX-005", "tuningType": "PEFT",
        "trainEpochs": 8, "learningRate": 1.0e-4, "validationSplitRatio": 0.0, "loraR": 8, "loraAlpha": 64,
        "trainingDatasetFilePath": PATH, "trainingDatasetBucket": BUCKET,
        "trainingDatasetAccessKey": os.environ["NCP_ACCESS_KEY"], "trainingDatasetSecretKey": os.environ["NCP_SECRET_KEY"],
    }
    public = {key: value for key, value in payload.items() if key not in {"trainingDatasetFilePath", "trainingDatasetBucket", "trainingDatasetAccessKey", "trainingDatasetSecretKey"}}
    authority = {"bucket": BUCKET, "path": PATH, "local_sha256": HASH, "prompt_sha256": PROMPT_SHA256, "payload_changed": False}
    try:
        created = api_json("POST", TUNING_URL, os.environ["HCX_API_KEY"], payload)
    except Exception as error:
        artifact = {"stage": "P49 HCX-005 v5 name-only retry", "outcome": "task_creation_failed", "created_at": datetime.now(timezone.utc).isoformat(), "model": "HCX-005", "tuning_type": "PEFT", "dataset": authority, "submitted_hyperparameters": public, "prior_failure": {"task_artifact": V4_ARTIFACT.name, "message": "Invalid parameter: name"}, "failure": safe_failure("create_tuning_task", error), "retry_count": 1, "secrets_recorded": False}
        record(artifact); print(json.dumps({"outcome": artifact["outcome"], "failure": artifact["failure"]}, ensure_ascii=False)); return 2
    task = task_snapshot(created); status_failure = None
    if task.get("task_id"):
        try:
            task["status_check"] = task_snapshot(api_json("GET", f"{TUNING_URL}/{task['task_id']}", os.environ["HCX_API_KEY"]))
        except Exception as error:
            status_failure = safe_failure("get_tuning_task", error)
    artifact = {"stage": "P49 HCX-005 v5 name-only retry", "outcome": "task_created", "created_at": datetime.now(timezone.utc).isoformat(), "model": "HCX-005", "tuning_type": "PEFT", "dataset": authority, "submitted_hyperparameters": public, "prior_failure": {"task_artifact": V4_ARTIFACT.name, "message": "Invalid parameter: name"}, "task": task, "status_check_failure": status_failure, "retry_count": 1, "secrets_recorded": False}
    record(artifact); print(json.dumps({"outcome": artifact["outcome"], "task": task, "status_check_failure": status_failure}, ensure_ascii=False)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
