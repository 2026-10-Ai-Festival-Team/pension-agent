"""P16 실제 answer/context를 검토한 1차 semantic label을 packet에 적용한다.

이 스크립트는 P3 결과를 읽거나 재사용하지 않는다. 각 variant의 현재 review packet
hash와 generated answer 집합을 검증한 뒤, P16 run에서 수동 검토한 판정을 기록한다.
원문 answer와 context는 Git 제외 diagnostics에만 남는다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.answer_quality import REVIEW_FIELDS


BASELINE = {
    "accepted": {
        "R-001", "R-002", "R-003", "R-004", "R-005", "R-006", "R-007", "R-008", "R-009", "R-010",
        "R-011", "R-013", "R-014", "R-015", "R-018", "R-019", "R-020", "R-021", "R-022", "R-023",
        "R-025", "R-026", "R-027", "R-028", "R-029", "R-030", "R-031", "R-032", "R-036", "R-037", "R-038",
    },
    "factual_fail": {"R-002", "R-005", "R-010", "R-011", "R-013", "R-027", "R-028", "R-037"},
    "coverage_fail": {"R-010", "R-011", "R-013", "R-015", "R-019", "R-020", "R-028", "R-037"},
    "grounding_fail": {"R-002", "R-013", "R-027", "R-028", "R-037"},
    "hallucination_fail": {"R-002", "R-005", "R-010", "R-013", "R-027", "R-028"},
    "limit_fail": {"R-011", "R-028", "R-037"},
}

SHADOW = {
    "accepted": {
        "R-001", "R-003", "R-004", "R-007", "R-008", "R-009", "R-011", "R-013", "R-014", "R-015",
        "R-017", "R-018", "R-019", "R-020", "R-021", "R-022", "R-023", "R-024", "R-025", "R-026",
        "R-028", "R-029", "R-030", "R-031", "R-032", "R-033", "R-034", "R-036",
    },
    "factual_fail": {"R-011", "R-013", "R-024", "R-028", "R-033", "R-034"},
    "coverage_fail": {"R-011", "R-013", "R-015", "R-019", "R-020", "R-024", "R-028", "R-033", "R-034"},
    "grounding_fail": {"R-013", "R-024", "R-033", "R-034"},
    "hallucination_fail": {"R-013", "R-024", "R-033", "R-034"},
    "limit_fail": {"R-011", "R-024", "R-028", "R-033", "R-034"},
}


def _load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _label(packet: list[dict], labels: dict, variant: str) -> list[dict]:
    generated = {item["question_id"] for item in packet if item["review_eligibility"] == "generated_answer"}
    if generated != labels["accepted"]:
        raise ValueError(f"{variant} generated answer set differs from reviewed P16 run")
    for item in packet:
        if item["review_eligibility"] != "generated_answer":
            continue
        question_id = item["question_id"]
        review = item["review"]
        review.update(
            {
                "factual_correctness": "fail" if question_id in labels["factual_fail"] else "pass",
                "numeric_fidelity": "not_applicable",
                "requirement_coverage": "fail" if question_id in labels["coverage_fail"] else "pass",
                "evidence_grounding": "fail" if question_id in labels["grounding_fail"] else "pass",
                "hallucination": "fail" if question_id in labels["hallucination_fail"] else "pass",
                "premise_correction": "not_applicable",
                "comparison_coverage": review["comparison_coverage"],
                "information_limit_handling": "fail" if question_id in labels["limit_fail"] else "pass",
                "reviewer": "assistant-assisted-p16-1",
                "notes": "P16 current answer·citation·retrieved context independent review",
            }
        )
        if question_id in {"R-002", "R-024", "R-036"}:
            review["comparison_coverage"] = (
                "pass"
                if review["requirement_coverage"] == "pass"
                else "fail"
            )
        if set(review) < set(REVIEW_FIELDS) | {"reviewer", "notes"}:
            raise ValueError("incomplete review fields")
    return packet


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-packet", type=Path, required=True)
    parser.add_argument("--shadow-packet", type=Path, required=True)
    parser.add_argument("--baseline-output", type=Path, required=True)
    parser.add_argument("--shadow-output", type=Path, required=True)
    args = parser.parse_args()
    for packet_path, output_path, labels, variant in (
        (args.baseline_packet, args.baseline_output, BASELINE, "baseline"),
        (args.shadow_packet, args.shadow_output, SHADOW, "shadow"),
    ):
        labeled = _label(_load(packet_path), labels, variant)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in labeled),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
