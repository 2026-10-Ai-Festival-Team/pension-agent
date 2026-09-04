"""Validate P49-2H-3C micro-pilot candidates without promoting any record."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/parsed/chunks.jsonl"
FROZEN_SEED = ROOT / "evaluation/robustness/p49_2h_robustness_human_seed_v1.jsonl"
UNREQUESTED_CAVEAT_TERMS = ("투자판단", "투자 판단", "투자 권유", "추천드립니다", "권유드립니다")

# Host-owned, exact product identities for the curated sources used in this
# micro-pilot.  They are deliberately not fuzzy matching rules: an explicit
# product mention in the question must resolve to exactly this source subject.
PRODUCT_SUBJECTS = {
    "545de7c663ff2726": {
        "product_code": "KR5114450222",
        "product_name": "삼성클래식연금증권전환형자투자신탁 제1호[주식]",
    },
    "9175b4d6847de4c3": {
        "product_code": "KR5113450111",
        "product_name": "한국투자 골드플랜 연금 증권 전환형 투자신탁 1호(주식)",
    },
    "1bfc399c9b3d6a67": {
        "product_code": "KR5111420047",
        "product_name": None,
    },
}

# Exhaustive wording such as “어떤 서류” asks for document categories, not
# merely a single true example from the chunk.  Each category may have several
# evidence spellings; the answer must mention at least one spelling per group.
REQUIRED_ITEM_CONTRACTS = {
    "DC.early_withdrawal.required_documents": {
        "exhaustive_question_markers": ("어떤 서류", "필요한 서류", "무슨 서류", "무엇이 필요"),
        "required_item_groups": {
            "application_form": ("신청양식", "중도인출신청서"),
            "medical_certificate": ("진단서", "소견서"),
            "long_term_care_confirmation": ("장기요양확인서", "장기요양인정서"),
            "income_verification": ("연간임금총액", "근로소득원천징수영수증", "보수총액신고서", "급여명세서"),
            "medical_expense_proof": ("의료비 지출", "진료비계산서", "진료비영수증", "의료비 증빙"),
        },
    },
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def normalized(text: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", text.lower())


def trigrams(text: str) -> set[str]:
    text = normalized(text)
    return {text[index:index + 3] for index in range(max(0, len(text) - 2))} or {text}


def similarity(left: str, right: str) -> float:
    first, second = trigrams(left), trigrams(right)
    return len(first & second) / len(first | second) if first | second else 1.0


def subject_contract_for_evidence(evidence: list[dict]) -> dict | None:
    """Return the one exact product subject bound to the evidence, if any."""
    subjects = [PRODUCT_SUBJECTS[item["source_id"]] for item in evidence if item.get("source_id") in PRODUCT_SUBJECTS]
    unique = {(item["product_code"], item["product_name"]) for item in subjects}
    if len(unique) != 1:
        return None
    code, name = next(iter(unique))
    return {"entity_type": "product", "canonical_id": code, "canonical_name": name}


def explicit_product_subjects(question: str) -> set[str]:
    """Resolve only exact known product identifiers present in the question."""
    compact = normalized(question)
    found: set[str] = set()
    for subject in PRODUCT_SUBJECTS.values():
        aliases = (subject["product_code"], subject["product_name"])
        if any(alias and normalized(alias) in compact for alias in aliases):
            found.add(subject["product_code"])
    return found


def validate_subject_provenance(row: dict) -> list[str]:
    """Fail closed on an explicit product subject that differs from evidence."""
    contract = row.get("subject_contract") or subject_contract_for_evidence(row.get("direct_evidence", []))
    if not contract or contract.get("entity_type") != "product":
        return []
    question_subjects = explicit_product_subjects(row["question"])
    if question_subjects and question_subjects != {contract["canonical_id"]}:
        return ["subject_provenance_mismatch"]
    return []


def validate_required_item_completeness(row: dict) -> list[str]:
    """Check mandatory evidence categories when the question asks exhaustively."""
    if row["outcome"] != "supported_answer":
        return []
    requirement = row["requirements"][0]["canonical_requirement"]
    contract = REQUIRED_ITEM_CONTRACTS.get(requirement)
    if not contract or not any(marker in row["question"] for marker in contract["exhaustive_question_markers"]):
        return []
    answer = normalized(row["draft_completion"].split("[근거]", 1)[0])
    omitted = [
        name for name, aliases in contract["required_item_groups"].items()
        if not any(normalized(alias) in answer for alias in aliases)
    ]
    return ["required_item_omission:" + ",".join(omitted)] if omitted else []


def status_for(requirements: list[dict], outcome: str) -> str:
    factual = [row for row in requirements if row["requirement_kind"] == "factual" and row["coverage_required"]]
    statuses = {row["support_status"] for row in factual}
    if not factual:
        return "unresolved" if outcome == "clarification_required" else "none"
    if statuses == {"supported"}:
        return "full"
    if statuses == {"unsupported"}:
        return "none"
    return "partial"


def validate_supported(row: dict) -> list[str]:
    """Validate the host-defined answer field, not every adjacent chunk fact."""
    findings: list[str] = []
    answer_text = row["draft_completion"].split("[근거]", 1)[0]
    contract = row.get("modifiers", {}).get("answer_contract", {})
    normalized_answer = normalized(answer_text)
    if contract.get("required_terms") and not all(normalized(term) in normalized_answer for term in contract["required_terms"]):
        findings.append("supported_required_fact_omission")
    if any(normalized(term) in normalized_answer for term in contract.get("forbidden_terms", [])):
        findings.append("supported_adjacent_field_expansion")
    if any(normalized(term) in normalized_answer for term in contract.get("unsupported_caveat_terms", [])):
        findings.append("supported_unsupported_caveat_expansion")
    if any(normalized(term) in normalized_answer for term in UNREQUESTED_CAVEAT_TERMS):
        findings.append("supported_unrequested_caveat_expansion")
    return findings


def validate_clarification(row: dict, expected: str) -> list[str]:
    """A clarification must ask only host-specified missing conditions."""
    findings: list[str] = []
    if expected != "unresolved" or row["direct_evidence"] or row["required_gold_facts"]:
        findings.append("clarification_must_not_answer_or_bind_evidence")
    missing_conditions = row.get("modifiers", {}).get("missing_conditions", [])
    completion = row["draft_completion"]
    if "[답변] 정확히 안내하려면 다음 정보를 알려주세요." not in completion and not completion.strip().endswith("?") and "?" not in completion:
        findings.append("clarification_completion_not_question")
    if missing_conditions and not any(condition.split()[0] in completion for condition in missing_conditions):
        findings.append("clarification_missing_condition_not_requested")
    # Host assembly may include a generic process sentence but must never cite
    # evidence or turn the scenario into a pension factual answer.
    if "[근거] 없음" not in completion or any(token in completion for token in ("60일", "600만원", "900만원", "1/12", "2등급")):
        findings.append("clarification_factual_answer_leakage")
    return findings


def validate_bounded(row: dict, expected: str) -> list[str]:
    """A bounded answer must state its supported part and limit only the target."""
    findings: list[str] = []
    if expected not in {"partial", "none"}:
        findings.append("bounded_contract_mismatch")
    disclosure = row.get("modifiers", {}).get("unsupported_disclosure", "")
    target = row.get("modifiers", {}).get("unsupported_target", "")
    completion = row["draft_completion"]
    if not disclosure or disclosure not in completion:
        findings.append("bounded_unsupported_disclosure_missing")
    if target and not any(word in disclosure for word in target.split() if len(word) >= 2):
        findings.append("bounded_disclosure_does_not_name_target")
    answer_text = completion.split("[근거]", 1)[0]
    required_terms = row.get("modifiers", {}).get("supported_answer_required_terms", [])
    normalized_answer = normalized(answer_text)
    if required_terms and not all(normalized(term) in normalized_answer for term in required_terms):
        findings.append("bounded_supported_part_omission")
    generic_disclaimers = ("제공된자료에서확인가능한현재정보만안내할수있습니다", "해당정보는제공할수없습니다", "죄송합니다만")
    if any(normalized(phrase) in normalized_answer for phrase in generic_disclaimers):
        findings.append("bounded_generic_disclaimer")
    if any(normalized(term) in normalized_answer for term in UNREQUESTED_CAVEAT_TERMS):
        findings.append("bounded_unrequested_caveat_expansion")
    # Unsupported future values must be confined to the host-owned disclosure.
    if any(term in answer_text for term in ("내년", "다음 달", "3년 뒤", "확정", "예측")):
        findings.append("bounded_unsupported_fact_generation")
    return findings


def validate(row: dict, corpus: dict[str, dict]) -> list[str]:
    findings: list[str] = []
    required = {"candidate_schema_version", "candidate_id", "micro_request_id", "coverage_cell", "target_outcome", "outcome", "question", "requirements", "evidence_status", "direct_evidence", "required_gold_facts", "draft_completion", "generation_status", "generation_model", "generation_prompt_version", "generation_attempt", "generation_parameters", "validation_status", "validation_failures", "human_review_status", "acceptance_status", "candidate_lifecycle"}
    missing = sorted(required - row.keys())
    if missing:
        return ["missing_required_fields:" + ",".join(missing)]
    if row["generation_status"] != "generated" or row["validation_status"] != "pending":
        findings.append("invalid_automation_lifecycle")
    if row["human_review_status"] != "pending" or row["acceptance_status"] != "not_accepted":
        findings.append("automation_promoted_human_or_acceptance")
    lifecycle = row["candidate_lifecycle"]
    if lifecycle.get("state") != "generated" or lifecycle.get("human_review") != "pending" or lifecycle.get("acceptance") != "not_accepted":
        findings.append("invalid_candidate_state_machine")
    if row["target_outcome"] != row["outcome"]:
        findings.append("host_owned_outcome_mismatch")
    if row["generation_model"] != "HCX-007" or row["generation_attempt"] not in {1, 2, 3}:
        findings.append("generation_provenance_invalid")
    if "P49" in row["question"] or "chunk_id" in row["question"] or len(row["question"].strip()) < 4:
        findings.append("question_is_instruction_or_not_natural")
    requirements = row["requirements"]
    expected = status_for(requirements, row["outcome"])
    if row["evidence_status"] != expected:
        findings.append("evidence_status_mismatch")
    if row["outcome"] == "supported_answer" and expected != "full":
        findings.append("supported_contract_mismatch")
    if row["outcome"] == "supported_answer":
        findings.extend(validate_supported(row))
        findings.extend(validate_required_item_completeness(row))
    elif row["outcome"] == "clarification_required":
        findings.extend(validate_clarification(row, expected))
    elif row["outcome"] == "bounded_answer":
        findings.extend(validate_bounded(row, expected))
    bound_ids = {chunk_id for req in requirements for chunk_id in req["evidence_chunk_ids"]}
    direct = {item["chunk_id"]: item for item in row["direct_evidence"]}
    if set(direct) != bound_ids:
        findings.append("direct_evidence_requirement_binding_mismatch")
    for chunk_id, evidence in direct.items():
        if chunk_id not in corpus or evidence.get("text") != corpus[chunk_id]["text"]:
            findings.append("direct_evidence_not_exact_corpus_copy")
    findings.extend(validate_subject_provenance(row))
    supported = {req["canonical_requirement"] for req in requirements if req["coverage_required"] and req["support_status"] == "supported"}
    facts_by_requirement = Counter()
    for fact in row["required_gold_facts"]:
        fact_required = {"fact_id", "requirement", "text", "evidence_chunk_ids", "evidence_literal_quotes"}
        if fact_required - fact.keys():
            findings.append("malformed_required_gold_fact")
            continue
        if fact["requirement"] not in supported:
            findings.append("gold_fact_not_for_supported_requirement")
        facts_by_requirement[fact["requirement"]] += 1
        text = "\n".join(corpus.get(chunk_id, {}).get("text", "") for chunk_id in fact["evidence_chunk_ids"])
        if not fact["evidence_literal_quotes"]:
            findings.append("missing_evidence_literal_quote")
        if any(quote not in text or quote.startswith("CHK-") or re.fullmatch(r"[0-9a-f]{16}-.+", quote) for quote in fact["evidence_literal_quotes"]):
            findings.append("evidence_literal_quote_not_exact")
    if row["outcome"] in {"supported_answer", "bounded_answer"} and any(facts_by_requirement[key] == 0 for key in supported):
        findings.append("supported_requirement_missing_gold_fact")
    return sorted(set(findings))


def lifecycle_after_validation(row: dict, findings: list[str]) -> dict:
    """Record deterministic gates without granting human approval/export."""
    lifecycle = dict(row["candidate_lifecycle"])
    schema_failures = ("missing_required_fields", "invalid_candidate_state_machine", "generation_provenance_invalid")
    evidence_markers = ("evidence", "gold_fact", "supported_requirement")
    semantic_markers = ("supported_", "bounded_", "clarification_", "question_is_", "required_item_", "subject_provenance_")
    dedup_markers = ("near_duplicate",)
    lifecycle["schema"] = "fail" if any(item.startswith(schema_failures) for item in findings) else "schema_valid"
    lifecycle["evidence"] = "fail" if any(any(marker in item for marker in evidence_markers) for item in findings) else "evidence_valid"
    lifecycle["semantic"] = "fail" if any(any(marker in item for marker in semantic_markers) for item in findings) else "semantic_valid"
    lifecycle["dedup"] = "fail" if any(any(marker in item for marker in dedup_markers) for item in findings) else "dedup_valid"
    lifecycle["state"] = "dedup_valid" if not findings else "generated"
    lifecycle["human_review"] = "pending"
    lifecycle["acceptance"] = "not_accepted"
    return lifecycle


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--near-duplicate-threshold", type=float, default=0.88)
    args = parser.parse_args()
    rows = read_jsonl(args.input)
    corpus = {row["chunk_id"]: row for row in read_jsonl(CORPUS)}
    seed_questions = [row["question"] for row in read_jsonl(FROZEN_SEED)]
    duplicate_findings: dict[str, list[str]] = {row["candidate_id"]: [] for row in rows}
    for index, row in enumerate(rows):
        if any(similarity(row["question"], question) >= args.near_duplicate_threshold for question in seed_questions):
            duplicate_findings[row["candidate_id"]].append("near_duplicate_frozen_seed")
        for other in rows[:index]:
            if similarity(row["question"], other["question"]) >= args.near_duplicate_threshold:
                duplicate_findings[row["candidate_id"]].append("near_duplicate_candidate")
                duplicate_findings[other["candidate_id"]].append("near_duplicate_candidate")
    validated = []
    operational = {"requested": len(rows), "generated": 0, "generation_exhausted": 0}
    for row in rows:
        # Exhaustion is an operational result of the bounded retry policy, not
        # a generated-candidate quality verdict.  Preserve its attribution but
        # exclude it from the schema/evidence/semantic/dedup denominator.
        if row.get("generation_status") == "generation_exhausted":
            operational["generation_exhausted"] += 1
            validated.append({
                **row,
                "validation_status": "not_evaluated",
                "validation_findings": [],
                "operational_failure_reasons": row.get("validation_failures", []),
                "candidate_lifecycle": {
                    **row["candidate_lifecycle"],
                    "state": "generation_exhausted",
                    "schema": "not_evaluated", "evidence": "not_evaluated",
                    "semantic": "not_evaluated", "dedup": "not_evaluated",
                },
            })
            continue
        operational["generated"] += 1
        findings = validate(row, corpus) + duplicate_findings[row["candidate_id"]]
        findings = sorted(set(findings))
        validated.append({
            **row,
            "validation_status": "pass" if not findings else "fail",
            "validation_failures": findings,
            "validation_findings": findings,
            "candidate_lifecycle": lifecycle_after_validation(row, findings),
        })
    quality_rows = [row for row in validated if row["validation_status"] != "not_evaluated"]
    by_lane = {lane: {"total": sum(row["outcome"] == lane for row in quality_rows), "pass": sum(row["outcome"] == lane and row["validation_status"] == "pass" for row in quality_rows)} for lane in ("supported_answer", "clarification_required", "bounded_answer")}
    manifest = {
        "stage": "P49-2H-3C Contract-Split Micro-Pilot Validation", "input_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "record_count": len(validated), "operational": operational,
        "quality_generated_count": len(quality_rows),
        "validation_pass_count": sum(row["validation_status"] == "pass" for row in quality_rows),
        "validation_fail_count": sum(row["validation_status"] == "fail" for row in quality_rows), "lane_results": by_lane,
        "literal_quote_compliance": sum("evidence_literal_quote_not_exact" not in row["validation_findings"] and "missing_evidence_literal_quote" not in row["validation_findings"] for row in validated if row["outcome"] in {"supported_answer", "bounded_answer"}),
        "accepted_records": 0, "training_export_allowed": False, "tuning_allowed": False,
        "next_required_action": "Human evidence-first spot review and outcome-lane attribution; do not promote records automatically.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in validated), encoding="utf-8")
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
