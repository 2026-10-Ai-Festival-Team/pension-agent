"""CSV/JSON 평가 문항을 namespaced specification question bank로 정규화한다.

이 도구는 평가 문항을 학습 데이터로 만들지 않는다. 원본에서 제공한
행동 정책·근거·정답 rubric을 보존하여 planner/retrieval/gate/policy/E2E
검증의 공통 입력으로 만든다.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _parse_behavior(value: str | list[str]) -> list[str]:
    """CSV의 JSON-encoded 행동값과 JSON의 행동값을 같은 list로 보존한다."""
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return [value]
    return parsed if isinstance(parsed, list) else [parsed]


def _source_paths(value: str) -> list[str]:
    """CSV의 제출 폴더 접두어를 제거한 corpus-relative path 목록."""
    paths = []
    for source in value.split("|"):
        source = source.strip()
        if source:
            paths.append(source.removeprefix("2.연금/"))
    return paths


def _default_dimensions(expected_behavior: list[str]) -> list[str]:
    if any(action in {"clarify", "safe_response", "insufficient_information", "abstain"} for action in expected_behavior):
        return ["policy_behavior", "information_limit_handling", "safety_reliability"]
    return ["accuracy", "evidence_completeness", "groundedness", "requirement_coverage"]


def _record_from_csv(row: dict[str, str]) -> dict[str, Any]:
    expected_behavior = _parse_behavior(row["expected_behavior"])
    source_paths = _source_paths(row["source_files"])
    expected_source_paths = _source_paths(row["expected_source_files"])
    gold_answer = row["gold_answer"].strip()
    return {
        "id": f"CSV-{row['question_id']}",
        "source_set": "eval_questions_final_csv",
        "source_item_id": row["question_id"],
        "question": row["question"],
        "topic": row["topic"],
        "subtype": row["subtype"],
        "difficulty": row["difficulty"],
        "question_format": row["question_format"],
        "expected_behavior": expected_behavior,
        "requirements": [{"kind": "gold_answer_rubric", "text": gold_answer}] if gold_answer else [],
        "planner_slot_status": "needs_annotation",
        "gold_answer_points": [],
        "gold_answer": gold_answer,
        "required_evidence": [],
        "source_paths": source_paths,
        "expected_source_paths": expected_source_paths,
        "forbidden_claims": [],
        "required_clarifications": [],
        "evaluation_dimensions": [part.strip() for part in row["evaluation_dimensions"].split("|") if part.strip()],
        "fixtures": {
            "planner": {"expected_slots": [], "status": "needs_annotation"},
            "retrieval": {"required_evidence": [], "expected_source_paths": expected_source_paths},
            "gate_policy": {"expected_behavior": expected_behavior},
            "generation": {"gold_answer_points": [], "gold_answer": gold_answer, "forbidden_claims": []},
            "grounding": {"expected_source_paths": expected_source_paths},
        },
    }


def _record_from_json(row: dict[str, Any]) -> dict[str, Any]:
    expected_behavior = _parse_behavior(row["expected_behavior"])
    gold_points = list(row.get("gold_answer_points", []))
    required_evidence = list(row.get("required_evidence", []))
    clarifications = list(row.get("required_clarifications", []))
    requirements = [
        {"kind": "gold_answer_point", "text": point} for point in gold_points
    ] + [
        {"kind": "required_clarification", "text": item} for item in clarifications
    ]
    return {
        "id": f"JSON-{row['id']}",
        "source_set": "eval_questions_json",
        "source_item_id": row["id"],
        "question": row["question"],
        "topic": row["category"],
        "subtype": row["subcategory"],
        "difficulty": row["difficulty"],
        "question_format": row["question_type"],
        "expected_behavior": expected_behavior,
        "requirements": requirements,
        "planner_slot_status": "needs_annotation",
        "gold_answer_points": gold_points,
        "gold_answer": None,
        "required_evidence": required_evidence,
        "source_paths": [],
        "expected_source_paths": [],
        "forbidden_claims": list(row.get("must_not_include", [])),
        "required_clarifications": clarifications,
        "evaluation_dimensions": _default_dimensions(expected_behavior),
        "fixtures": {
            "planner": {"expected_slots": [], "status": "needs_annotation"},
            "retrieval": {"required_evidence": required_evidence, "expected_source_paths": []},
            "gate_policy": {"expected_behavior": expected_behavior},
            "generation": {"gold_answer_points": gold_points, "gold_answer": None, "forbidden_claims": list(row.get("must_not_include", []))},
            "grounding": {"required_evidence": required_evidence},
        },
    }


def build_records(csv_path: Path, json_path: Path) -> list[dict[str, Any]]:
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        csv_records = [_record_from_csv(row) for row in csv.DictReader(handle)]
    json_rows = json.loads(json_path.read_text(encoding="utf-8"))
    json_records = [_record_from_json(row) for row in json_rows]
    records = csv_records + json_records
    ids = [record["id"] for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("question bank namespace 이후에도 ID 충돌이 있습니다.")
    return records


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=ROOT / "eval_questions_final.csv")
    parser.add_argument("--json", type=Path, default=ROOT / "eval_questions.json")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/question_bank_v1.jsonl")
    parser.add_argument("--metadata-output", type=Path, default=ROOT / "evaluation/question_bank_v1_metadata.json")
    args = parser.parse_args()

    records = build_records(args.csv, args.json)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    metadata = {
        "schema_version": "1.0",
        "purpose": "development/regression specification bank; not training data and not a fresh holdout",
        "record_count": len(records),
        "source_sets": {
            "eval_questions_final_csv": {"count": sum(record["source_set"] == "eval_questions_final_csv" for record in records), "sha256": _sha256(args.csv)},
            "eval_questions_json": {"count": sum(record["source_set"] == "eval_questions_json" for record in records), "sha256": _sha256(args.json)},
        },
        "namespace_rule": "id = CSV-<source_item_id> or JSON-<source_item_id>; never merge source files by EVAL number alone",
        "planner_slot_policy": "Source files do not supply canonical planner slots. planner.expected_slots remains empty until separately reviewed; gold answer rubrics must not be silently treated as canonical slots.",
    }
    args.metadata_output.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"records": len(records), "output": str(args.output), "metadata": str(args.metadata_output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
