"""Create the one permitted post-T_ID-repair HCX-005 PEFT task."""
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
from scripts.create_p49_hcx005_tuning_task import PROMPT_SHA256, TUNING_URL, api_json, digest, safe_failure, task_snapshot, write_once_or_verify

TRANSPORT = ROOT / "evaluation/fine_tuning/p49_hcx005_training_export_ncp_transport_v2.csv"
TRANSPORT_MANIFEST = ROOT / "evaluation/fine_tuning/p49_hcx005_training_export_ncp_transport_manifest_v2.json"
TASK_ARTIFACT = ROOT / "evaluation/fine_tuning/p49_hcx005_tuning_task_v4.json"
BUCKET = "pension-agent"
PATH = "tuning/p49-hcx005/p49_hcx005_training_export_ncp_transport_v2.csv"
EXPECTED_HASH = "595ae54200a6226ba50df81ded1f7f29ae6a85e514563625a47d3baf03326462"


def write_artifact(payload: dict) -> None:
    write_once_or_verify(TASK_ARTIFACT, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    manifest = json.loads(TRANSPORT_MANIFEST.read_text(encoding="utf-8"))
    if not manifest.get("transport_repair_go") or digest(TRANSPORT.read_bytes()) != EXPECTED_HASH:
        raise RuntimeError("T_ID-repaired frozen transport integrity failed")
    if not args.execute:
        print(json.dumps({"external_calls": 0, "path": PATH, "sha256": EXPECTED_HASH}, ensure_ascii=False)); return 0
    if TASK_ARTIFACT.exists():
        raise SystemExit("refusing a second v4 task creation attempt")
    for name in ("HCX_API_KEY", "NCP_ACCESS_KEY", "NCP_SECRET_KEY"):
        if not os.getenv(name, "").strip():
            raise SystemExit(f"required credential missing: {name}")
    submitted = {
        "name": "p49-hcx005-peft-600-v2-singleturn", "model": "HCX-005", "tuningType": "PEFT",
        "trainEpochs": 8, "learningRate": 1.0e-4, "validationSplitRatio": 0.0, "loraR": 8, "loraAlpha": 64,
        "trainingDatasetFilePath": PATH, "trainingDatasetBucket": BUCKET,
        "trainingDatasetAccessKey": os.environ["NCP_ACCESS_KEY"], "trainingDatasetSecretKey": os.environ["NCP_SECRET_KEY"],
    }
    public_hparams = {key: value for key, value in submitted.items() if key not in {
        "trainingDatasetFilePath", "trainingDatasetBucket", "trainingDatasetAccessKey", "trainingDatasetSecretKey",
    }}
    upload = {"bucket": BUCKET, "path": PATH, "local_sha256": EXPECTED_HASH, "repair_manifest": TRANSPORT_MANIFEST.name, "payload_changed": False}
    try:
        created = api_json("POST", TUNING_URL, os.environ["HCX_API_KEY"], submitted)
    except Exception as error:
        artifact = {"stage": "P49 HCX-005 T_ID-repaired task creation", "outcome": "task_creation_failed", "created_at": datetime.now(timezone.utc).isoformat(), "model": "HCX-005", "tuning_type": "PEFT", "prompt_sha256": PROMPT_SHA256, "console_upload": upload, "submitted_hyperparameters": public_hparams, "failure": safe_failure("create_tuning_task", error), "retry_count": 0, "secrets_recorded": False}
        write_artifact(artifact); print(json.dumps({"outcome": artifact["outcome"], "failure": artifact["failure"]}, ensure_ascii=False)); return 2
    task = task_snapshot(created); status_failure = None
    if task.get("task_id"):
        try:
            task["status_check"] = task_snapshot(api_json("GET", f"{TUNING_URL}/{task['task_id']}", os.environ["HCX_API_KEY"]))
        except Exception as error:
            status_failure = safe_failure("get_tuning_task", error)
    artifact = {"stage": "P49 HCX-005 T_ID-repaired task creation", "outcome": "task_created", "created_at": datetime.now(timezone.utc).isoformat(), "model": "HCX-005", "tuning_type": "PEFT", "prompt_sha256": PROMPT_SHA256, "console_upload": upload, "submitted_hyperparameters": public_hparams, "task": task, "status_check_failure": status_failure, "retry_count": 0, "secrets_recorded": False}
    write_artifact(artifact); print(json.dumps({"outcome": artifact["outcome"], "task": task, "status_check_failure": status_failure}, ensure_ascii=False)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
