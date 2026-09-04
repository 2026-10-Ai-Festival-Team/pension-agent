"""Run exactly three post-success endpoint smoke requests; this is not A/B/C."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.create_p49_hcx005_tuning_task import api_json, safe_failure, task_snapshot, write_once_or_verify

TASK_ID = "782y5g7f"
CSV_PATH = ROOT / "evaluation/fine_tuning/p49_hcx005_training_export_ncp_transport_v2.csv"
ARTIFACT = ROOT / "evaluation/fine_tuning/p49_hcx005_tuned_endpoint_smoke_v1.json"
OUTCOMES = ("supported_answer", "clarification_required", "bounded_answer")
ENDPOINT = f"https://clovastudio.stream.ntruss.com/v3/tasks/{TASK_ID}/chat-completions"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def response_content(payload: dict) -> str:
    result = payload.get("result", {}) if isinstance(payload, dict) else {}
    message = result.get("message", {}) if isinstance(result, dict) else {}
    content = message.get("content") or payload.get("message", {}).get("content")
    if not content and isinstance(payload.get("choices"), list) and payload["choices"]:
        content = payload["choices"][0].get("message", {}).get("content")
    return str(content or "")


def request_tuned(api_key: str, system_prompt: str, text: str) -> dict:
    body = json.dumps({
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": text}],
        "temperature": 0, "maxTokens": 1024,
    }, ensure_ascii=False).encode("utf-8")
    request = Request(ENDPOINT, data=body, headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
        "X-NCP-CLOVASTUDIO-REQUEST-ID": str(uuid4()),
    }, method="POST")
    with urlopen(request, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    load_dotenv(ROOT / ".env")
    if ARTIFACT.exists():
        raise SystemExit("smoke artifact already exists; refusing duplicate endpoint calls")
    status = task_snapshot(api_json("GET", f"https://clovastudio.stream.ntruss.com/tuning/v2/tasks/{TASK_ID}", os.environ["HCX_API_KEY"]))
    if status.get("status") != "SUCCEEDED":
        raise SystemExit("tuning task is not succeeded; endpoint smoke forbidden")
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    selected = []
    for outcome in OUTCOMES:
        marker = f"[결과 유형]\n{outcome}"
        row = next((item for item in rows if marker in item["Text"]), None)
        if row is None:
            raise RuntimeError(f"smoke source missing: {outcome}")
        selected.append((outcome, row))
    results = []
    for outcome, row in selected:
        try:
            payload = request_tuned(os.environ["HCX_API_KEY"], row["System_Prompt"], row["Text"])
            content = response_content(payload)
            results.append({
                "outcome": outcome, "c_id": row["C_ID"], "t_id": row["T_ID"], "provider_response": True,
                "response_sha256": sha(content), "response_chars": len(content),
                "answer_marker": "[답변]" in content, "evidence_marker": "[근거]" in content,
                "caution_marker": "[유의사항]" in content, "endpoint_schema_ok": bool(content),
            })
        except (HTTPError, URLError) as error:
            results.append({"outcome": outcome, "c_id": row["C_ID"], "t_id": row["T_ID"], "provider_response": False, "failure": safe_failure("tuned_endpoint_smoke", error)})
        except Exception as error:
            results.append({"outcome": outcome, "c_id": row["C_ID"], "t_id": row["T_ID"], "provider_response": False, "failure": {"exception_type": type(error).__name__}})
    artifact = {
        "stage": "P49 HCX-005 tuned endpoint smoke", "kind": "endpoint/provider/schema smoke only; not A/B/C",
        "task_id": TASK_ID, "task_status": status.get("status"), "logical_requests": 3,
        "outcomes": list(OUTCOMES), "results": results,
        "all_endpoint_schema_ok": all(item.get("endpoint_schema_ok") for item in results),
        "all_section_markers_ok": all(item.get("answer_marker") and item.get("evidence_marker") and item.get("caution_marker") for item in results),
        "secrets_recorded": False,
    }
    write_once_or_verify(ARTIFACT, (json.dumps(artifact, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({key: artifact[key] for key in ("task_id", "task_status", "logical_requests", "all_endpoint_schema_ok", "all_section_markers_ok")}, ensure_ascii=False))
    return 0 if artifact["all_endpoint_schema_ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
