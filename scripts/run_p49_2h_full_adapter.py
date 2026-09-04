"""P49-2H-3E thin full-run adapter for the frozen P49-2H-3D contract.

This is deliberately *not* the legacy 3B runner.  It schedules a 700-record
manifest, but delegates all natural-language generation, host-owned hydration,
and semantic validation to the exact v4 micro-pilot functions.  Until an
explicit six-record smoke succeeds, ``--execute`` refuses a larger request.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_p49_2h_contract_split_micro_pilot import (  # v4 authority; never copy policy here
    build_payload,
    hydrate_candidate,
    read_jsonl,
    validation_findings_for_attempt,
)
from scripts.prepare_p49_2h_contract_split_micro_pilot import ANSWER_CONTRACTS
from scripts.validate_p49_2h_contract_split_micro_pilot import CORPUS, FROZEN_SEED, read_jsonl as read_validation_jsonl
from scripts.p49_2h_register_taxonomy import BANMAL_REGISTERS
from scripts.p49_2h_4d_e2_host_renderer import RENDERER_ID as E2_RENDERER_ID, render_host_question as render_e2_host_question
from scripts.p49_2h_4d_f_host_renderer import RENDERER_ID as F_RENDERER_ID, render_host_question as render_f_host_question
from scripts.p49_2h_4d_i1_supported_host_renderer import RENDERER_ID as I1_RENDERER_ID, render_host_question as render_i1_host_question
from src.augmentation.candidate_builder import build_candidate
from src.augmentation.candidate_schema import GeneratedAugmentationText, HostOwnedAugmentationRequest
from src.augmentation.hcx_structured_generator import HCXStructuredAugmentationGenerator
from src.config.generation import GenerationSettings


LANE_TARGETS = {"supported_answer": 450, "clarification_required": 125, "bounded_answer": 125}
SMOKE_LANE_TARGETS = {"supported_answer": 2, "clarification_required": 2, "bounded_answer": 2}
PROMPT_VERSION = "p49-2h-3d-v4-full-adapter-v1"
SEMANTIC_REQUESTS = ROOT / "evaluation/fine_tuning/p49_2h_full_semantic_requests_v1.jsonl"


def semantic_to_v4_request(semantic: dict) -> dict:
    """Bridge one 3F host contract into the unmodified v4 lane interface."""
    host, lane = semantic["host_question_contract"], semantic["target_outcome"]
    request = {
        "full_request_id": semantic["full_request_id"], "micro_request_id": semantic["full_request_id"],
        "contract_lane": lane, "source_seed_id": semantic.get("source_seed_id"),
        "question_type": semantic["question_type"], "factual_domain": semantic["factual_domain"],
        "pool_id": semantic["pool_id"], "coverage_cell": semantic["coverage_cell"],
        "augmentation_type": f"{semantic['question_type']}:semantic_contract",
        "variation_control": {"register": host["question_register"], "length": host["question_length_band"], "query_form": host["question_intent_type"], "lexical_constraint": "host semantic contract only"},
        "semantic_focus": host.get("canonical_requirement") or (semantic["supported_requirements"][0]["canonical_requirement"] if semantic["supported_requirements"] else None),
        "requirements": semantic["requirements"], "direct_evidence": semantic["direct_evidence"],
        "literal_evidence_quotes": semantic["literal_evidence_quotes"], "field_constraints": semantic["forbidden_fields"],
        "table_fields": [], "numeric_anchors": [], "semantic_request": semantic,
        "answer_contract": ANSWER_CONTRACTS.get(
            host.get("canonical_requirement") or (semantic["supported_requirements"][0]["canonical_requirement"] if semantic["supported_requirements"] else ""),
            {"required_terms": semantic["literal_evidence_quotes"][:1], "forbidden_terms": [], "unsupported_caveat_terms": []},
        ),
    }
    if lane == "clarification_required":
        request["missing_conditions"] = semantic["missing_conditions"]
        request["decision_target"] = semantic["decision_target"]
        request["scenario_context"] = semantic["scenario_context"]
        request["user_question_scenario"] = f"{semantic['scenario_context']}. {semantic['decision_target']}을 묻되 {', '.join(semantic['missing_conditions'])}에 따라 판단이 달라지는지 알고 싶은 사용자 질문"
    elif lane == "bounded_answer":
        request["supported_requirements"] = semantic["supported_requirements"]
        request["unsupported_requirements"] = semantic["unsupported_requirements"]
        request["unsupported_target"] = semantic["unsupported_target"]
        # NONE has no supported factual portion.  Do not accidentally inherit
        # a literal quote from optional context as a required answer term.
        request["supported_answer_required_terms"] = (
            request["answer_contract"]["required_terms"]
            if semantic["supported_requirements"] else []
        )
        request["user_question_scenario"] = f"{host['subject']}의 {semantic['unsupported_target']}을(를) 구체적으로 묻는 사용자 질문"
    return request


def semantic_question_findings(question: str, semantic: dict) -> list[str]:
    """Fail closed when HCX wording loses host-owned question semantics."""
    compact = "".join(question.lower().split())
    lane, host = semantic["target_outcome"], semantic["host_question_contract"]
    findings: list[str] = []
    subject = host["subject"].replace("제도", "").replace("만기자금", "").strip()
    aliases = {"".join(alias.lower().split()) for alias in host.get("request_local_subject_aliases", [])}
    aliases.add("".join(subject.lower().split()))
    local_aliases = {"해당상품", "이상품", "위상품"}
    if subject.replace(" ", "") not in local_aliases and aliases and not any(alias in compact for alias in aliases):
        findings.append("semantic_subject_mismatch")
    scope = host.get("canonical_requirement")
    if lane != "clarification_required":
        # product.total_fee has a deliberately narrow exception: its own
        # target marker (총보수/총보수율) must not be inferred from a
        # forbidden-field *description* and then rejected.  Preserve the
        # boundary by checking concrete adjacent fee fields instead.  This
        # does not alter product.period_cost or any other requirement.
        if scope == "product.total_fee":
            adjacent_fee_markers = (
                "기간별 비용",
                "기간 비용",
                "1,000만원",
                "1천만원",
                "1년 비용",
                "판매보수",
                "판매 수수료",
                "판매수수료",
                "회사 판매 보상",
                "company sales compensation",
            )
            if any(marker in question.lower() for marker in adjacent_fee_markers):
                findings.append("semantic_forbidden_field_expansion")
        else:
            forbidden_terms = set()
            for constraint in semantic.get("forbidden_fields", []):
                for term in ("DB", "DC", "IRP", "연금저축", "총보수", "기간별 비용", "60일", "300만원", "900만원"):
                    if term in constraint:
                        forbidden_terms.add(term)
            allowed_subject = host["subject"]
            allowed_target = (host.get("target_type", "") + " " + " ".join(semantic.get("allowed_fields", []))).replace("율", "")
            for term in forbidden_terms:
                if term in question and term not in allowed_subject and term.replace("율", "") not in allowed_target:
                    findings.append("semantic_forbidden_field_expansion")
    if lane == "bounded_answer":
        target = semantic["unsupported_target"]
        future = ("내년", "미래", "앞으로", "다음", "향후", "예측", "언제", "몇")
        if not any(token in question for token in future):
            findings.append("bounded_temporal_drift")
        target_type = host["target_type"]
        if ("위험" in target_type and "위험" not in question) or ("총보수" in target_type and "총보수" not in question) or ("세액" in target_type and not any(token in question for token in ("세액", "공제", "한도"))):
            findings.append("bounded_target_type_drift")
        concrete = ("몇", "얼마", "언제", "수치", "비율", "등급", "한도", "날짜", "시점")
        if not any(token in question for token in concrete):
            findings.append("bounded_concreteness_drift")
    elif lane == "clarification_required":
        decision = ("어떤", "어느", "추천", "유리", "가능", "어떻게", "할지", "될까", "여부", "처리", "선택")
        dependency = ("따라", "경우", "달라", "여부")
        generic = ("고려할 사항", "일반적으로 어떻게", "절차", "필요한 서류")
        if not any(token in question for token in decision) or not any(token in question for token in dependency) or any(token in question for token in generic):
            findings.append("clarification_missing_condition_drift")
    else:
        scope = host["canonical_requirement"]
        scope_markers = {
            "DB.operation_party": ("운용", "굴리"), "DB.benefit_determination": ("급여", "계산", "산정"),
            "DC.operation_party": ("운용", "굴리"), "DC.employer_contribution": ("부담금", "임금", "기여"),
            "product.total_fee": ("총보수",), "product.period_cost": ("비용", "기간"),
        }.get(scope, ())
        if scope_markers and not any("".join(marker.lower().split()) in compact for marker in scope_markers):
            findings.append("supported_question_scope_drift")
    return sorted(set(findings))


def full_requests(templates: list[dict]) -> list[dict]:
    """Expand frozen v4 request contracts without changing their semantics."""
    by_lane: dict[str, list[dict]] = defaultdict(list)
    for row in templates:
        by_lane[row["contract_lane"]].append(row)
    if set(by_lane) != set(LANE_TARGETS):
        raise ValueError("v4 templates must provide all three outcome lanes")
    requests: list[dict] = []
    index = 1
    for lane, target in LANE_TARGETS.items():
        rows = by_lane[lane]
        for offset in range(target):
            template = rows[offset % len(rows)]
            request_id = f"P49-2H-FULL-{index:04d}"
            # JSON cloning prevents a retry/full-run marker from mutating a
            # frozen micro request in memory.
            row = json.loads(json.dumps(template, ensure_ascii=False))
            row["full_request_id"] = request_id
            row["micro_request_id"] = request_id  # v4 validator's canonical request key
            row["generation_status"] = "not_started"
            row["generation_prompt_version"] = PROMPT_VERSION
            requests.append(row)
            index += 1
    counts = Counter(row["contract_lane"] for row in requests)
    if dict(counts) != LANE_TARGETS or len({row["full_request_id"] for row in requests}) != 700:
        raise AssertionError("full request manifest violated the frozen 450/125/125 contract")
    return requests


def host_authority_bridge(request: dict, model: dict) -> None:
    """Exercise the structured-generator/schema/builder authority boundary.

    The v4 lane schemas deliberately contain richer temporary fields.  This
    bridge normalizes only their model-owned natural text and validates it via
    the common augmentation modules before v4 hydration owns the completion.
    Its return value is intentionally discarded: candidate provenance and
    outcome continue to be owned by the v4 request/host contract.
    """
    answer = model.get("answer_text") or model.get("supported_answer_text")
    if not answer:
        answer = " ".join(model.get("clarification_questions", [])) or "host-owned clarification"
    generated = GeneratedAugmentationText.from_mapping({
        "question": model["question"], "answer": answer,
        "coverage_tags": [request["question_type"]],
        "augmentation_type": request["augmentation_type"],
    })
    host = HostOwnedAugmentationRequest(
        candidate_id=request["full_request_id"], coverage_cell=request["coverage_cell"],
        target_outcome=request["contract_lane"],
        evidence_chunk_ids=tuple(item["chunk_id"] for item in request["direct_evidence"]),
        source_ids=tuple(item["source_id"] for item in request["direct_evidence"]),
        source_seed_id=request["source_seed_id"], generation_prompt_version=PROMPT_VERSION,
        allowed_coverage_tags=(request["question_type"],),
        allowed_augmentation_types=(request["augmentation_type"],),
    )
    build_candidate(host, generated)


def bounded_host_question(semantic: dict, remediation_control: dict | None = None) -> str:
    """Render immutable future/target/concreteness slots for bounded lanes.

    The frozen full-run route keeps its original renderer.  A 4B remediation
    request additionally supplies host-owned diversity controls, so its final
    host-rendered question—not merely the discarded model draft—must reflect
    the requested user situation and question form.
    """
    host = semantic["host_question_contract"]
    subject, target = host["subject"], host["target_type"]
    if target == "미래 값":
        target = "수익률이나 위험등급"
    if remediation_control:
        # A reviewed linguistic anchor is host-owned wording, not model-owned
        # content.  The bridge has already required human_written plus
        # human_approved before a live call.  Reusing it here means the
        # canonical v4 candidate keeps the approved anchor instead of
        # discarding it after HCX responds.
        anchor = remediation_control.get("bounded_linguistic_anchor")
        if anchor is not None:
            return anchor["anchor_question"]
        context_clauses = {
            "이직/퇴직 직후": "퇴직 직후 계좌 이전을 검토하면서",
            "이전 신청 중": "계좌 이전 신청을 진행하면서",
            "상담 전 확인": "상담 전에",
            "상품 비교 전 확인": "상품 비교 전에",
            "세액공제 계산 전": "세액공제 계산 전에",
            "서류 준비 중": "서류 준비를 하면서",
            "공시자료 검토 중": "공시자료를 검토하면서",
            "계약 체결 직전": "계약 체결 직전에",
            "정기 점검 중": "정기 점검을 하면서",
            "운용 변경 안내 확인 중": "운용 변경 안내를 확인하면서",
            "장기 보유 계획 중": "장기 보유 계획을 세우면서",
            "연말 자금 계획 중": "연말 자금 계획을 세우면서",
        }
        form_endings = {
            "direct": "얼마인가요?",
            "confirmation": "이미 정해져 있나요?",
            "misconception": "이미 정해져 있다고 봐도 되나요?",
            "conditional": "어떤 조건에서 달라지나요?",
            "numeric": "얼마인가요?",
            "evidence_limit": "제공 자료만으로 알 수 있나요?",
            "planning_check": "지금 정해진 정보인가요?",
            "assumption_check": "이미 확정된 값인가요?",
        }
        try:
            context = context_clauses[remediation_control["context_frame"]]
            ending = form_endings[remediation_control["query_form"]]
        except KeyError as exc:
            raise ValueError(f"unsupported remediation bounded diversity control: {exc.args[0]}") from exc
        register = remediation_control.get("register")
        if register in BANMAL_REGISTERS:
            casual_endings = {
                "direct": "얼마야?",
                "confirmation": "이미 정해진 거야?",
                "misconception": "이미 정해진 거라고 봐도 돼?",
                "conditional": "어떤 조건에서 달라져?",
                "numeric": "얼마야?",
                "evidence_limit": "제공 자료만으로 알 수 있어?",
                "planning_check": "지금 정해진 정보야?",
                "assumption_check": "이미 확정된 값이야?",
            }
            terse_endings = {
                "direct": "얼마임?",
                "confirmation": "이미 정해진 거임?",
                "misconception": "이미 정해진 거 맞지?",
                "conditional": "어떤 조건에서 달라짐?",
                "numeric": "얼마임?",
                "evidence_limit": "제공 자료만으로 알 수 있음?",
                "planning_check": "지금 정해진 정보임?",
                "assumption_check": "이미 확정된 값임?",
            }
            ending = (casual_endings if register == "casual_banmal" else terse_endings)[remediation_control["query_form"]]
        # ``unsupported_target`` remains the authority for temporal scope and
        # target type; no product, value, or requirement is invented here.
        return f"{context} {subject}의 {semantic['unsupported_target']} 관련 수치는 {ending}"
    slot = int(semantic["full_request_id"].rsplit("-", 1)[-1]) % 3
    value_form = "몇 등급" if "위험" in target else ("몇 %" if "보수" in target else "얼마")
    variants = (
        f"{subject}의 향후 {target}은 {value_form}인가요?",
        f"{subject}에 앞으로 적용될 {target} 수치는 얼마인가요?",
        f"{subject}의 향후 {target}에 대한 구체적인 비율·수치를 알려주세요.",
    )
    return variants[slot]


def build_full_candidate(request: dict, model: dict, *, attempt: int = 1) -> dict:
    """Single shared v4 path used by tests, smoke, and eventual full execution."""
    host_authority_bridge(request, model)
    candidate = hydrate_candidate(
        request, model, generation_attempt=attempt,
        generation_prompt_version=PROMPT_VERSION,
        use_model_question=True,
    )
    semantic = request.get("semantic_request")
    if semantic:
        renderer = request.get("remediation_control", {}).get("host_question_renderer")
        if renderer is not None:
            # HCX continues to exercise the existing schema/caller route, but
            # E2 makes only the final user-facing question host-owned. Keep
            # the HCX draft for audit without giving it semantic authority.
            candidate["model_question_raw"] = model["question"]
            if renderer.get("renderer_id") == E2_RENDERER_ID:
                candidate["question"] = render_e2_host_question(semantic, request["remediation_control"])
            elif renderer.get("renderer_id") == F_RENDERER_ID:
                candidate["question"] = render_f_host_question(semantic, request["remediation_control"])
            elif renderer.get("renderer_id") == I1_RENDERER_ID:
                candidate["question"] = render_i1_host_question(semantic, request["remediation_control"])
            else:
                raise ValueError("unknown host question renderer")
            candidate["question_renderer"] = {**renderer, "authority": "host_owned"}
        if semantic["target_outcome"] == "bounded_answer" and semantic["host_question_contract"].get("concreteness_requirement"):
            # A reviewed bounded anchor is host-owned wording.  Keep the HCX
            # draft for audit, but never let it replace that final question.
            # This is deliberately limited to the existing bounded canonical
            # bridge so hydration and validation still follow the v4 path.
            if request.get("remediation_control", {}).get("bounded_linguistic_anchor") is not None:
                candidate["model_question_raw"] = model["question"]
                candidate["question_renderer"] = {
                    "authority": "host_owned_human_approved_bounded_anchor",
                    "renderer_id": "bounded_host_question",
                }
            candidate["question"] = bounded_host_question(semantic, request.get("remediation_control"))
        candidate["semantic_request_id"] = semantic["full_request_id"]
        candidate["host_question_contract"] = semantic["host_question_contract"]
        candidate["semantic_contract_findings"] = semantic_question_findings(candidate["question"], semantic)
    return candidate


def select_requests(requests: list[dict], completed: set[str], requested_ids: str | None, max_requests: int) -> list[dict]:
    remaining = [row for row in requests if row["full_request_id"] not in completed]
    if requested_ids:
        wanted = [item.strip() for item in requested_ids.split(",") if item.strip()]
        found = {row["full_request_id"]: row for row in remaining}
        unknown = [item for item in wanted if item not in found]
        if unknown:
            raise ValueError("unknown or completed full request IDs: " + ", ".join(unknown))
        if len(wanted) > max_requests:
            raise ValueError("--request-ids exceeds --max-requests")
        return [found[item] for item in wanted]
    return remaining[:max_requests]


def dry_run_manifest(requests: list[dict]) -> dict:
    counts = Counter(row["contract_lane"] for row in requests)
    return {
        "stage": "P49-2H-3E Full-Run Adapter dry run",
        "request_count": len(requests), "lane_targets": LANE_TARGETS,
        "lane_actual": dict(counts),
        "host_assembly": "scripts.run_p49_2h_contract_split_micro_pilot.hydrate_candidate",
        "validator": "scripts.validate_p49_2h_contract_split_micro_pilot.validate",
        "legacy_3b_runner_used": False,
        "training_export_allowed": False, "tuning_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--semantic-requests", type=Path, default=SEMANTIC_REQUESTS)
    parser.add_argument("--manifest-output", type=Path, default=ROOT / "evaluation/fine_tuning/p49_2h_full_run_requests_v1.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/fine_tuning/p49_2h_full_run_raw_v1.jsonl")
    parser.add_argument("--execute", action="store_true", help="Required for paid HCX-007 calls.")
    parser.add_argument("--request-ids", help="Explicit comma-separated full_request_id values.")
    parser.add_argument("--max-requests", type=int, default=0, help="0 is dry-run; paid smoke allows at most six.")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-generation-attempts", type=int, default=3, help="Bounded v4 retry limit; failed attempts retain provenance.")
    parser.add_argument("--unlock-full-after-smoke", action="store_true", help="Requires a successful six-record v4 smoke manifest before any run over six requests.")
    parser.add_argument("--smoke-validation-manifest", type=Path, help="Validated 2/2/2 smoke manifest required with --unlock-full-after-smoke.")
    args = parser.parse_args()

    semantic_rows = read_jsonl(args.semantic_requests)
    if len(semantic_rows) != 700:
        parser.error("3F semantic manifest must contain exactly 700 requests")
    requests = [semantic_to_v4_request(row) for row in semantic_rows]
    args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in requests), encoding="utf-8")
    dry = dry_run_manifest(requests)
    if not args.execute:
        print(json.dumps(dry, ensure_ascii=False, indent=2))
        return
    if args.unlock_full_after_smoke:
        if not args.smoke_validation_manifest or not args.smoke_validation_manifest.exists():
            parser.error("--unlock-full-after-smoke requires an existing --smoke-validation-manifest")
        smoke = json.loads(args.smoke_validation_manifest.read_text(encoding="utf-8"))
        expected_smoke = {"supported_answer": {"total": 2, "pass": 2}, "clarification_required": {"total": 2, "pass": 2}, "bounded_answer": {"total": 2, "pass": 2}}
        if smoke.get("record_count") != 6 or smoke.get("validation_fail_count") != 0 or smoke.get("lane_results") != expected_smoke:
            parser.error("smoke manifest is not a 2/2/2 all-pass v4 validation result")
        if not 1 <= args.max_requests <= 700:
            parser.error("--max-requests must be within 1..700 after smoke unlock")
    elif not 1 <= args.max_requests <= 6:
        parser.error("P49-2H-3E permits only a 1..6 request external smoke; full 700 remains locked.")
    if args.output.exists() and not args.resume:
        parser.error("Output exists. Use --resume or a new output path.")
    if not 1 <= args.max_generation_attempts <= 3:
        parser.error("--max-generation-attempts must be within 1..3")

    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend.lower() != "hcx" or settings.hcx_model.upper() != "HCX-007" or not settings.hcx_api_key or not settings.hcx_base_url:
        raise RuntimeError("P49-2H-3E smoke requires HCX-007, HCX_API_KEY, and HCX_BASE_URL.")
    settings = replace(settings, hcx_min_interval_seconds=max(settings.hcx_min_interval_seconds, 4.0))
    existing = read_jsonl(args.output) if args.output.exists() else []
    completed = {row.get("micro_request_id") for row in existing if row.get("generation_status") == "generated"}
    selected = select_requests(requests, completed, args.request_ids, args.max_requests)
    expected = Counter(row["contract_lane"] for row in selected)
    if len(selected) == 6 and dict(expected) != SMOKE_LANE_TARGETS:
        parser.error("six-record smoke must be exactly supported 2 / clarification 2 / bounded 2")
    generator = HCXStructuredAugmentationGenerator(config=settings)
    corpus = {row["chunk_id"]: row for row in read_validation_jsonl(CORPUS)}
    seed_questions = [row["question"] for row in read_validation_jsonl(FROZEN_SEED)]
    previous_questions = [row.get("question", "") for row in existing]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for request in selected:
        findings: list[str] = []
        attempts: list[dict] = []
        candidate: dict | None = None
        for attempt in range(1, args.max_generation_attempts + 1):
            payload = build_payload(request, previous_questions, findings or None)
            model = generator.generate_structured(payload["messages"][0]["content"], payload["responseFormat"]["schema"])
            candidate = build_full_candidate(request, model, attempt=attempt)
            candidate["generation_parameters"] = {"temperature": payload["temperature"], "topP": payload.get("topP"), "maxTokens": payload["maxCompletionTokens"]}
            findings = validation_findings_for_attempt(candidate, corpus, previous_questions, seed_questions)
            findings = sorted(set(findings + candidate.get("semantic_contract_findings", [])))
            attempts.append({"attempt": attempt, "validation_findings": findings})
            if not findings:
                break
        assert candidate is not None
        candidate["full_request_id"] = request["full_request_id"]
        candidate["generation_attempt_history"] = attempts
        candidate["validation_failures"] = findings
        candidate["full_adapter_validation_route"] = "v4"
        if findings:
            candidate["generation_status"] = "generation_exhausted"
            candidate["generation_exhausted"] = True
        else:
            candidate["generation_exhausted"] = False
        with args.output.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(candidate, ensure_ascii=False) + "\n")
        previous_questions.append(candidate["question"])
        print(json.dumps({"full_request_id": request["full_request_id"], "outcome": request["contract_lane"], "findings": findings}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
