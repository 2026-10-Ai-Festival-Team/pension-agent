"""P49-2H-4C: guarded remediation execution and 145-set dedup audit.

The 4B manifest owns coverage, provenance, and semantic controls.  This
module only recovers the matching frozen v3 request, reuses the existing v4
payload/candidate route, and writes an auditable execution result. It permits
one explicit live request or the one frozen 12-record smoke selection; it has
no bulk-remediation route.
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from dataclasses import replace
from itertools import combinations
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_p49_2h_contract_split_micro_pilot import (
    BOUNDED_LINGUISTIC_ANCHOR_FIELDS,
    BOUNDED_TARGETED_PROFILE_FIELDS,
    build_payload,
    banmal_final_question_check_instruction,
    remediation_diversity_instruction,
    remediation_field_boundary_instruction,
    validation_findings_for_attempt,
)
from scripts.run_p49_2h_full_adapter import build_full_candidate, semantic_to_v4_request
from scripts.p49_2h_4d_f_host_renderer import RENDERER_ID as F_REGISTER_RENDERER_ID, surface_findings as f_register_surface_findings
from scripts.p49_2h_4d_i1_supported_host_renderer import RENDERER_ID as I1_RENDERER_ID, surface_findings as i1_surface_findings
from scripts.p49_2h_register_taxonomy import BANMAL_REGISTERS
from scripts.validate_p49_2h_contract_split_micro_pilot import CORPUS, FROZEN_SEED, normalized, similarity
from src.augmentation.hcx_structured_generator import HCXStructuredAugmentationGenerator
from src.config.generation import GenerationSettings
from src.generation.errors import GenerationError


REMEDIATION_MANIFEST = ROOT / "evaluation/fine_tuning/p49_2h_deficit_remediation_manifest_v1.jsonl"
SEMANTIC_REQUESTS = ROOT / "evaluation/fine_tuning/p49_2h_full_semantic_requests_v3.jsonl"
COMPARISON_POOL = ROOT / "evaluation/fine_tuning/p49_2h_full_semantic_validated_v5.jsonl"
TRACE_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4c_execution_bridge_trace_v5.jsonl"
SMOKE_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4c_execution_smoke_v4.jsonl"

SMOKE_REQUEST_IDS = frozenset(
    {f"P49-2H-4B-{number:04d}" for number in range(270, 276)}
    | {f"P49-2H-4B-{number:04d}" for number in range(367, 373)}
)

COMMON_CONTROL_FIELDS = (
    "coverage_cell",
    "target_outcome",
    "canonical_requirement",
    "subject",
    "evidence_chunk_ids",
    "source_ids",
    "context_frame",
    "query_form",
    "register",
    "length_band",
)
LANE_CONTROL_FIELDS = {
    "supported_answer": (),
    "clarification_required": (
        "decision_target",
        "scenario_context",
        "missing_conditions",
        "required_question_slots",
    ),
    "bounded_answer": (
        "unsupported_target",
        "temporal_scope",
        "target_type",
        "concreteness_requirement",
        "supported_requirements",
    ),
}
SEMANTIC_BOUNDARY_FIELDS = ("allowed_fields", "forbidden_fields")
HOST_QUESTION_RENDERER_FIELDS = ("renderer_id", "family")
SUPPORTED_ANSWER_COMPLETENESS_FIELDS = ("canonical_requirement", "required_answer_terms", "required_literal_quotes")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validated_questions(rows: list[dict[str, Any]]) -> list[str]:
    """Return only already-valid questions for the existing dedup comparison."""
    return [row["question"] for row in rows if row.get("validation_status") == "pass"]


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def control_snapshot(remediation: dict[str, Any]) -> dict[str, Any]:
    """Return every 4B field that remains host-owned in the execution path."""
    lane = remediation["target_outcome"]
    if lane not in LANE_CONTROL_FIELDS:
        raise ValueError(f"unsupported remediation outcome lane: {lane}")
    slots = remediation["semantic_slots"]
    snapshot = {
        **{field: deepcopy(remediation[field]) for field in COMMON_CONTROL_FIELDS},
        "outcome": remediation["target_outcome"],
        **{field: deepcopy(slots[field]) for field in SEMANTIC_BOUNDARY_FIELDS},
        **{field: deepcopy(slots[field]) for field in LANE_CONTROL_FIELDS[lane]},
    }
    profile = remediation.get("bounded_diversity_profile")
    if profile is not None:
        if lane != "bounded_answer":
            raise ValueError("bounded diversity profile is not valid outside bounded_answer")
        missing = [field for field in BOUNDED_TARGETED_PROFILE_FIELDS if not profile.get(field)]
        if missing:
            raise ValueError("bounded diversity profile is incomplete: " + ", ".join(missing))
        snapshot["bounded_diversity_profile"] = deepcopy(profile)
    anchor = remediation.get("bounded_linguistic_anchor")
    if anchor is not None:
        if lane != "bounded_answer":
            raise ValueError("bounded linguistic anchor is not valid outside bounded_answer")
        missing = [field for field in BOUNDED_LINGUISTIC_ANCHOR_FIELDS if not anchor.get(field)]
        if missing:
            raise ValueError("bounded linguistic anchor is incomplete: " + ", ".join(missing))
        snapshot["bounded_linguistic_anchor"] = deepcopy(anchor)
    renderer = remediation.get("host_question_renderer")
    if renderer is not None:
        if lane not in {"supported_answer", "clarification_required"}:
            raise ValueError("host question renderer is only valid for supported/clarification")
        missing = [field for field in HOST_QUESTION_RENDERER_FIELDS if not renderer.get(field)]
        if missing:
            raise ValueError("host question renderer is incomplete: " + ", ".join(missing))
        snapshot["host_question_renderer"] = deepcopy(renderer)
    completeness = remediation.get("supported_answer_completeness")
    if completeness is not None:
        if lane != "supported_answer":
            raise ValueError("supported answer completeness is only valid for supported_answer")
        missing = [field for field in SUPPORTED_ANSWER_COMPLETENESS_FIELDS if not completeness.get(field)]
        if missing:
            raise ValueError("supported answer completeness is incomplete: " + ", ".join(missing))
        snapshot["supported_answer_completeness"] = deepcopy(completeness)
    return snapshot


def matching_semantic_request(remediation: dict[str, Any], semantic_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Recover the exact immutable 3F source from which 4B was scheduled."""
    matches = [
        row
        for row in semantic_rows
        if row["target_outcome"] == remediation["target_outcome"]
        and row["coverage_cell"] == remediation["coverage_cell"]
        and row["host_question_contract"] == remediation["semantic_slots"]
        and row["evidence_chunk_ids"] == remediation["evidence_chunk_ids"]
        and row["source_ids"] == remediation["source_ids"]
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one frozen semantic source for {remediation['remediation_request_id']}; found {len(matches)}"
        )
    return matches[0]


