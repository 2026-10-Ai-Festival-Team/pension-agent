"""P30-Live의 동결된 answer hash에 수동 semantic review를 결합한다."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# P27-E baseline과 같은 축을 유지한다. R-019는 호출하지 않은 정상
# information-limit handling이므로 semantic QA 분모와 strict useful에서는 제외한다.
REVIEW = {
    "R-011": ("correct", "full", "fully_supported", "n/a", True, None),
    "R-035": ("correct", "full", "fully_supported", "n/a", True, None),
    "R-038": ("partial", "partial", "partially_supported", "n/a", False, "requirement_omission"),
    "R-034": ("correct", "full", "fully_supported", "n/a", True, None),
    "R-019": ("not_evaluable", "missing", "unsupported", "correct", False, "policy_block"),
    "R-001": ("correct", "full", "fully_supported", "n/a", True, None),
    "R-002": ("correct", "full", "fully_supported", "n/a", True, None),
    "R-004": ("correct", "full", "fully_supported", "n/a", True, None),
    "R-008": ("correct", "full", "fully_supported", "n/a", True, None),
}


def main() -> None:
    source = ROOT / "evaluation/p30_live_semantic_candidate.jsonl"
    rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    actual_ids = {row["question_id"] for row in rows}
    if actual_ids != set(REVIEW):
        raise ValueError("P30-Live review IDs do not match the execution artifact")

    labels = []
    for row in rows:
        if hashlib.sha256(row["answer"].encode("utf-8")).hexdigest() != row["answer_hash"]:
            raise ValueError(f"answer hash mismatch: {row['question_id']}")
        semantic, coverage, grounding, policy, useful, reason = REVIEW[row["question_id"]]
        labels.append(
            {
                "question_id": row["question_id"],
                "role": row["role"],
                "answer_hash": row["answer_hash"],
                "semantic_correctness": semantic,
                "requirement_coverage": coverage,
                "grounding": grounding,
                "policy_behavior": policy,
                "strict_useful": useful,
                "failure_reason": reason,
            }
        )
    target = [item for item in labels if item["role"] == "target"]
    controls = [item for item in labels if item["role"] == "control"]
    blocked = next(item for item in labels if item["role"] == "fail_closed_control")
    payload = {
        "dataset": "P30 limited HCX semantic review; labels bind to the recorded answer hash",
        "source_execution": "evaluation/p30_live_semantic_candidate.jsonl",
        "labels": labels,
        "summary": {
            "target_strict_useful": f"{sum(item['strict_useful'] for item in target)}/{len(target)}",
            "control_strict_useful": f"{sum(item['strict_useful'] for item in controls)}/{len(controls)}",
            "fail_closed_control_policy_correct": blocked["policy_behavior"] == "correct",
            "p27e_target_baseline_strict_useful": "0/4",
            "target_strict_useful_delta": f"+{sum(item['strict_useful'] for item in target)}",
        },
    }
    label_path = ROOT / "evaluation/p30_live_semantic_labels.json"
    label_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    report = "\n".join(
        [
            "# P30-Live: Limited HCX Semantic Reevaluation",
            "",
            "## Fixed conditions",
            "",
            "- P30 requirement planner and product-field boundary",
            "- HCX-007 Native Structured Outputs, thinking none, 6-second pacing",
            "- strict parser, strict citation validator, Financial Policy",
            "- no prompt, retrieval, workflow, or validator tuning",
            "",
            "## Execution contract",
            "",
            "- HCX attempted: 8/8 eligible cases",
            "- JSON/schema success: 8/8",
            "- Citation validation: 8/8",
            "- Provider 429 / 5xx: 0 / 0",
            "- R-019: HCX not called; DC-specific detailed statutory grounds were not sufficiently isolated from IRP-only evidence.",
            "",
            "## Semantic labels",
            "",
            "| ID | Role | Correctness | Coverage | Grounding | Strict useful |",
            "|---|---|---|---|---|---:|",
            *[
                f"| {item['question_id']} | {item['role']} | {item['semantic_correctness']} | "
                f"{item['requirement_coverage']} | {item['grounding']} | "
                f"{'yes' if item['strict_useful'] else 'no'} |"
                for item in labels
            ],
            "",
            "## P30 target delta",
            "",
            "- P27-E target baseline: 0/4 strict useful (`R-011`, `R-034`, `R-035`, `R-038`).",
            f"- P30-Live target result: {payload['summary']['target_strict_useful']} strict useful.",
            "- Improved: R-011 (IRP 이전 과세 시점), R-034 (총보수와 투자대상), R-035 (주요 투자 위험).",
            "- Remaining: R-038은 법정사유는 제시했지만 계정 유형별 적용 범위를 구분하지 않아 partial로 유지한다.",
            "",
            "## Decision",
            "",
            "**P30-Live Go.** P30 requirement slots improved the limited target set without control regression, provider failure, schema failure, or citation regression. This is a small semantic result only; Full-40 candidate execution is a separate decision.",
            "",
        ]
    )
    (ROOT / "docs/p30_live_semantic_reevaluation.md").write_text(report, encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
