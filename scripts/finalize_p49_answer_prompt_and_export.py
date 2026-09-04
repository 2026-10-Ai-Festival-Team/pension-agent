"""Freeze the P49 final answer prompt and export only Final Acceptance 600."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ACCEPTANCE = ROOT / "evaluation/fine_tuning/p49_2h_final_acceptance_600_manifest_v1.jsonl"
ACCEPTANCE_AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_final_acceptance_600_audit_v1.json"
PROMPT = ROOT / "evaluation/fine_tuning/generator_prompt_final_v1.json"
EXPORT_JSONL = ROOT / "evaluation/fine_tuning/p49_hcx005_training_export_v1.jsonl"
EXPORT_CSV = ROOT / "evaluation/fine_tuning/p49_hcx005_training_export_v1.csv"
MANIFEST = ROOT / "evaluation/fine_tuning/p49_hcx005_training_export_manifest_v1.json"

PROMPT_ID = "generator_prompt_final_v1"
MAX_TEXT_CHARS = 30_000
OUTCOME_TARGETS = {"supported_answer": 390, "clarification_required": 108, "bounded_answer": 102}

SYSTEM_PROMPT = """당신은 제공된 연금 문서 근거에만 근거해 답하는 생성기입니다.

입력에는 질문, canonical requirement, 선택된 직접 근거, 결과 유형이 주어집니다. 결과 유형과 직접 근거의 범위를 벗어나지 마세요.

- supported_answer: 질문의 canonical requirement에 필요한 사실을 빠짐없이 답하세요. 근거 밖 사실·수치·상품·조건을 추가하지 말고, 인접 field를 확장하지 마세요.
- clarification_required: 결론이나 추천을 만들지 말고, 결정을 위해 필요한 최소 조건만 질문하세요.
- bounded_answer: 직접 근거에 없는 미래값·예측값·미지원 항목을 만들지 마세요. 확인 가능한 범위만 답하고 한계를 밝히세요.
- subject, 제도, 상품을 서로 바꾸거나 혼동하지 마세요. 근거 없는 투자 추천·단정적 권유를 하지 마세요.

출력은 반드시 아래 세 section을 순서대로 포함합니다.
[답변]
...
[근거]
...
[유의사항]
...

