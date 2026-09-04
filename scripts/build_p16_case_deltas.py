"""P16 두 실제 run과 answer-hash별 semantic review를 질문 단위로 비교한다."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _packet_by_id(path: Path) -> dict[str, dict]:
    return {
        item["question_id"]: item
        for item in (
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }


def _strict(item: dict) -> bool | None:
    if item["review_eligibility"] != "generated_answer":
        return None
    return all(
        item["review"][field] == "pass"
        for field in ("factual_correctness", "requirement_coverage", "evidence_grounding")
    )


def _label(item: dict) -> str:
    strict = _strict(item)
    if strict is True:
        return "strict_useful"
    if strict is False:
        return "semantic_error"
    return item["review_eligibility"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-run", type=Path, required=True)
    parser.add_argument("--shadow-run", type=Path, required=True)
    parser.add_argument("--baseline-review", type=Path, required=True)
    parser.add_argument("--shadow-review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    baseline_rows = {row["question_id"]: row for row in json.loads(args.baseline_run.read_text(encoding="utf-8"))["rows"]}
    shadow_rows = {row["question_id"]: row for row in json.loads(args.shadow_run.read_text(encoding="utf-8"))["rows"]}
    baseline_review = _packet_by_id(args.baseline_review)
    shadow_review = _packet_by_id(args.shadow_review)
    if set(baseline_rows) != set(shadow_rows) or set(baseline_rows) != set(baseline_review) or set(baseline_rows) != set(shadow_review):
        raise ValueError("P16 inputs must contain the same question IDs")
    rows = []
    for question_id in sorted(baseline_rows):
        before, after = baseline_rows[question_id], shadow_rows[question_id]
        before_label, after_label = _label(baseline_review[question_id]), _label(shadow_review[question_id])
        before_strict, after_strict = _strict(baseline_review[question_id]), _strict(shadow_review[question_id])
        delta = (
            "improved" if after_strict is True and before_strict is not True
            else "regressed" if before_strict is True and after_strict is not True
            else "same"
        )
        rows.append(
            {
                "question_id": question_id,
                "baseline_outcome": before.get("failure_stage"),
                "shadow_outcome": after.get("failure_stage"),
                "baseline_semantic_label": before_label,
                "shadow_semantic_label": after_label,
                "route": after.get("route"),
                "evidence_difference": {
                    "baseline": before.get("retrieved_chunk_ids", []),
                    "shadow": after.get("retrieved_chunk_ids", []),
                },
                "citation_difference": {
                    "baseline": before.get("cited_chunk_ids", []),
                    "shadow": after.get("cited_chunk_ids", []),
                },
                "latency_difference_ms": round(after["elapsed_ms"] - before["elapsed_ms"], 3),
                "delta": delta,
                "primary_reason": after.get("evidence_reason") if after.get("failure_stage") == "evidence_rejection" else after_label,
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


if __name__ == "__main__":
    main()