def adapt_remediation_record(remediation: dict[str, Any], semantic_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Reuse the v3→v4 adapter and attach 4B-only diversity controls verbatim."""
    source = matching_semantic_request(remediation, semantic_rows)
    request = semantic_to_v4_request(deepcopy(source))
    controls = control_snapshot(remediation)
    request.update(
        {
            "remediation_request_id": remediation["remediation_request_id"],
            "full_request_id": remediation["remediation_request_id"],
            "micro_request_id": remediation["remediation_request_id"],
            "remediation_control": controls,
            # This is host metadata carried beside the HCX prompt. HCX never
            # receives authority to rewrite it; the actual caller receives
            # only its existing prompt and structured-response schema.
            "variation_control": {
                **request["variation_control"],
                "context_frame": remediation["context_frame"],
                "query_form": remediation["query_form"],
                "register": remediation["register"],
                "length": remediation["length_band"],
            },
        }
    )
    return request


def preservation_findings(remediation: dict[str, Any], request: dict[str, Any]) -> list[str]:
    """Compare 4B authority against the adapted v4 request before any call."""
    expected = control_snapshot(remediation)
    findings: list[str] = []
    if request.get("coverage_cell") != expected["coverage_cell"]:
        findings.append("coverage_cell_mismatch")
    if request.get("contract_lane") != expected["target_outcome"] or request.get("target_outcome", request.get("contract_lane")) != expected["outcome"]:
        findings.append("outcome_mismatch")
    semantic = request.get("semantic_request", {})
    host_contract = semantic.get("host_question_contract", {})
    if host_contract.get("canonical_requirement") != expected["canonical_requirement"]:
        findings.append("canonical_requirement_mismatch")
    if host_contract.get("subject") != expected["subject"]:
        findings.append("subject_mismatch")
    if host_contract.get("allowed_fields") != expected["allowed_fields"]:
        findings.append("allowed_fields_mismatch")
    if semantic.get("forbidden_fields") != expected["forbidden_fields"]:
        findings.append("forbidden_fields_mismatch")
    if [item["chunk_id"] for item in request.get("direct_evidence", [])] != expected["evidence_chunk_ids"]:
        findings.append("evidence_binding_mismatch")
    if [item["source_id"] for item in request.get("direct_evidence", [])] != expected["source_ids"]:
        findings.append("source_binding_mismatch")
    for field in ("context_frame", "query_form", "register", "length_band"):
        if request.get("remediation_control", {}).get(field) != expected[field]:
            findings.append(f"{field}_mismatch")
    if request.get("remediation_control", {}).get("bounded_diversity_profile") != expected.get("bounded_diversity_profile"):
        findings.append("bounded_diversity_profile_mismatch")
    if request.get("remediation_control", {}).get("bounded_linguistic_anchor") != expected.get("bounded_linguistic_anchor"):
        findings.append("bounded_linguistic_anchor_mismatch")
    if request.get("remediation_control", {}).get("host_question_renderer") != expected.get("host_question_renderer"):
        findings.append("host_question_renderer_mismatch")
    if request.get("remediation_control", {}).get("supported_answer_completeness") != expected.get("supported_answer_completeness"):
        findings.append("supported_answer_completeness_mismatch")
    for field in SEMANTIC_BOUNDARY_FIELDS:
        if request.get("remediation_control", {}).get(field) != expected[field]:
            findings.append(f"execution_control_mismatch:{field}")
    for field in LANE_CONTROL_FIELDS[remediation["target_outcome"]]:
        if host_contract.get(field) != expected[field]:
            findings.append(f"semantic_slot_mismatch:{field}")
        if request.get("remediation_control", {}).get(field) != expected[field]:
            findings.append(f"execution_control_mismatch:{field}")
    return sorted(set(findings))


def caller_input_for(request: dict[str, Any], previous_questions: list[str], retry_findings: list[str] | None = None) -> dict[str, Any]:
    """Build the existing v4 caller input while retaining host authority separately."""
    payload = build_payload(request, previous_questions, retry_findings)
    return {
        "prompt": payload["messages"][0]["content"],
        "response_schema": payload["responseFormat"]["schema"],
        "generation_parameters": {
            "temperature": payload["temperature"],
            "topP": payload.get("topP"),
            "maxTokens": payload["maxCompletionTokens"],
        },
        "host_control": deepcopy(request["remediation_control"]),
    }


def diversity_prompt_findings(remediation: dict[str, Any], caller_input: dict[str, Any]) -> list[str]:
    """Audit that every host diversity control is an active prompt rule."""
    expected_instruction = remediation_diversity_instruction(
        {
            "target_outcome": remediation["target_outcome"],
            "remediation_control": control_snapshot(remediation),
        }
    )
    prompt = caller_input["prompt"]
    if expected_instruction is None or expected_instruction not in prompt:
        return ["remediation_diversity_instruction_missing"]
    final_banmal_check = banmal_final_question_check_instruction(
        {
            "target_outcome": remediation["target_outcome"],
            "remediation_control": control_snapshot(remediation),
        }
    )
    if final_banmal_check is not None and final_banmal_check not in prompt:
        return ["banmal_final_question_check_missing"]
    completeness = remediation.get("supported_answer_completeness")
    if completeness is not None:
        markers = (
            "[P49-2H-4D-E2A supported answer completeness — host-owned]",
            f"canonical_requirement={completeness['canonical_requirement']}",
            "required_answer_terms=" + json.dumps(completeness["required_answer_terms"], ensure_ascii=False),
            "required_literal_quotes=" + json.dumps(completeness["required_literal_quotes"], ensure_ascii=False),
        )
        if any(marker not in prompt for marker in markers):
            return ["supported_answer_completeness_instruction_missing"]
    markers = [
        f"context_frame={remediation['context_frame']}:",
        f"query_form={remediation['query_form']}:",
        f"register={remediation['register']}:",
        f"length_band={remediation['length_band']}:",
    ]
    if remediation["register"] in BANMAL_REGISTERS:
        markers.extend(
            [
                f"banmal_subject_binding: subject={remediation['subject']}",
                f"banmal_register_surface={remediation['register']}:",
                f"banmal_final_question_check: subject={remediation['subject']}; register={remediation['register']}",
            ]
        )
    profile = remediation.get("bounded_diversity_profile")
    if profile is not None:
        markers.extend(
            [
                f"bounded_profile_id={profile['profile_id']}",
                f"user_situation_frame={profile['user_situation_frame']}:",
                f"speech_act={profile['speech_act']}:",
                f"information_gap_mode={profile['information_gap_mode']}:",
                f"temporal_expression={profile['temporal_expression']}:",
                f"misconception_type={profile['misconception_type']}:",
                f"sentence_shape={profile['sentence_shape']}:",
            ]
        )
    anchor = remediation.get("bounded_linguistic_anchor")
    if anchor is not None:
        markers.extend(
            [
                f"anchor_id={anchor['anchor_id']}",
                f"anchor_question={anchor['anchor_question']}",
                f"linguistic_archetype={anchor['linguistic_archetype']}",
            ]
        )
    return [f"remediation_diversity_control_missing:{marker.split('=', 1)[0]}" for marker in markers if marker not in prompt]


def field_boundary_prompt_findings(
    remediation: dict[str, Any],
    request: dict[str, Any],
    caller_input: dict[str, Any],
) -> list[str]:
    """Confirm a remediation supported field boundary is both preserved and active."""
    expected = control_snapshot(remediation)
    findings: list[str] = []
    semantic = request.get("semantic_request", {})
    contract = semantic.get("host_question_contract", {})
    if contract.get("allowed_fields") != expected["allowed_fields"]:
        findings.append("field_boundary_allowed_fields_mismatch")
    if semantic.get("forbidden_fields") != expected["forbidden_fields"]:
        findings.append("field_boundary_forbidden_fields_mismatch")
    instruction = remediation_field_boundary_instruction(request)
    if instruction is not None and instruction not in caller_input["prompt"]:
        findings.append("field_boundary_instruction_missing")
    return findings


def response_schema_findings(model: object, schema: dict[str, Any]) -> list[str]:
    """Check the existing lane schema before passing a response to v4 hydration."""
    if not isinstance(model, dict):
        return ["response_not_object"]
    findings: list[str] = []
    properties = schema.get("properties", {})
    for field in schema.get("required", []):
        if field not in model:
            findings.append(f"missing_response_field:{field}")
            continue
        expected_type = properties.get(field, {}).get("type")
        if expected_type == "string" and not isinstance(model[field], str):
            findings.append(f"invalid_response_type:{field}")
        elif expected_type == "object" and not isinstance(model[field], dict):
            findings.append(f"invalid_response_type:{field}")
        elif expected_type == "array" and not isinstance(model[field], list):
            findings.append(f"invalid_response_type:{field}")
    unexpected = set(model) - set(properties)
    if unexpected:
        findings.extend(f"unexpected_response_field:{field}" for field in sorted(unexpected))
    return sorted(set(findings))


def register_surface_and_subject_findings(remediation: dict[str, Any], request: dict[str, Any], question: str) -> list[str]:
    """Validate new banmal controls without weakening the semantic validator.

    ``그거 맞지?``-style wording is intentionally rejected when it drops the
    subject.  These findings apply only to the new two-register experiment;
    legacy artifacts retain their existing validation route unchanged.
    """
    register = remediation.get("register")
    if register not in BANMAL_REGISTERS:
        return []
    compact = "".join(question.lower().split())
    host = request["semantic_request"]["host_question_contract"]
    raw_subject = host["subject"]
    subject = raw_subject.replace("제도", "").replace("만기자금", "").strip()
    aliases = {"".join(item.lower().split()) for item in host.get("request_local_subject_aliases", [])}
    aliases.add("".join(subject.lower().split()))
    local_product_subject = subject.replace(" ", "") in {"해당상품", "이상품", "위상품"}
    if local_product_subject:
        aliases.update({"해당상품", "이상품", "이펀드", "이투자상품"})
    findings: list[str] = []
    if not any(alias and alias in compact for alias in aliases):
        findings.append("register_subject_loss")
    casual_markers = ("야?", "거야?", "맞아?", "돼?", "있어?", "해?", "될까?", "인가?")
    terse_markers = ("임?", "맞지?", "됨?", "몰라?", "있음?")
    expected_markers = casual_markers if register == "casual_banmal" else terse_markers
    if not any(compact.endswith(marker) for marker in expected_markers):
        findings.append("register_surface_drift")
    return findings


def trace_base(remediation: dict[str, Any], mode: str, preservation: list[str]) -> dict[str, Any]:
    return {
        "remediation_request_id": remediation["remediation_request_id"],
        "mode": mode,
        "coverage_cell": remediation["coverage_cell"],
        "outcome": remediation["target_outcome"],
        "adapter_preservation_pass": not preservation,
        "caller_input_preservation_pass": not preservation,
        "diversity_control_prompt_pass": False,
        "diversity_control_prompt_findings": [],
        "field_boundary_prompt_pass": False,
        "field_boundary_prompt_findings": [],
        "linguistic_anchor_review_status": remediation.get("bounded_linguistic_anchor", {}).get("human_review_status"),
        "preservation_findings": preservation,
        "external_call_attempted": False,
        "external_call_success": False,
        "attempt_count": 0,
        "response_schema_valid": False,
        "build_full_candidate_status": "not_started",
        "hydration_status": "not_started",
        "validator_executed": False,
        "validation_status": "not_evaluated",
        "validation_findings": [],
        "generation_status": "not_started",
    }


def execute_adapted_request(
    remediation: dict[str, Any],
    request: dict[str, Any],
    *,
    mode: str,
    generator: Any | None = None,
    corpus: dict[str, dict[str, Any]] | None = None,
    seed_questions: list[str] | None = None,
    comparison_questions: list[str] | None = None,
    max_generation_attempts: int = 3,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Run zero calls, one record, or the frozen 12-record smoke path."""
    if mode not in {"dry-run", "single-live", "twelve-smoke", "anchor-smoke", "register-tranche", "register-retest", "host-renderer-tranche", "supported-answer-repair", "supported-answer-neighbor-smoke", "register-additive-tranche", "batch-live", "g3b-human-tranche", "h-clarification-tranche", "i-supported-tranche"}:
        raise ValueError(f"unsupported 4C execution mode: {mode}")
    if not 1 <= max_generation_attempts <= 3:
        raise ValueError("max_generation_attempts must be within 1..3")

    preservation = preservation_findings(remediation, request)
    trace = trace_base(remediation, mode, preservation)
    if preservation:
        trace["generation_status"] = "preservation_failed"
        return trace, None

    caller_input = caller_input_for(request, comparison_questions or [])
    if caller_input["host_control"] != control_snapshot(remediation):
        trace["caller_input_preservation_pass"] = False
        trace["preservation_findings"] = ["caller_input_host_control_mismatch"]
        trace["generation_status"] = "preservation_failed"
        return trace, None
    diversity_findings = diversity_prompt_findings(remediation, caller_input)
    trace["diversity_control_prompt_pass"] = not diversity_findings
    trace["diversity_control_prompt_findings"] = diversity_findings
    if diversity_findings:
        trace["generation_status"] = "prompt_binding_failed"
        return trace, None
    boundary_findings = field_boundary_prompt_findings(remediation, request, caller_input)
    trace["field_boundary_prompt_pass"] = not boundary_findings
    trace["field_boundary_prompt_findings"] = boundary_findings
    if boundary_findings:
        trace["generation_status"] = "prompt_binding_failed"
        return trace, None
    anchor = remediation.get("bounded_linguistic_anchor")
    if mode != "dry-run" and anchor is not None and (
        anchor["authoring_status"] != "human_written"
        or anchor["human_review_status"] != "human_approved"
    ):
        trace["generation_status"] = "anchor_human_review_required"
        return trace, None
    if mode == "dry-run":
        trace["response_schema_valid"] = None
        trace["build_full_candidate_status"] = "not_called_dry_run"
        trace["hydration_status"] = "not_called_dry_run"
        trace["generation_status"] = "not_started"
        return trace, None
    if generator is None or corpus is None or seed_questions is None or comparison_questions is None:
        raise ValueError("live execution requires a generator, corpus, frozen seed questions, and comparison questions")

    previous_questions = list(comparison_questions)
    attempt_history: list[dict[str, Any]] = []
    candidate: dict[str, Any] | None = None
    final_findings: list[str] = []
    for attempt in range(1, max_generation_attempts + 1):
        caller_input = caller_input_for(request, previous_questions, final_findings or None)
        if caller_input["host_control"] != control_snapshot(remediation):
            trace["caller_input_preservation_pass"] = False
            trace["preservation_findings"] = ["caller_input_host_control_mismatch"]
            trace["generation_status"] = "preservation_failed"
            return trace, None
        diversity_findings = diversity_prompt_findings(remediation, caller_input)
        trace["diversity_control_prompt_pass"] = not diversity_findings
        trace["diversity_control_prompt_findings"] = diversity_findings
        if diversity_findings:
            trace["generation_status"] = "prompt_binding_failed"
            return trace, None
        boundary_findings = field_boundary_prompt_findings(remediation, request, caller_input)
        trace["field_boundary_prompt_pass"] = not boundary_findings
        trace["field_boundary_prompt_findings"] = boundary_findings
        if boundary_findings:
            trace["generation_status"] = "prompt_binding_failed"
            return trace, None
        trace["external_call_attempted"] = True
        trace["attempt_count"] = attempt
        try:
            model = generator.generate_structured(caller_input["prompt"], caller_input["response_schema"])
            trace["external_call_success"] = True
        except GenerationError:
            trace["generation_status"] = "generation_exhausted"
            trace["validation_status"] = "not_evaluated"
            return trace, None
        schema_findings = response_schema_findings(model, caller_input["response_schema"])
        if schema_findings:
            trace["response_schema_valid"] = False
            trace["validation_findings"] = schema_findings
            trace["generation_status"] = "generation_exhausted"
            return trace, None
        trace["response_schema_valid"] = True
        # build_full_candidate is the canonical v4 bridge. It invokes the
        # existing host_authority_bridge and hydrate_candidate exactly once.
        try:
            candidate = build_full_candidate(request, model, attempt=attempt)
        except (KeyError, ValueError) as exc:
            # A host-side bridge error is operational: the HCX response was
            # schema-valid, but canonical candidate construction did not
            # complete.  It is recorded separately from semantic quality and
            # never promotes a candidate.
            trace["build_full_candidate_status"] = "failed"
            trace["hydration_status"] = "failed"
            trace["validation_findings"] = [f"candidate_bridge_error:{exc}"]
            trace["validation_status"] = "not_evaluated"
            trace["generation_status"] = "candidate_bridge_failed"
            return trace, None
        trace["build_full_candidate_status"] = "success"
        trace["hydration_status"] = "success"
        candidate["generation_parameters"] = caller_input["generation_parameters"]
        final_findings = validation_findings_for_attempt(candidate, corpus, previous_questions, seed_questions)
        if request.get("remediation_control", {}).get("host_question_renderer", {}).get("renderer_id") == F_REGISTER_RENDERER_ID:
            final_findings.extend(f_register_surface_findings(
                candidate["question"], request["semantic_request"], request["remediation_control"],
            ))
        if request.get("remediation_control", {}).get("host_question_renderer", {}).get("renderer_id") == I1_RENDERER_ID:
            final_findings.extend(i1_surface_findings(candidate["question"], request["semantic_request"]))
        final_findings = sorted(set(
            final_findings
            + candidate.get("semantic_contract_findings", [])
            + register_surface_and_subject_findings(remediation, request, candidate["question"])
        ))
        attempt_history.append({"attempt": attempt, "validation_findings": final_findings})
        trace["validator_executed"] = True
        if not final_findings:
            break

    assert candidate is not None
    candidate["remediation_request_id"] = remediation["remediation_request_id"]
    candidate["full_request_id"] = remediation["remediation_request_id"]
    candidate["generation_attempt_history"] = attempt_history
    candidate["full_adapter_validation_route"] = "v4"
    candidate["validation_findings"] = final_findings
    if final_findings:
        # Reuse the P49-2H-4A operational contract: retry exhaustion is not a
        # quality-denominator failure and never promotes a candidate.
        candidate["generation_status"] = "generation_exhausted"
        candidate["generation_exhausted"] = True
        candidate["validation_status"] = "not_evaluated"
        candidate["candidate_lifecycle"]["state"] = "generation_exhausted"
        candidate["candidate_lifecycle"]["schema"] = "not_evaluated"
        candidate["candidate_lifecycle"]["evidence"] = "not_evaluated"
        candidate["candidate_lifecycle"]["semantic"] = "not_evaluated"
        candidate["candidate_lifecycle"]["dedup"] = "not_evaluated"
    else:
        candidate["generation_exhausted"] = False
        candidate["validation_status"] = "pass"
    trace["validation_findings"] = final_findings
    trace["validation_status"] = candidate["validation_status"]
    trace["generation_status"] = candidate["generation_status"]
    return trace, candidate


def select_remediation_records(
    rows: list[dict[str, Any]],
    request_id: str | None,
    *,
    live: bool,
    smoke_12: bool = False,
) -> list[dict[str, Any]]:
    """Select only a dry audit, one live ID, or the frozen balanced twelve."""
    selected = [row for row in rows if row["remediation_request_id"] in SMOKE_REQUEST_IDS]
    if len(selected) != len(SMOKE_REQUEST_IDS):
        raise ValueError("the frozen 4C smoke selection is incomplete")
    if not live:
        if smoke_12:
            raise ValueError("--smoke-12 requires --live")
        if request_id is None:
            return selected
        return [row for row in selected if row["remediation_request_id"] == request_id]
    if smoke_12:
        if request_id:
            raise ValueError("--smoke-12 cannot be combined with --request-id")
        return selected
    if not request_id:
        raise ValueError("--live requires exactly one --request-id")
    if request_id not in SMOKE_REQUEST_IDS:
        raise ValueError("--live request-id must be one of the frozen 12-record smoke selection")
    return [row for row in selected if row["remediation_request_id"] == request_id]


def _record_ref(row: dict[str, Any]) -> str:
    """Return the stable provenance identifier used in dedup diagnostics."""
    return str(row.get("remediation_request_id") or row.get("candidate_id") or row.get("record_id") or "unknown")


def _duplicate_groups(records: list[dict[str, str]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[str]] = {}
    for row in records:
        grouped.setdefault(row[key], []).append(row["record_ref"])
    return [
        {"question_key": question_key, "record_refs": record_refs}
        for question_key, record_refs in sorted(grouped.items())
        if len(record_refs) > 1
    ]


def full_set_dedup_audit(
    immutable_pass: list[dict[str, Any]],
    smoke_candidates: list[dict[str, Any]],
    frozen_seeds: list[dict[str, Any]],
) -> dict[str, Any]:
    """Audit the immutable 133 plus only fresh validated candidates.

    This mirrors the existing 0.88 trigram similarity rule and does not
    mutate candidate state, thresholds, or the frozen comparison artifacts.
    """
    new_pass = [row for row in smoke_candidates if row.get("validation_status") == "pass"]
    records = [
        {"record_ref": _record_ref(row), "question": row["question"], "normalized_question": normalized(row["question"])}
        for row in [*immutable_pass, *new_pass]
    ]
    exact_duplicates = _duplicate_groups(records, "question")
    normalized_duplicates = _duplicate_groups(records, "normalized_question")
    semantic_near_duplicates = [
        {
            "left": left["record_ref"],
            "right": right["record_ref"],
            "similarity": round(similarity(left["question"], right["question"]), 6),
        }
        for left, right in combinations(records, 2)
        if similarity(left["question"], right["question"]) >= 0.88
    ]
    frozen_seed_collisions = [
        {
            "candidate": candidate["record_ref"],
            "frozen_seed": _record_ref(seed),
            "similarity": round(similarity(candidate["question"], seed["question"]), 6),
        }
        for candidate in records
        for seed in frozen_seeds
        if similarity(candidate["question"], seed["question"]) >= 0.88
    ]
    return {
        "audit": "P49-2H-4C-4-full-set-dedup",
        "near_duplicate_threshold": 0.88,
        "immutable_pass_count": len(immutable_pass),
        "new_smoke_candidate_count": len(smoke_candidates),
        "new_pass_candidate_count": len(new_pass),
        "full_set_candidate_count": len(records),
        "frozen_seed_count": len(frozen_seeds),
        "exact_duplicates": exact_duplicates,
        "normalized_duplicates": normalized_duplicates,
        "semantic_near_duplicates": semantic_near_duplicates,
        "frozen_seed_collisions": frozen_seed_collisions,
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
        "smoke_candidates": [
            {
                "remediation_request_id": _record_ref(row),
                "validation_status": row.get("validation_status"),
                "generation_status": row.get("generation_status"),
            }
            for row in smoke_candidates
        ],
    }


def full_set_audit_verdict(audit: dict[str, Any]) -> str:
    """Return GO only for the declared 133 + exactly 12 fresh valid candidates."""
    valid_ids = {
        row["remediation_request_id"]
        for row in audit["smoke_candidates"]
        if row["validation_status"] == "pass"
    }
    is_clean = not any(
        audit[key]
        for key in ("exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions")
    )
    if (
        audit["immutable_pass_count"] == 133
        and audit["new_pass_candidate_count"] == len(SMOKE_REQUEST_IDS)
        and audit["full_set_candidate_count"] == 145
        and valid_ids == SMOKE_REQUEST_IDS
        and is_clean
    ):
        return "GO"
    return "NO-GO"


def write_full_set_audit(
    output: Path,
    immutable_pass: list[dict[str, Any]],
    smoke_candidates: list[dict[str, Any]],
    frozen_seeds: list[dict[str, Any]],
) -> dict[str, Any]:
    """Write a new immutable audit artifact; overwrite is deliberately refused."""
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing full-set audit: {output}")
    audit = full_set_dedup_audit(immutable_pass, smoke_candidates, frozen_seeds)
    audit["verdict"] = full_set_audit_verdict(audit)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return audit


def configured_generator() -> HCXStructuredAugmentationGenerator:
    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend.lower() != "hcx" or settings.hcx_model.upper() != "HCX-007" or not settings.hcx_api_key or not settings.hcx_base_url:
        raise RuntimeError("P49-2H-4C single-live requires configured HCX-007, HCX_API_KEY, and HCX_BASE_URL.")
    return HCXStructuredAugmentationGenerator(
        config=replace(settings, hcx_min_interval_seconds=max(settings.hcx_min_interval_seconds, 4.0))
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Allow one paid HCX-007 request, or the explicit frozen twelve-record smoke.")
    parser.add_argument("--smoke-12", action="store_true", help="With --live, execute exactly the frozen six clarification plus six bounded requests.")
    parser.add_argument("--request-id", help="Required with --live unless --smoke-12 is used; must be one frozen 4C smoke request ID.")
    parser.add_argument("--manifest", type=Path, default=REMEDIATION_MANIFEST)
    parser.add_argument("--semantic-requests", type=Path, default=SEMANTIC_REQUESTS)
    parser.add_argument("--comparison-pool", type=Path, default=COMPARISON_POOL)
    parser.add_argument("--trace-output", type=Path, default=TRACE_OUTPUT)
    parser.add_argument("--output", type=Path, default=SMOKE_OUTPUT)
    parser.add_argument("--audit-full-set", action="store_true", help="Run local-only 133 immutable + fresh smoke candidate dedup audit.")
    parser.add_argument(
        "--prior-candidates",
        type=Path,
        action="append",
        help="Validated prior P49-2H-4C-3 candidate JSONL included in retry dedup comparisons; no candidates are modified.",
    )
    parser.add_argument(
        "--audit-candidates",
        type=Path,
        action="append",
        help="Fresh P49-2H-4C-3 candidate JSONL used by --audit-full-set; repeat for retry artifacts.",
    )
    parser.add_argument(
        "--audit-output",
        type=Path,
        default=ROOT / "evaluation/fine_tuning/p49_2h_4c_4_full_set_dedup_v1.json",
        help="New JSON audit artifact; existing files are never overwritten.",
    )
    parser.add_argument("--max-generation-attempts", type=int, default=3)
    args = parser.parse_args()

    if args.audit_full_set:
        if args.live or args.smoke_12 or args.request_id or args.prior_candidates:
            parser.error("--audit-full-set is local-only and cannot be combined with live execution options")
        if args.audit_candidates is None:
            parser.error("--audit-full-set requires --audit-candidates")
        immutable_pass = [row for row in read_jsonl(args.comparison_pool) if row.get("validation_status") == "pass"]
        audit_candidates = [row for path in args.audit_candidates for row in read_jsonl(path)]
        audit = write_full_set_audit(
            args.audit_output,
            immutable_pass,
            audit_candidates,
            read_jsonl(FROZEN_SEED),
        )
        print(
            json.dumps(
                {
                    "mode": "full-set-dedup-audit",
                    "immutable_pass": audit["immutable_pass_count"],
                    "new_pass": audit["new_pass_candidate_count"],
                    "full_set": audit["full_set_candidate_count"],
                    "exact_duplicates": len(audit["exact_duplicates"]),
                    "normalized_duplicates": len(audit["normalized_duplicates"]),
                    "semantic_near_duplicates": len(audit["semantic_near_duplicates"]),
                    "frozen_seed_collisions": len(audit["frozen_seed_collisions"]),
                    "verdict": audit["verdict"],
                    "audit_output": str(args.audit_output),
                },
                ensure_ascii=False,
            )
        )
        return

    if args.smoke_12 and not args.live:
        parser.error("--smoke-12 requires --live")
    if args.live and not (args.request_id or args.smoke_12):
        parser.error("--live requires exactly one --request-id unless --smoke-12 is used")
    if args.live and args.smoke_12 and args.request_id:
        parser.error("--smoke-12 cannot be combined with --request-id")
    mode = "twelve-smoke" if args.smoke_12 else "single-live" if args.live else "dry-run"
    remediation = select_remediation_records(
        read_jsonl(args.manifest),
        args.request_id,
        live=args.live,
        smoke_12=args.smoke_12,
    )
    semantic_rows = read_jsonl(args.semantic_requests)
    comparison = validated_questions(read_jsonl(args.comparison_pool))
    if args.prior_candidates is not None:
        if not args.live:
            parser.error("--prior-candidates is valid only with --live retry execution")
        comparison.extend(question for path in args.prior_candidates for question in validated_questions(read_jsonl(path)))
    generator = configured_generator() if args.live else None
    corpus = {row["chunk_id"]: row for row in read_jsonl(CORPUS)} if args.live else None
    seed_questions = [row["question"] for row in read_jsonl(FROZEN_SEED)] if args.live else None

    traces: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for row in remediation:
        adapted = adapt_remediation_record(row, semantic_rows)
        trace, candidate = execute_adapted_request(
            row,
            adapted,
            mode=mode,
            generator=generator,
            corpus=corpus,
            seed_questions=seed_questions,
            comparison_questions=comparison,
            max_generation_attempts=args.max_generation_attempts,
        )
        traces.append(trace)
        if candidate is not None:
            candidates.append(candidate)
            # Every earlier fresh PASS becomes a comparison input for the
            # next record in the explicit 12-record smoke. This retains the
            # existing validator and the same 0.88 threshold while catching
            # new-to-new collisions before the aggregate audit.
            if candidate.get("validation_status") == "pass":
                comparison.append(candidate["question"])

    append_jsonl(args.trace_output, traces)
    if args.live:
        append_jsonl(args.output, candidates)
    print(
        json.dumps(
            {
                "mode": mode,
                "records": len(remediation),
                "external_hcx_calls_attempted": sum(trace["attempt_count"] for trace in traces),
                "preservation_pass": sum(trace["caller_input_preservation_pass"] for trace in traces),
                "diversity_prompt_pass": sum(trace["diversity_control_prompt_pass"] for trace in traces),
                "trace_output": str(args.trace_output),
                "candidate_output": str(args.output) if args.live else None,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
