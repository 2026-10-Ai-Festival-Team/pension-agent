"""Emit a Git-safe summary of P22/P23 fixed-pacing smoke artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    runs = []
    for path in args.inputs:
        payload = json.loads(path.read_text(encoding="utf-8"))
        runs.append(
            {
                "artifact": path.name,
                "phase": payload["phase"],
                "minimum_interval_seconds": payload["settings"]["minimum_interval_seconds"],
                "question_count": len(payload["question_ids"]),
                "duration_ms": payload["duration_ms"],
                "observed_minimum_start_delta_ms": payload["spacing"]["observed_minimum_start_delta_ms"],
                "spacing_policy_satisfied": payload["spacing"]["spacing_policy_satisfied"],
                "http_429": payload["http_429"],
                "retry_after_seen": payload["retry_after_seen"],
                "full_run_permitted": payload["full_run_permitted"],
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"runs": runs}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"runs": runs}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
