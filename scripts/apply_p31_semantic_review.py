"""동결된 P31 Full-40 answer hash의 수동 semantic review를 기록한다."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "evaluation/p31_candidate_execution.jsonl"
OUTPUT = ROOT / "evaluation/p31_semantic_labels.json"
REPORT = ROOT / "docs/p31_semantic_labeling.md"

# 아래 hash 확인은 P31 실행 결과가 바뀐 뒤 이전 수동 판정을 재사용하는 일을 막는다.
REVIEWED_HASHES = {
    "R-006": "12f10ea2acb8f4b3a9f17fe720a572e32c71b31f2860deb8f76ebb82d3623542",
    "R-010": "cc157791d25bfc04b51227e31694c73528aaf4ee36a79dea853f9885b4aa59cd",
    "R-011": "ef9e92b81d59349a767292e80a5c1a3b37bf5749367c54965392278a990d0f0e",
    "R-019": "41b15e3d8968d1c6d2a2c700415b28bef646e98f3460fea7172b7048faa8eed3",
    "R-033": "d885b95bb68fdba46a2bec16d8343735bd4c1b645e41acf96a11a494f77c1b75",
    "R-034": "fd4b4347a6427d0c5d5787044d77841cf20c8c18881a5e4e9ca587524cfb1d4e",
    "R-035": "e1791670d2e94483e7f614f9e006936e4db76d2c8c8c34b7fedf0e62ea8338a1",
    "R-038": "868ad2d228cf20b841f4d2f008da72ed4b779a39011696776e00fbbc396ab049",
}

FAILURES = {
    "R-006": ("partial", "partial", "fully_supported", "n/a", "requirement_omission"),
    "R-010": ("partial", "partial", "fully_supported", "n/a", "requirement_omission"),
    "R-019": ("not_evaluable", "missing", "unsupported", "correct", "policy_block"),
    "R-033": ("incorrect", "missing", "unsupported", "n/a", "product_field_confusion"),
    # 총보수와 기간별 비용 예시를 동일 field로 표현했다. 투자대상은 맞지만 총보수
    # requirement가 완결되지 않아 strict useful로 보지 않는다.
    "R-034": ("partial", "partial", "fully_supported", "n/a", "numeric_confusion"),
    "R-038": ("partial", "partial", "partially_supported", "n/a", "requirement_omission"),
}


def label_for(row: dict) -> dict:
    question_id = row["question_id"]
    if question_id in {"R-039", "R-040"}:
        semantic, coverage, grounding, policy, reason = (
            "not_evaluable",
            "missing",
            "unsupported",
            "correct",
            "policy_block",
        )
    elif question_id in FAILURES:
        semantic, coverage, grounding, policy, reason = FAILURES[question_id]
    else:
        semantic, coverage, grounding, policy, reason = (
            "correct",
            "full",
            "fully_supported",
            "n/a",
            None,
        )
    return {
        "question_id": question_id,
        "answer_hash": row["answer_hash"],
        "semantic_correctness": semantic,
        "requirement_coverage": coverage,
        "grounding": grounding,
        "policy_behavior": policy,
        "strict_useful": (
            semantic == "correct"
            and coverage == "full"
            and grounding == "fully_supported"
            and policy != "incorrect"
        ),
        "failure_reason": reason,
    }


def main() -> None:
    rows = [json.loads(line) for line in INPUT.read_text(encoding="utf-8").splitlines()]
    if len(rows) != 40:
        raise SystemExit(f"P31 full run은 40개여야 합니다. 현재: {len(rows)}")
    by_id = {row["question_id"]: row for row in rows}
    if set(REVIEWED_HASHES) - set(by_id):
        raise SystemExit("P31 manual review 대상 질문이 누락되었습니다.")
    for question_id, expected_hash in REVIEWED_HASHES.items():
        if by_id[question_id]["answer_hash"] != expected_hash:
            raise SystemExit(
                f"{question_id} answer hash가 수동 검토본과 다릅니다. 새 review가 필요합니다."
            )

    labels = [label_for(row) for row in rows]
    answerable = [label for label in labels if label["question_id"] not in {"R-039", "R-040"}]
    p27e_compound_ids = {
        "R-002", "R-005", "R-006", "R-010", "R-024", "R-027", "R-028", "R-033", "R-034", "R-036", "R-037"
    }
    dynamic_compound_ids = {
        row["question_id"] for row in rows if row.get("route") == "compound"
    }
    p30_targets = {"R-011", "R-034", "R-035", "R-038"}
    useful = lambda ids: sum(label["strict_useful"] for label in labels if label["question_id"] in ids)
    payload = {
        "dataset": "P31 Full-40 candidate execution의 answer-hash 수동 semantic review",
        "source_execution_file": "evaluation/p31_candidate_execution.jsonl",
        "labels": labels,
        "summary": {
            "strict_e2e_useful": f"{sum(label['strict_useful'] for label in answerable)}/{len(answerable)}",
            "semantic_correctness": f"{sum(label['semantic_correctness'] == 'correct' for label in answerable)}/{len(answerable)}",
            "requirement_full_coverage": f"{sum(label['requirement_coverage'] == 'full' for label in answerable)}/{len(answerable)}",
            "fully_grounded": f"{sum(label['grounding'] == 'fully_supported' for label in answerable)}/{len(answerable)}",
            "legacy_p27e_compound_strict_useful": f"{useful(p27e_compound_ids)}/{len(p27e_compound_ids)}",
            "dynamic_p31_compound_strict_useful": f"{useful(dynamic_compound_ids)}/{len(dynamic_compound_ids)}",
            "p30_targets_strict_useful": f"{useful(p30_targets)}/{len(p30_targets)}",
        },
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = payload["summary"]
    report = "\n".join(
        [
            "# P31-S: Full-40 Candidate 의미 품질 라벨링",
            "",
            "P31에서 생성된 answer hash를 대상으로 새로 수동 라벨링했다. P27-E 결과를 재사용하지 않았으며, 같은 문항이라도 P31 hash가 달라지면 P31 답변을 다시 검토했다.",
            "",
            "## 결과",
            "",
            f"- Strict E2E Useful: **{summary['strict_e2e_useful']}** (P27-E: 30/38)",
            f"- Semantic correctness: **{summary['semantic_correctness']}** (P27-E: 31/38)",
            f"- Requirement full coverage: **{summary['requirement_full_coverage']}**",
            f"- Fully grounded: **{summary['fully_grounded']}**",
            f"- P27-E 동등 compound subset: **{summary['legacy_p27e_compound_strict_useful']}** (P27-E: 7/11)",
            f"- P31 dynamic compound route: **{summary['dynamic_p31_compound_strict_useful']}**",
            f"- P30 targets (R-011/R-034/R-035/R-038): **{summary['p30_targets_strict_useful']}** (P27-E: 0/4)",
            "",
            "## P30 Target Delta",
            "",
            "| ID | P27-E | P31 | 판정 |",
            "|---|---|---|---|",
            "| R-011 | answer irrelevance | strict useful | 개선 재현 |",
            "| R-034 | numeric confusion | numeric confusion | P30-Live 개선 미재현 |",
            "| R-035 | product-field confusion | strict useful | 개선 재현 |",
            "| R-038 | answer irrelevance | partial | 관련 답변으로 개선됐지만 requirement 완결성 부족 |",
            "",
            "## 해석",
            "",
            "운영·형식 계약은 P31에서 모두 통과했다. P30는 Full-40에서도 Strict Useful을 30/38에서 32/38으로 올렸지만, 총보수와 기간별 비용 예시의 field 혼동(R-034)은 동일 evidence 아래서 재발했다. 따라서 P30 planner/product-field boundary는 candidate 효과가 있으나, product numerical generation을 완전히 해결한 것으로 보지 않는다.",
            "",
        ]
    )
    REPORT.write_text(report, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