실제 유의사항이 없으면 [유의사항]에는 '없음'이라고 쓰세요. [근거]에는 선택된 직접 근거에 있는 짧은 원문 표현만 사용하세요."""


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_new(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing overwrite: {path}")
    path.write_text(content, encoding="utf-8")


def candidate_id(row: dict[str, Any]) -> str:
    return str(row.get("remediation_request_id") or row.get("full_request_id") or "")


def canonical_requirements(row: dict[str, Any]) -> list[str]:
    values = [item.get("canonical_requirement") for item in row.get("requirements", []) if item.get("canonical_requirement")]
    if values:
        return list(dict.fromkeys(values))
    contract = row.get("host_question_contract", {})
    allowed = [value for value in contract.get("allowed_fields", []) if value]
    if allowed:
        return list(dict.fromkeys(allowed))
    if contract.get("question_scope"):
        return [contract["question_scope"]]
    raise ValueError(f"canonical requirement unavailable: {candidate_id(row)}")


def evidence_text(row: dict[str, Any]) -> tuple[str, str]:
    evidence = row.get("direct_evidence", [])
    if evidence:
        parts = []
        for item in evidence:
            if not all(isinstance(item.get(field), str) and item[field] for field in ("chunk_id", "source_id", "text")):
                raise ValueError(f"malformed direct evidence: {candidate_id(row)}")
            parts.append(f"[chunk_id: {item['chunk_id']}]\n{item['text']}")
        return "\n\n".join(parts), "selected_direct_evidence"
    if row.get("outcome") == "clarification_required" or row.get("evidence_status") == "none":
        return "없음", "explicit_no_direct_evidence_allowed_by_outcome"
    raise ValueError(f"missing required direct-evidence binding: {candidate_id(row)}")


def training_text(*, question: str, requirements: list[str], evidence: str, outcome: str) -> str:
    return (
        f"[질문]\n{question}\n\n"
        f"[canonical requirement]\n" + "\n".join(requirements) + "\n\n"
        f"[선택된 직접 근거]\n{evidence}\n\n"
        f"[결과 유형]\n{outcome}"
    )


def validate_completion(completion: str, request_id: str) -> None:
    markers = ("[답변]", "[근거]", "[유의사항]")
    if not completion.startswith("[답변]") or any(marker not in completion for marker in markers):
        raise ValueError(f"completion section contract failed: {request_id}")
    if not (completion.index("[답변]") < completion.index("[근거]") < completion.index("[유의사항]")):
        raise ValueError(f"completion section order failed: {request_id}")


def build_rows(accepted: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    outcome_counts = Counter()
    no_evidence_binding = 0
    for index, source in enumerate(accepted, start=1):
        request_id = candidate_id(source)
        if not request_id or request_id in seen:
            raise ValueError(f"duplicate or missing accepted candidate ID: {request_id}")
        seen.add(request_id)
        if source.get("acceptance_status") != "accepted_final_600" or source.get("validation_status") != "pass":
            raise ValueError(f"non-accepted record entered export: {request_id}")
        outcome = source.get("outcome")
        if outcome not in OUTCOME_TARGETS:
            raise ValueError(f"unknown outcome: {request_id}")
        requirements = canonical_requirements(source)
        evidence, binding = evidence_text(source)
        if binding.startswith("explicit_no"):
            no_evidence_binding += 1
        completion = source.get("draft_completion", "")
        validate_completion(completion, request_id)
        text = training_text(question=source["question"], requirements=requirements, evidence=evidence, outcome=outcome)
        if len(text) > MAX_TEXT_CHARS:
            raise ValueError(f"CLOVA row exceeds explicit text limit: {request_id}")
        rows.append({
            "C_ID": index,
            "T_ID": index,
            "System_Prompt": SYSTEM_PROMPT,
            "Text": text,
            "Completion": completion,
        })
        outcome_counts[outcome] += 1
    audit = {
        "records": len(rows), "outcome_counts": dict(outcome_counts),
        "duplicate_candidate_id": 0, "missing_completion": 0,
        "missing_evidence_binding": 0, "provenance_error": 0,
        "acceptance_outside_record": 0,
        "explicit_no_direct_evidence_bindings": no_evidence_binding,
    }
    if len(rows) != 600 or dict(outcome_counts) != OUTCOME_TARGETS:
        raise ValueError("Final Acceptance export quota drift")
    return rows, audit


def main() -> None:
    accepted = read_jsonl(ACCEPTANCE)
    acceptance_audit = json.loads(ACCEPTANCE_AUDIT.read_text(encoding="utf-8"))
    if not acceptance_audit.get("final_acceptance_go") or len(accepted) != 600:
        raise RuntimeError("Final Acceptance 600 is not frozen GO")
    for path in (PROMPT, EXPORT_JSONL, EXPORT_CSV, MANIFEST):
        if path.exists():
            raise FileExistsError(f"export artifact already exists: {path}")
    prompt_payload = {
        "prompt_id": PROMPT_ID,
        "status": "frozen_final_answer_prompt",
        "runtime_input_contract": ["question", "canonical_requirement", "selected_direct_evidence", "outcome"],
        "output_contract": ["[답변]", "[근거]", "[유의사항]"],
        "semantic_guards": [
            "required_fact_completeness", "evidence_only_grounding", "adjacent_field_prohibition",
            "subject_product_preservation", "bounded_no_future_invention",
            "clarification_minimum_missing_conditions", "no_unsupported_investment_recommendation",
        ],
        "prompt": SYSTEM_PROMPT,
    }
    prompt_bytes = (SYSTEM_PROMPT + "\n").encode("utf-8")
    prompt_payload["prompt_sha256"] = sha256_bytes(prompt_bytes)
    rows, export_audit = build_rows(accepted)
    jsonl = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    csv_lines: list[str] = []
    import io
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=["C_ID", "T_ID", "System_Prompt", "Text", "Completion"])
    writer.writeheader(); writer.writerows(rows)
    csv_text = buffer.getvalue()
    manifest = {
        "stage": "P49 Final Answer Prompt Freeze + HCX-005 Training Export",
        "external_hcx_calls": 0, "ncp_tuning_api_calls": 0,
        "augmentation_generation_status": "closed",
        "authority_manifest": ACCEPTANCE.name,
        "authority_manifest_sha256": sha256_bytes(ACCEPTANCE.read_bytes()),
        "acceptance_audit_sha256": sha256_bytes(ACCEPTANCE_AUDIT.read_bytes()),
        "prompt_artifact": PROMPT.name, "prompt_id": PROMPT_ID, "prompt_sha256": prompt_payload["prompt_sha256"],
        "export_jsonl": EXPORT_JSONL.name, "export_jsonl_sha256": sha256_bytes(jsonl.encode("utf-8")),
        "export_csv": EXPORT_CSV.name, "export_csv_sha256": sha256_bytes(csv_text.encode("utf-8")),
        "clova_schema": ["C_ID", "T_ID", "System_Prompt", "Text", "Completion"],
        "text_limit_chars": MAX_TEXT_CHARS,
        "training_export_audit": export_audit,
        "training_export_go": export_audit == {
            "records": 600, "outcome_counts": OUTCOME_TARGETS,
            "duplicate_candidate_id": 0, "missing_completion": 0, "missing_evidence_binding": 0,
            "provenance_error": 0, "acceptance_outside_record": 0,
            "explicit_no_direct_evidence_bindings": export_audit["explicit_no_direct_evidence_bindings"],
        },
        "tuning_allowed": False,
    }
    write_new(PROMPT, json.dumps(prompt_payload, ensure_ascii=False, indent=2) + "\n")
    write_new(EXPORT_JSONL, jsonl)
    write_new(EXPORT_CSV, csv_text)
    write_new(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"records": len(rows), "prompt_sha256": prompt_payload["prompt_sha256"], "training_export_go": manifest["training_export_go"], "external_hcx_calls": 0, "ncp_tuning_api_calls": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
