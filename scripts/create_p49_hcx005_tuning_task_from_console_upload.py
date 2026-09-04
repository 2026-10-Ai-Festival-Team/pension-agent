"""Create one P49 HCX-005 PEFT task from the user-confirmed console upload."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.create_p49_hcx005_tuning_task import (
    PROMPT_SHA256, TRANSPORT, TUNING_URL, api_json, digest, make_transport_artifacts,
    safe_failure, task_snapshot, write_once_or_verify,
)

TASK_ARTIFACT = ROOT / "evaluation/fine_tuning/p49_hcx005_tuning_task_v3.json"
CONSOLE_BUCKET = "pension-agent"
CONSOLE_PATH = "tuning/p49-hcx005/p49_hcx005_training_export_ncp_transport_v1.csv"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Required before POST/GET tuning API calls.")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    transport = make_transport_artifacts()
    if transport["transport_csv_sha256"] != digest(TRANSPORT.read_bytes()):
        raise RuntimeError("local frozen transport hash mismatch")
    if not args.execute:
        print(json.dumps({"external_calls": 0, "bucket": CONSOLE_BUCKET, "path": CONSOLE_PATH}, ensure_ascii=False))
        return 0
    if TASK_ARTIFACT.exists():
        raise SystemExit("refusing a second console-upload task attempt")
    for name in ("HCX_API_KEY", "NCP_ACCESS_KEY", "NCP_SECRET_KEY"):
        if not os.getenv(name, "").strip():
            raise SystemExit(f"required credential missing: {name}")

    submitted = {
        "name": "p49-hcx005-peft-600-v1", "model": "HCX-005", "tuningType": "PEFT",
        "trainEpochs": 8, "learningRate": 1.0e-4, "validationSplitRatio": 0.0, "loraR": 8, "loraAlpha": 64,
        "trainingDatasetFilePath": CONSOLE_PATH, "trainingDatasetBucket": CONSOLE_BUCKET,
        "trainingDatasetAccessKey": os.environ["NCP_ACCESS_KEY"], "trainingDatasetSecretKey": os.environ["NCP_SECRET_KEY"],
    }
    public_hyperparameters = {key: value for key, value in submitted.items() if key not in {
        "trainingDatasetFilePath", "trainingDatasetBucket", "trainingDatasetAccessKey", "trainingDatasetSecretKey",
    }}
    console_upload = {
        "bucket": CONSOLE_BUCKET, "path": CONSOLE_PATH, "console_observed_size": "1.82MB",
        "local_transport_csv": TRANSPORT.name, "local_transport_sha256": transport["transport_csv_sha256"],
        "local_model_visible_payload_sha256": transport["model_visible_payload_sha256"],
        "payload_changed": False,
    }
    try:
        created = api_json("POST", TUNING_URL, os.environ["HCX_API_KEY"], submitted)
    except Exception as error:
        artifact = {
            "stage": "P49 HCX-005 console-upload task creation", "outcome": "task_creation_failed",
            "created_at": datetime.now(timezone.utc).isoformat(), "model": "HCX-005", "tuning_type": "PEFT",
            "prompt_sha256": PROMPT_SHA256, "console_upload": console_upload,
            "submitted_hyperparameters": public_hyperparameters, "failure": safe_failure("create_tuning_task", error),
            "retry_count": 0, "secrets_recorded": False,
        }
        write_once_or_verify(TASK_ARTIFACT, (json.dumps(artifact, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
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
        "stage": "P49 HCX-005 console-upload task creation", "outcome": "task_created",
        "created_at": datetime.now(timezone.utc).isoformat(), "model": "HCX-005", "tuning_type": "PEFT",
        "prompt_sha256": PROMPT_SHA256, "console_upload": console_upload,
        "submitted_hyperparameters": public_hyperparameters, "task": task,
        "status_check_failure": status_failure, "retry_count": 0, "secrets_recorded": False,
    }
    write_once_or_verify(TASK_ARTIFACT, (json.dumps(artifact, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"outcome": artifact["outcome"], "task": task, "status_check_failure": status_failure}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
