"""Validate P49-2H augmentation candidates without promoting them to training.

The validator consumes a raw oversampled JSONL batch.  It validates provenance,
numeric/factual anchors, behavior-policy state, duplicate leakage, and quota
distribution.  It only writes a validation result; human-review and acceptance
states always remain untouched by this script.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "evaluation"
CONTRACT = BASE / "fine_tuning/p49_2h_candidate_generation_contract_v1.json"
MATRIX = BASE / "fine_tuning/p49_2h_augmentation_coverage_matrix_v1.json"
CORPUS = ROOT / "data/parsed/chunks.jsonl"
FROZEN_SEED = BASE / "robustness/p49_2h_robustness_human_seed_v1.jsonl"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def normalized(text: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", text.lower())


def trigrams(text: str) -> set[str]:
    text = normalized(text)
    return {text[index : index + 3] for index in range(max(0, len(text) - 2))} or {text}


def similarity(left: str, right: str) -> float:
    a, b = trigrams(left), trigrams(right)
    return len(a & b) / len(a | b) if a | b else 1.0


def expected_evidence_status(requirements: list[dict], outcome: str) -> str:
    factual = [item for item in requirements if item["requirement_kind"] == "factual" and item["coverage_required"]]
    if not factual:
        return "unresolved" if outcome == "clarification_required" else "none"
    statuses = {item["support_status"] for item in factual}
    if statuses == {"supported"}:
        return "full"
    if statuses == {"unsupported"}:
        return "none"
    return "partial"


def numeric_tokens(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:[,.]\d+)?(?:%|년|만원|일|분의\s*\d+)?", re.sub(r"\s+", "", text)))


def valid_percent_of_derivation(fact: dict, evidence_text: str) -> bool:
    """Allow only an auditable ``base × rate%`` calculation.

    It covers facts such as ``600만원 × 16.5% = 99만원`` without allowing a
    generator to introduce arbitrary numeric values.  All inputs must remain
    literal anchors in the selected original evidence.
    """
    derivation = fact.get("derivation")
    if not isinstance(derivation, dict) or derivation.get("operator") != "percent_of":
        return False
    try:
        base = float(derivation["base"])
        rate_percent = float(derivation["rate_percent"])
        result = float(derivation["result"])
    except (KeyError, TypeError, ValueError):
        return False
    if abs(base * rate_percent / 100 - result) > 1e-9:
        return False
    anchors = derivation.get("evidence_anchors")
    if not isinstance(anchors, list) or not anchors or not all(anchor in evidence_text for anchor in anchors):
        return False
    return str(int(result) if result.is_integer() else result) in re.sub(r"\s+", "", fact["text"])


def validate_candidate(
    candidate: dict,
    *,
    corpus: dict[str, dict],
    known_seed_ids: set[str],
    known_question_types: set[str],
    active_domains: set[str],
) -> list[str]:
    findings: list[str] = []
    required = {
        "candidate_id", "source_seed_id", "question_type", "factual_domain", "outcome", "modifiers", "question",
        "requirements", "evidence_status", "direct_evidence", "required_gold_facts", "optional_relevant_context",
        "draft_completion", "generation_status", "validation_status", "human_review_status", "acceptance_status",
    }
    missing = sorted(required - candidate.keys())
    if missing:
        return [f"missing_required_fields:{','.join(missing)}"]
    if candidate["source_seed_id"] not in known_seed_ids:
        findings.append("unknown_source_seed_id")
    if candidate["question_type"] not in known_question_types:
        findings.append("unknown_question_type")
    if candidate["factual_domain"] not in active_domains:
        findings.append("inactive_or_unknown_domain")
    if candidate["generation_status"] != "generated":
        findings.append("generation_status_not_generated")
    if candidate["validation_status"] != "pending":
        findings.append("validation_status_must_start_pending")
    if candidate["human_review_status"] != "pending" or candidate["acceptance_status"] != "not_accepted":
        findings.append("automation_must_not_promote_human_or_acceptance_status")

    requirements = candidate["requirements"]
    requirement_by_name = {item.get("canonical_requirement"): item for item in requirements}
    if len(requirement_by_name) != len(requirements):
        findings.append("duplicate_or_missing_canonical_requirement")
    for item in requirements:
        required_req_fields = {"canonical_requirement", "requirement_kind", "coverage_required", "support_status", "evidence_chunk_ids"}
        if required_req_fields - item.keys():
            findings.append("malformed_requirement")
            continue
        chunk_ids = item["evidence_chunk_ids"]
        if any(chunk_id.startswith("CHK-") or chunk_id not in corpus for chunk_id in chunk_ids):
            findings.append("opaque_or_missing_requirement_evidence")
        if item["support_status"] == "unsupported" and chunk_ids:
            findings.append("unsupported_requirement_has_evidence")
        if item["support_status"] == "supported" and item["requirement_kind"] == "factual" and item["coverage_required"] and not chunk_ids:
            findings.append("supported_factual_requirement_missing_evidence")
    if candidate["evidence_status"] != expected_evidence_status(requirements, candidate["outcome"]):
        findings.append("evidence_status_mismatch")
    outcome_ok = (
        (candidate["outcome"] == "supported_answer" and candidate["evidence_status"] == "full")
        or (candidate["outcome"] == "clarification_required" and candidate["evidence_status"] == "unresolved")
        or (candidate["outcome"] == "bounded_answer" and candidate["evidence_status"] in {"partial", "none"})
    )
    if not outcome_ok:
        findings.append("outcome_behavior_policy_mismatch")

    direct = {item.get("chunk_id"): item for item in candidate["direct_evidence"]}
    requirement_chunk_ids = {chunk_id for item in requirements for chunk_id in item["evidence_chunk_ids"]}
    if set(direct) != requirement_chunk_ids:
        findings.append("direct_evidence_requirement_binding_mismatch")
    for chunk_id, item in direct.items():
        source = corpus.get(chunk_id)
        if not source or item.get("text") != source["text"]:
            findings.append("direct_evidence_not_exact_corpus_copy")
            break

    supported_factual_requirements = {
        item["canonical_requirement"]
        for item in requirements
        if item["requirement_kind"] == "factual" and item["coverage_required"] and item["support_status"] == "supported"
    }
    facts_by_requirement = Counter()
    for fact in candidate["required_gold_facts"]:
        needed = {"fact_id", "requirement", "text", "evidence_chunk_ids", "evidence_anchors", "completion_required_terms"}
        if needed - fact.keys():
            findings.append("malformed_required_gold_fact")
            continue
        if fact["requirement"] not in supported_factual_requirements:
            findings.append("required_fact_is_not_supported_requirement")
        facts_by_requirement[fact["requirement"]] += 1
        requirement = requirement_by_name.get(fact["requirement"], {})
        if not set(fact["evidence_chunk_ids"]).issubset(set(requirement.get("evidence_chunk_ids", []))):
            findings.append("gold_fact_evidence_outside_requirement_binding")
        anchored_text = "\n".join(corpus.get(chunk_id, {}).get("text", "") for chunk_id in fact["evidence_chunk_ids"])
        for anchor in fact["evidence_anchors"]:
            if anchor not in anchored_text:
                findings.append("gold_fact_anchor_missing_from_evidence")
                break
        evidence_numbers = numeric_tokens(anchored_text)
        fact_numbers = numeric_tokens(fact["text"])
        if not fact_numbers.issubset(evidence_numbers) and not valid_percent_of_derivation(fact, anchored_text):
            findings.append("numeric_fact_not_anchored_in_evidence")
        if not all(term in candidate["draft_completion"] for term in fact["completion_required_terms"]):
            findings.append("draft_completion_missing_required_term")
    if any(facts_by_requirement[requirement] == 0 for requirement in supported_factual_requirements):
        findings.append("supported_requirement_missing_required_gold_fact")
    return sorted(set(findings))


def duplicate_findings(candidates: list[dict], seed_questions: list[str], threshold: float) -> dict[str, list[str]]:
    findings: dict[str, list[str]] = {item["candidate_id"]: [] for item in candidates}
    for index, candidate in enumerate(candidates):
        for seed_question in seed_questions:
            if similarity(candidate["question"], seed_question) >= threshold:
                findings[candidate["candidate_id"]].append("near_duplicate_frozen_seed")
                break
        for other in candidates[:index]:
            if similarity(candidate["question"], other["question"]) >= threshold:
                findings[candidate["candidate_id"]].append("near_duplicate_candidate")
                findings[other["candidate_id"]].append("near_duplicate_candidate")
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Raw oversampled candidate JSONL")
    parser.add_argument("--output", type=Path, required=True, help="Validated candidate JSONL")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--near-duplicate-threshold", type=float, default=0.88)
    parser.add_argument("--full-batch", action="store_true", help="Require the frozen 700-record lane quota.")
    args = parser.parse_args()

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    candidates = read_jsonl(args.input)
    corpus = {item["chunk_id"]: item for item in read_jsonl(CORPUS)}
    frozen_seed = read_jsonl(FROZEN_SEED)
    known_seed_ids = {item["record_id"] for item in frozen_seed}
    question_types = {item["code"] for item in matrix["question_type_targets"]}
    active_domains = {item["code"] for item in matrix["domain_targets"]}
    if len({item.get("candidate_id") for item in candidates}) != len(candidates):
        raise RuntimeError("Candidate IDs must be present and unique.")
    duplicate = duplicate_findings(candidates, [item["question"] for item in frozen_seed], args.near_duplicate_threshold)
    validated = []
    for candidate in candidates:
        findings = validate_candidate(candidate, corpus=corpus, known_seed_ids=known_seed_ids, known_question_types=question_types, active_domains=active_domains)
        findings.extend(duplicate.get(candidate.get("candidate_id"), []))
        status = "pass" if not findings else "fail"
        validated.append({
            **candidate,
            "validation_status": status,
            "validation_findings": sorted(set(findings)),
            "human_review_status": candidate["human_review_status"],
            "acceptance_status": candidate["acceptance_status"],
        })
    lane_counts = Counter(item["outcome"] for item in candidates)
    lane_targets = {name: values["raw"] for name, values in contract["lane_targets"].items()}
    quota_findings = {
        outcome: {"actual": lane_counts[outcome], "target": target, "matches": lane_counts[outcome] == target}
        for outcome, target in lane_targets.items()
    }
    full_batch_ok = not args.full_batch or (
        len(candidates) == contract["raw_oversampling_target"] and all(item["matches"] for item in quota_findings.values())
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in validated), encoding="utf-8")
    manifest = {
        "stage": "P49-2H-3 Candidate Validation",
        "input_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "record_count": len(candidates),
        "validation_pass_count": sum(item["validation_status"] == "pass" for item in validated),
        "validation_fail_count": sum(item["validation_status"] == "fail" for item in validated),
        "quota_reconciliation": quota_findings,
        "full_batch_quota_pass": full_batch_ok,
        "human_review_auto_promoted": 0,
        "acceptance_auto_promoted": 0,
        "training_export_allowed": False,
        "next_required_action": "Human/evidence-first QA and quota reconciliation before acceptance; no training export.",
    }
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))
    if not full_batch_ok:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
