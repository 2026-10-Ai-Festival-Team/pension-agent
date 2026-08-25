"""Attribute P35 pre-HCX failures without changing the candidate Agent.

P35 was a fresh holdout at execution time and is a development/regression set
after its pre-HCX No-Go.  This script only replays the shared deterministic
``prepare`` path with ``FakeGenerator``.  It never invokes HCX, never writes
the frozen P35 execution artifact, and binds manual source-relevance decisions
to the exact selected chunk IDs from that frozen execution.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evaluate_p34_closed_pre_hcx import _manifest_hash
from src.experiments.p27d_structured_output import P27DStructuredOutputAgent
from src.generation.fake import FakeGenerator
from src.orchestration.retrieval_service import build_frozen_retriever


PRIMARY_OWNERS = (
    "normalization_alias_miss",
    "normalization_semantic_miss",
    "planner_intent_miss",
    "planner_slot_miss",
    "planner_multi_requirement_miss",
    "planner_schema_variant",
    "subject_resolution",
    "retrieval_missing",
    "matcher_field_miss",
    "evidence_selection_miss",
)


# This is a manual *diagnostic* adjudication, not routing behaviour.  Every
# entry names the earliest observed break in the frozen P35 trace.  Keeping it
# here makes the conclusion reviewable without adding P35-specific behaviour to
# production code.
FAILURE_AUDITS = {
    "P35-001": {
        "primary_owner": "normalization_semantic_miss",
        "raw_terms": ["회사가 돈을 굴려주는 쪽"],
        "canonical_terms": ["DB·DC operation_party"],
        "missing_normalization": ["굴려주는 쪽 → 적립금 운용 주체"],
        "missing_requirements": ["DB·DC 운용 주체"],
        "secondary_effects": ["planner_multi_requirement_miss: benefit slots만 생성되어 operation slot이 빠짐"],
        "reason": "DB/DC와 급여 계산은 인식해 benefit plan을 만들었지만, 구어체 ‘돈을 굴려주는 쪽’이 operation_party로 정규화되지 않아 운용 주체 requirement가 생성되지 않았다.",
    },
    "P35-004": {
        "primary_owner": "normalization_alias_miss",
        "raw_terms": ["연저"],
        "canonical_terms": ["연금저축"],
        "missing_normalization": ["연저 → 연금저축"],
        "missing_requirements": ["연금저축 단독 세액공제 대상 한도", "IRP 포함 합산 세액공제 대상 한도"],
        "secondary_effects": ["planner_intent_miss: 연금저축+IRP 비교 predicate가 충족되지 않음", "gate_false_reject"],
        "reason": "현재 entity extraction은 ‘연금저축’만 account로 인식한다. IRP만 추출된 상태에서는 연금저축·IRP 한도 비교 schema의 두 account predicate가 성립하지 않는다.",
    },
    "P35-005": {
        "primary_owner": "normalization_semantic_miss",
        "raw_terms": ["세금을 나중에 낸다", "세금이 없어지는 것인가요"],
        "canonical_terms": ["tax_deferral", "일반계좌 대비 연금계좌 과세 시점"],
        "missing_normalization": ["세금을 나중에 낸다 → 과세이연"],
        "missing_requirements": ["일반계좌 과세 시점", "연금계좌 과세이연의 조건·시점"],
        "secondary_effects": ["planner_intent_miss: tax_deferral comparison plan 미생성"],
        "reason": "질문은 면제와 과세시점 이연을 구분하지만 현재 canonical form은 ‘과세이연’ intent로 바꾸지 못해 simple retrieval 경로로 남았다.",
    },
    "P35-007": {
        "primary_owner": "matcher_field_miss",
        "raw_terms": [],
        "canonical_terms": [],
        "missing_normalization": [],
        "missing_requirements": [],
        "secondary_effects": ["source_relevance_wrong_scope", "evidence_selection_contains_wrong_scope_context"],
        "reason": "연금저축·IRP 인출 비교 plan과 gold withdrawal chunks는 모두 candidate에 있다. 그러나 matcher의 넓은 인출/과세 term이 DC 해외 ETF 과세 문장과 일반 DB/DC 문단을 선택해 IRP 법정사유·계좌별 과세 requirement를 잘못 충족으로 판단했다.",
    },
    "P35-008": {
        "primary_owner": "normalization_semantic_miss",
        "raw_terms": ["중간에 찾기", "증명 서류"],
        "canonical_terms": ["중도인출", "중도인출 신청·증빙"],
        "missing_normalization": ["중간에 찾기 → 중도인출", "증명 서류 → 증빙서류"],
        "missing_requirements": ["DC 중도인출 가능 사유", "신청 절차·증빙"],
        "secondary_effects": ["planner_multi_requirement_miss: withdrawal procedure schema 미생성"],
        "reason": "현재 normalization은 ‘중간에 꺼내/빼’만 중도인출로 바꾸며 ‘중간에 찾기’와 ‘증명 서류’를 canonical withdrawal-procedure 표현으로 바꾸지 못한다.",
    },
    "P35-009": {
        "primary_owner": "normalization_semantic_miss",
        "raw_terms": ["넘길"],
        "canonical_terms": ["ISA 만기 이전/전환"],
        "missing_normalization": ["넘길 → 이전 또는 전환"],
        "missing_requirements": ["ISA 만기자금 이전 기한", "추가 세액공제 계산 기준·한도"],
        "secondary_effects": ["planner_intent_miss: ISA maturity transfer plan 미생성", "normalization_alias_miss: 연저 미정규화는 존재하지만 IRP entity가 있어 최초 차단 원인은 아님"],
        "reason": "IRP entity가 이미 추출되어 account scope는 충족한다. 하지만 ISA rule의 transfer verb 집합에 ‘넘길’이 없어 ISA 만기 이전 intent 자체가 만들어지지 않았다.",
    },
    "P35-013": {
        "primary_owner": "normalization_semantic_miss",
        "raw_terms": ["계속 고정"],
        "canonical_terms": ["risk_grade_changeability"],
        "missing_normalization": ["계속 고정 → 위험등급 변경 가능성"],
        "missing_requirements": ["위험등급 변경 가능성"],
        "secondary_effects": ["planner_slot_miss", "evaluator_slot_observability_gap: frozen expected_slot_keys에는 changeability가 없음"],
        "reason": "위험등급 값 slot은 생성됐지만 ‘시장 상황이 바뀌어도 계속 고정’이라는 반대 표현이 변경 가능성 field로 정규화되지 않았다. 따라서 frozen slot-key metric의 pass와 달리 manifest의 두 번째 factual requirement는 빠져 있다.",
    },
    "P35-017": {
        "primary_owner": "retrieval_missing",
        "raw_terms": [],
        "canonical_terms": [],
        "missing_normalization": [],
        "missing_requirements": [],
        "secondary_effects": ["matcher_field_miss_not_reached: risk-grade chunk가 candidate에 없음", "gate_false_reject"],
        "reason": "두 product code 결속과 각 risk_grade slot 생성은 성공했다. 그러나 candidate 20개는 두 source의 성과·법률·관리 문단만 포함하고, 어느 product의 위험등급 direct/equivalent chunk도 포함하지 않아 matcher와 final selection 단계에 도달하지 못했다.",
    },
    "P35-018": {
        "primary_owner": "evidence_selection_miss",
        "raw_terms": [],
        "canonical_terms": [],
        "missing_normalization": [],
        "missing_requirements": [],
        "secondary_effects": ["source_relevance_partial: KR5120420039의 선택 표는 과거 위험등급 변경 내역만 제시"],
        "reason": "두 상품 subject와 risk_grade slots는 정확하며 candidate에는 KR5120420039의 현재 5등급 direct chunks도 있다. 하지만 final selection은 더 높은 lexical score의 과거 변경내역 표를 골라, 설명서 기준 현재 등급 requirement를 충족하지 못했다.",
    },
}


# Every non-exact verdict is tied to the frozen selected IDs.  It is deliberately
# re-adjudicated for P35 rather than copied from an earlier P33/P34 review.
SOURCE_AUDITS = {
    "P35-005": {
        "status": "partial",
        "required_selected_ids": ["eec10989c7067926-paragraph_group-72065e97ce5d"],
        "reason": "연금계좌에서 세금 납부 시점을 늦추는 일반 설명만 있어 일반계좌 과세 시점과 면제 아님을 함께 직접 비교하지 못한다.",
    },
    "P35-007": {
        "status": "wrong_scope",
        "required_selected_ids": [
            "de4f8448134189df-paragraph_group-56c3e7dd9332",
            "4607500e74afcdf8-paragraph_group-fd0d4e7d80e6",
        ],
        "reason": "선택된 DC 해외 ETF 과세 문장과 일반 DB/DC 설명은 연금저축·IRP 인출조건/법정사유 비교의 account scope를 직접 지지하지 않는다.",
    },
    "P35-012": {
        "status": "semantic_equivalent",
        "required_selected_ids": [
            "4607500e74afcdf8-table-6f164502cbce",
            "04782a392f49293e-paragraph_group-5ab22c46ff7c",
        ],
        "reason": "현재 DB/DC 비교표는 DB 회사·DC 근로자 운용 및 평균임금 대 부담금+운용손익 구조를 직접 지지하고, DC 지급 문단은 부담금 구조를 보강한다. gold와 chunk는 다르지만 subject·field·value·scope가 같다.",
    },
    "P35-013": {
        "status": "partial",
        "required_selected_ids": ["cf922cacac95fad9-table-8d0be7d0b37c"],
        "reason": "현재 표는 KR510902773M의 3등급 값을 직접 지지하지만, 운용실적·시장 상황에 따라 등급이 변경될 수 있다는 두 번째 requirement를 담지 않는다.",
    },
    "P35-016": {
        "status": "semantic_equivalent",
        "required_selected_ids": [
            "cf922cacac95fad9-table-8d0be7d0b37c",
            "c787719b514f51da-table-94fdc4ab85f6",
        ],
        "reason": "각 source product의 3등급·2등급 위험등급을 직접 제시한다. gold paragraph와 달라도 두 subject, field, value와 비교 scope를 모두 충족한다.",
    },
    "P35-017": {
        "status": "partial",
        "required_selected_ids": [],
        "reason": "final selected evidence가 없으므로 두 상품 위험등급 requirement를 하나도 지지하지 못한다. 다른 account/product를 잘못 선택한 wrong-scope가 아니라 selection 부재다.",
    },
    "P35-018": {
        "status": "partial",
        "required_selected_ids": [
            "fc3cd93441450fa8-table-3c68497fd9d9",
            "eefb7f7b407d91de-paragraph_group-e41211088478",
        ],
        "reason": "KR5120420091의 현재 6등급은 직접 지지하지만 KR5120420039 선택 표의 5등급은 과거 변경 내역이다. 질문의 설명서 기준 현재 등급 requirement를 direct/equivalent하게 확정하지 못한다.",
    },
}


# Current candidate IDs that can fully support the same requirement even when
# the manifest's exact chunk is not in the list.  This supports attribution
# only; it does not auto-promote evidence in the Agent.
EQUIVALENT_CANDIDATE_IDS = {
    "P35-012": {
        "4607500e74afcdf8-table-6f164502cbce",
        "04782a392f49293e-paragraph_group-5ab22c46ff7c",
    },
    "P35-013": {"cf922cacac95fad9-table-8d0be7d0b37c"},
    "P35-016": {
        "cf922cacac95fad9-table-8d0be7d0b37c",
        "c787719b514f51da-table-94fdc4ab85f6",
    },
    "P35-018": {
        "fc3cd93441450fa8-table-0f507789a744",
        "eefb7f7b407d91de-table-b3cdf4fe0023",
    },
}


def _slot_records(plan) -> list[dict]:
    if plan.selection is None:
        return []
    return [
        {
            "key": match.slot.key,
            "name": match.slot.name,
            "chunk_id": match.result.chunk_id if match.result else None,
            "matched_terms": list(match.matched_terms),
        }
        for match in plan.selection.matches
    ]


def _source_verdict(question_id: str, frozen_row: dict) -> tuple[str, str, bool]:
    audit = SOURCE_AUDITS.get(question_id)
    if audit is None:
        if not frozen_row["exact_gold_chunk_ids_selected"]:
            raise SystemExit(f"missing source audit for non-exact {question_id}")
        return "exact_gold", "선택 evidence에 manifest gold chunk가 있으며 frozen run 기준 factual coverage를 직접 지지한다.", True
    selected = set(frozen_row["selected_chunk_ids"])
    required = set(audit["required_selected_ids"])
    current = required <= selected
    if not current:
        raise SystemExit(f"stale source adjudication: {question_id} selected IDs changed")
    return audit["status"], audit["reason"], current


def _case_payload(record: dict, frozen_row: dict, plan) -> dict:
    question_id = record["question_id"]
    audit = FAILURE_AUDITS.get(question_id)
    analysis = plan.analysis
    generated = _slot_records(plan)
    generated_keys = [item["key"] for item in generated if item["key"]]
    selected_ids = [context.chunk_id for context in plan.contexts]
    frozen_selected = frozen_row["selected_chunk_ids"]
    if selected_ids != frozen_selected:
        raise SystemExit(f"frozen selected evidence drifted for {question_id}")
    candidate_ids = [result.chunk_id for result in plan.candidate_results]
    declared = set(record["acceptable_equivalent_evidence"])
    equivalent = EQUIVALENT_CANDIDATE_IDS.get(question_id, set())
    relevant_candidates = [chunk_id for chunk_id in candidate_ids if chunk_id in declared | equivalent]
    accepted_ids = [item["chunk_id"] for item in generated if item["chunk_id"]]
    status, source_reason, source_current = _source_verdict(question_id, frozen_row)
    missing = audit["missing_requirements"] if audit else []
    schema_equivalent = []
    if frozen_row["requirement_plan_coverage_status"] == "schema_equivalent":
        schema_equivalent = [
            "db_dc_benefit_calculation + operation slots are semantically equivalent to db_dc_general_comparison"
        ]
    return {
        "question_id": question_id,
        "question": record["question"],
        "gold_requirements": record["required_requirements"],
        "gold_evidence_chunk_ids": record["acceptable_equivalent_evidence"],
        "normalization": {
            "raw_question": analysis.question,
            "raw_terms": audit["raw_terms"] if audit else [],
            "canonical_terms": audit["canonical_terms"] if audit else [],
            "missing_normalization": audit["missing_normalization"] if audit else [],
            "extracted_accounts": analysis.extracted_entities.accounts,
            "product_codes": analysis.product_codes,
            "requested_fields": analysis.extracted_entities.requested_fields,
        },
        "generated_requirements": generated,
        "requirement_comparison": {
            "frozen_requirement_plan_coverage": frozen_row["requirement_plan_coverage"],
            "frozen_coverage_status": frozen_row["requirement_plan_coverage_status"],
            "covered_slot_keys": generated_keys,
            "missing": missing,
            "schema_equivalent": schema_equivalent,
        },
        "retrieval": {
            "gold_or_equivalent_in_candidates": bool(relevant_candidates),
            "candidate_chunk_ids": candidate_ids,
            "relevant_candidate_chunk_ids": relevant_candidates,
        },
        "matcher": {
            "accepted_chunk_ids": accepted_ids,
            "slot_matches": generated,
            "rejected_relevant_chunk_ids": [
                chunk_id for chunk_id in relevant_candidates if chunk_id not in accepted_ids
            ],
        },
        "selected_evidence": selected_ids,
        "evidence_sufficient": frozen_row["evidence_sufficient"],
        "assessment_reason": frozen_row["assessment_reason"],
        "source_relevance": status,
        "source_relevance_current_selected_ids_confirmed": source_current,
        "source_relevance_reason": source_reason,
        "primary_owner": audit["primary_owner"] if audit else None,
        "secondary_effects": audit["secondary_effects"] if audit else [],
        "reason": audit["reason"] if audit else "Requirement plan, candidate evidence, gate, and selected source meet the frozen pre-HCX closed factual contract.",
    }


def _report(payload: dict) -> str:
    summary = payload["summary"]
    lines = [
        "# P35-A Closed Pre-HCX Failure Attribution",
        "",
        "## Frozen run 확인",
        "",
        f"- Frozen manifest SHA-256: `{payload['manifest_sha256']}`",
        "- HCX 호출: **0** (FakeGenerator로 deterministic `prepare()`만 재현)",
        "- Candidate production code modification: **없음**",
        "- 기존 P35 manifest 및 `p35_closed_pre_hcx.json`은 수정하지 않았다.",
        "- P35는 fresh holdout 자격을 잃었으며 이후 development/regression set으로만 사용한다.",
        "",
        "## Pre-HCX 결과",
        "",
        f"- Frozen requirement-plan coverage: **{summary['frozen_requirement_plan_coverage']}/18**",
        f"- Semantic requirement audit coverage: **{summary['semantic_requirement_coverage']}/18** (P35-013의 changeability slot 누락 포함)",
        f"- Frozen evidence sufficiency: **{summary['evidence_sufficient']}/18**",
        f"- Original + primary selected evidence: **{summary['primary_original']}/18**",
        "",
        "## Primary owner summary",
        "",
    ]
    for owner in PRIMARY_OWNERS:
        lines.append(f"- `{owner}`: **{summary['primary_owner_counts'][owner]}**")
    lines.extend((
        "",
        "Primary owner는 최초 실패 지점만 센다. 이후 plan/gate/source 문제는 secondary effect로만 기록했다.",
        "",
        "## Source relevance",
        "",
        f"- Exact gold: **{summary['source_relevance']['exact_gold']}**",
        f"- Semantic equivalent: **{summary['source_relevance']['semantic_equivalent']}**",
        f"- Partial: **{summary['source_relevance']['partial']}**",
        f"- Wrong scope: **{summary['source_relevance']['wrong_scope']}**",
        "",
        "모든 non-exact 판정은 P35 frozen execution의 현재 selected IDs를 다시 확인해 수행했다. P33/P34 판정을 재사용하지 않았다.",
        "",
        "### Current non-exact evidence adjudications",
        "",
    ))
    for case in (item for item in payload["cases"] if item["source_relevance"] != "exact_gold"):
        lines.append(
            f"- **{case['question_id']}** — `{case['source_relevance']}`: "
            f"{case['source_relevance_reason']}"
        )
    lines.extend((
        "",
        "## Failed case analysis",
        "",
    ))
    for case in (item for item in payload["cases"] if item["primary_owner"]):
        lines.extend((
            f"### {case['question_id']} — `{case['primary_owner']}`",
            "",
            f"- 질문: {case['question']}",
            f"- Gold requirements: {' / '.join(case['gold_requirements'])}",
            f"- Generated slots: {', '.join(case['requirement_comparison']['covered_slot_keys']) or '없음'}",
            f"- Candidate에 gold/equivalent 존재: **{case['retrieval']['gold_or_equivalent_in_candidates']}**",
            f"- Selected evidence: {', '.join(case['selected_evidence']) or '없음'}",
            f"- Source relevance: `{case['source_relevance']}` — {case['source_relevance_reason']}",
            f"- 판정: {case['reason']}",
            f"- Downstream: {'; '.join(case['secondary_effects']) or '없음'}",
            "",
        ))
    lines.extend((
        "## Generalization diagnosis",
        "",
        "- **Semantic normalization**이 가장 이른 반복 failure다. ‘굴려주는 쪽’, ‘세금을 나중에 낸다’, ‘중간에 찾기’, ‘넘길’, ‘계속 고정’이 각각 운용주체·과세이연·중도인출/증빙·ISA 이전·위험등급 변경 가능성으로 canonicalize되지 않았다.",
        "- **Lexical alias**는 `연저 → 연금저축` 한 건에서 독립적인 최초 원인이었다. P35-009의 `연저`는 IRP가 이미 있어 ISA rule의 account predicate를 막지는 않았으므로 secondary로만 기록했다.",
        "- **Matcher scope binding**은 P35-007에서 account-specific withdrawal evidence 대신 DC 해외 ETF/일반 문단을 선택했다. candidate에는 적합한 IRP·연금저축 근거가 있었다.",
        "- **Product retrieval**은 P35-017에서 product code와 risk-grade slot은 정확했지만 source-level BM25 후보가 위험등급 본문까지 도달하지 못했다.",
        "- P35-013은 frozen slot-key metric이 risk_grade만 보아 pass로 집계했으나, manifest의 changeability requirement는 실제로 누락됐다. 이는 production pass가 아니라 evaluation observability gap이다.",
        "",
        "## P35-B recommendations (수정하지 않음)",
        "",
        "1. 표현별 질문 패치가 아니라 `surface phrase → canonical concept/entity/field` normalization layer를 설계한다. 이 레이어는 연금저축 alias, 과세이연, 중도인출+증빙, ISA 이전, 운용주체, 위험등급 변경 가능성을 각각 canonical representation으로 넘겨야 한다.",
        "2. requirement builder는 canonical representation에서 multi-requirement decomposition을 수행해, 조건/절차/증빙과 비교 대상별 동일 field를 별도 slot으로 생성한다.",
        "3. withdrawal matcher는 `account subject + field + value/condition`을 함께 요구해 DC 해외 ETF 과세 문장이 IRP 법정사유·계좌별 인출 과세 근거를 대체하지 못하게 한다.",
        "4. product-field retrieval은 code document의 일반 문단을 반복 확장하기보다 risk-grade field가 있는 첫 페이지/표 chunk를 후보로 보장하는 별도 field recall을 검증한다.",
        "5. 평가에서는 human-readable `required_requirements`와 machine slot keys의 semantic coverage를 함께 저장해 P35-013 같은 false pass를 방지한다.",
        "",
        "## Go / No-Go",
        "",
        "**No-Go.** P35 pre-HCX는 semantic requirement audit 12/18이며, source relevance도 exact-or-equivalent 13/18에 그친다. HCX를 호출하지 않는다. P35를 수정 후 점수로 일반화 증거로 쓰지 않으며, 일반화 검증은 향후 P36 fresh Closed holdout에서 수행한다.",
        "",
    ))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "evaluation/p35_closed_holdout_manifest.json")
    parser.add_argument("--pre-hcx", type=Path, default=ROOT / "evaluation/p35_closed_pre_hcx.json")
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/p35a_failure_attribution.json")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/p35a_failure_attribution.md")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    frozen = json.loads(args.pre_hcx.read_text(encoding="utf-8"))
    manifest_hash = _manifest_hash(manifest)
    if frozen["manifest_sha256"] != manifest_hash:
        raise SystemExit("P35 pre-HCX artifact belongs to a different frozen manifest")
    if frozen.get("hcx_called") is not False or frozen["summary"].get("hcx_calls") != 0:
        raise SystemExit("P35-A requires an HCX-free frozen execution")

    frozen_rows = {row["question_id"]: row for row in frozen["rows"]}
    agent = P27DStructuredOutputAgent(build_frozen_retriever(args.corpus, args.index), FakeGenerator())
    cases = []
    for record in manifest["questions"]:
        question_id = record["question_id"]
        if question_id not in frozen_rows:
            raise SystemExit(f"missing frozen row: {question_id}")
        plan = agent.prepare(record["question"], top_k=10)
        cases.append(_case_payload(record, frozen_rows[question_id], plan))

    owner_counts = Counter(case["primary_owner"] for case in cases if case["primary_owner"])
    relevance_counts = Counter(case["source_relevance"] for case in cases)
    semantic_requirement_failures = sum(bool(case["requirement_comparison"]["missing"]) for case in cases)
    summary = {
        "total_questions": len(cases),
        "frozen_requirement_failures": len(cases) - frozen["summary"]["requirement_plan_coverage"],
        "semantic_requirement_failures": semantic_requirement_failures,
        "frozen_requirement_plan_coverage": frozen["summary"]["requirement_plan_coverage"],
        "semantic_requirement_coverage": len(cases) - semantic_requirement_failures,
        "evidence_insufficient": len(cases) - frozen["summary"]["evidence_sufficient"],
        "evidence_sufficient": frozen["summary"]["evidence_sufficient"],
        "primary_original": frozen["summary"]["primary_original"],
        "primary_owner_counts": {owner: owner_counts[owner] for owner in PRIMARY_OWNERS},
        "source_relevance": {
            status: relevance_counts[status]
            for status in ("exact_gold", "semantic_equivalent", "partial", "wrong_scope")
        },
        "replay_selected_evidence_parity": len(cases),
    }
    payload = {
        "phase": "P35-A",
        "experiment": "P35 Closed Pre-HCX Failure Attribution",
        "manifest_sha256": manifest_hash,
        "hcx_calls": 0,
        "candidate_code_modified": False,
        "frozen_execution_modified": False,
        "summary": summary,
        "cases": cases,
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(_report(payload), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
