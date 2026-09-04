"""P16 baseline/shadow 1차 semantic review를 같은 정의로 집계한다."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _summary(packet: list[dict]) -> dict:
    generated = [item for item in packet if item["review_eligibility"] == "generated_answer"]
    strict = [
        item
        for item in generated
        if all(item["review"][field] == "pass" for field in ("factual_correctness", "requirement_coverage", "evidence_grounding"))
    ]
    compound_ids = {"R-002", "R-005", "R-006", "R-010", "R-024", "R-027", "R-028", "R-033", "R-034", "R-036", "R-037"}
    compound = [item for item in generated if item["question_id"] in compound_ids]
    return {
        "accepted_answer_count": len(generated),
        "semantic_correctness": sum(item["review"]["factual_correctness"] == "pass" for item in generated),
        "full_requirement_coverage": sum(item["review"]["requirement_coverage"] == "pass" for item in generated),
        "fully_grounded": sum(item["review"]["evidence_grounding"] == "pass" for item in generated),
        "strict_useful_answer_count": len(strict),
        "strict_e2e_useful_answer_rate": round(len(strict) / 38, 3),
        "compound": {
            "accepted": len(compound),
            "semantic_correctness": sum(item["review"]["factual_correctness"] == "pass" for item in compound),
            "full_requirement_coverage": sum(item["review"]["requirement_coverage"] == "pass" for item in compound),
            "fully_grounded": sum(item["review"]["evidence_grounding"] == "pass" for item in compound),
            "strict_useful": sum(
                all(item["review"][field] == "pass" for field in ("factual_correctness", "requirement_coverage", "evidence_grounding"))
                for item in compound
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--shadow", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = {"baseline": _summary(_load(args.baseline)), "shadow": _summary(_load(args.shadow))}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
