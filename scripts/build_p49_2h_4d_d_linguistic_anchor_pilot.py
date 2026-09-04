"""Prepare P49-2H-4D-D bounded linguistic-anchor drafts with zero HCX calls.

The twelve records here are deliberately labelled ``drafted_by_codex`` and
``human_review_required``.  They are not presented as human-written anchors
and the execution bridge refuses to call HCX until a human explicitly changes
that review state.  The builder only creates a separate additive artifact;
the frozen gold, 4B, and v4/v5/v6 manifests remain untouched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_p49_2h_4c_execution_bridge as bridge
from scripts import build_p49_2h_4d_bounded_targeted_v6 as v6
from scripts.run_p49_2h_full_adapter import semantic_question_findings


MANIFEST = bridge.REMEDIATION_MANIFEST
COMPARISON_POOL = bridge.COMPARISON_POOL
DEFAULT_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_d_linguistic_anchor_drafts_v1.jsonl"
DEFAULT_AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_4d_d_linguistic_anchor_drafts_audit_v1.json"


# Each question is a Codex draft for human revision/approval, not a claimed
# human-authored record.  The profile fields are separately rendered by the
# existing caller so HCX must consume the linguistic axes as active controls.
ANCHOR_SPECS: tuple[dict[str, Any], ...] = (
    {
        "coverage_cell": "D12-Q12-bounded_answer",
        "anchor_question": "ISA 만기자금을 연금계좌로 옮기려는데, 내년에도 추가 세액공제 한도가 지금과 같다고 봐도 되나요?",
        "linguistic_archetype": "공시자료 상황에서 미래 한도의 근거 범위를 확인하는 질문",
        "profile": ("공시자료 검토 중", "자료 범위 확인", "근거 범위 점검", "향후", "미래 값이 이미 확정됐다는 전제", "상황절+근거범위 확인", "evidence_limit", "general", "medium"),
    },
    {
        "coverage_cell": "D12-Q12-bounded_answer",
        "anchor_question": "ISA 이전 혜택을 내년 자금계획에 넣고 싶은데, 그때 적용될 추가 공제 한도까지 지금 자료로 알 수 있나요?",
        "linguistic_archetype": "연말 계획 상황에서 미래 한도의 확정 전제를 점검하는 질문",
        "profile": ("연말 자금 계획 중", "계획 전제 점검", "미래 수치 미확정 점검", "앞으로", "향후 시점에도 같은 값이라는 전제", "계획절+정보공백 확인", "planning_check", "conversational", "short"),
    },
    {
        "coverage_cell": "D12-Q12-bounded_answer",
        "anchor_question": "지금 안내된 ISA 만기자금 이전 공제 한도가 앞으로도 그대로인지, 아니면 아직 정해지지 않은 건지 궁금해요.",
        "linguistic_archetype": "계약 직전 상황에서 미래 한도 수치의 확인 가능성을 묻는 질문",
        "profile": ("계약 체결 직전", "확정 여부 확인", "현재 정보와 미래 확정값 구분", "미래", "미래 값이 이미 확정됐다는 전제", "상황절+확정전제 확인", "assumption_check", "beginner", "medium"),
    },
    {
        "coverage_cell": "D17-Q17-bounded_answer",
        "anchor_question": "이 상품을 몇 년 들고 갈 생각인데, 앞으로 위험등급이 몇 등급이 될지는 지금 자료만으로는 모르는 건가요?",
        "linguistic_archetype": "공시자료 상황에서 미래 위험등급의 근거 범위를 확인하는 질문",
        "profile": ("공시자료 검토 중", "자료 범위 확인", "근거 범위 점검", "향후", "현재 정보가 미래 값을 보장한다는 전제", "상황절+근거범위 확인", "evidence_limit", "general", "medium"),
    },
    {
        "coverage_cell": "D17-Q17-bounded_answer",
        "anchor_question": "현재 위험등급은 봤는데, 다음에 등급이 바뀐다면 어느 등급으로 갈지까지 이미 정해져 있나요?",
        "linguistic_archetype": "변경 안내 상황에서 미래 위험등급 수치의 확정 여부를 묻는 질문",
        "profile": ("운용 변경 안내 확인 중", "확정 여부 확인", "미래 수치 미확정 점검", "미래", "미래 값이 이미 확정됐다는 전제", "상황절+확정전제 확인", "assumption_check", "conversational", "short"),
    },
    {
        "coverage_cell": "D17-Q17-bounded_answer",
        "anchor_question": "장기 보유하려고 합니다. 지금 위험등급이 앞으로도 유지된다고 전제해도 되는지 알고 싶어요.",
        "linguistic_archetype": "장기 보유 계획에서 미래 위험등급 유지라는 전제를 점검하는 질문",
        "profile": ("장기 보유 계획 중", "계획 전제 점검", "현재 정보와 미래 확정값 구분", "앞으로", "향후 시점에도 같은 값이라는 전제", "계획절+정보공백 확인", "planning_check", "beginner", "medium"),
    },
    {
        "coverage_cell": "D18-Q18-bounded_answer",
        "anchor_question": "위험등급이 바뀔 수 있다는 건 알겠는데, 실제로 언제 바뀔지는 지금 확인할 수 있나요?",
        "linguistic_archetype": "공시자료 상황에서 위험등급 변경 시점의 근거 범위를 확인하는 질문",
        "profile": ("공시자료 검토 중", "자료 범위 확인", "근거 범위 점검", "향후", "미래 값이 이미 확정됐다는 전제", "상황절+근거범위 확인", "evidence_limit", "general", "medium"),
    },
    {
        "coverage_cell": "D18-Q18-bounded_answer",
        "anchor_question": "이 상품 위험등급이 변경될 수 있다면, 몇 등급으로 바뀔지까지 현재 정해져 있는 건가요?",
        "linguistic_archetype": "변경 안내 상황에서 미래 위험등급 값의 확정 전제를 점검하는 질문",
        "profile": ("운용 변경 안내 확인 중", "확정 여부 확인", "현재 정보와 미래 확정값 구분", "미래", "현재 정보가 미래 값을 보장한다는 전제", "상황절+확정전제 확인", "assumption_check", "conversational", "short"),
    },
    {
        "coverage_cell": "D18-Q18-bounded_answer",
        "anchor_question": "오래 들고 있을 예정이라 위험등급 변동이 신경 쓰입니다. 다음 변경 시점이나 등급을 미리 알 수 있나요?",
        "linguistic_archetype": "장기 보유 계획에서 미래 변경 날짜의 정보 공백을 확인하는 질문",
        "profile": ("장기 보유 계획 중", "계획 전제 점검", "미래 수치 미확정 점검", "앞으로", "향후 시점에도 같은 값이라는 전제", "계획절+정보공백 확인", "planning_check", "beginner", "medium"),
    },
    {
        "coverage_cell": "D20-Q12-bounded_answer",
        "anchor_question": "이 상품을 오래 가져가면 총보수율이 앞으로도 지금 표시된 비율로 유지된다고 보면 되나요?",
        "linguistic_archetype": "공시자료 상황에서 미래 총보수율의 근거 범위를 확인하는 질문",
        "profile": ("공시자료 검토 중", "자료 범위 확인", "근거 범위 점검", "향후", "미래 값이 이미 확정됐다는 전제", "상황절+근거범위 확인", "evidence_limit", "general", "medium"),
    },
    {
        "coverage_cell": "D20-Q12-bounded_answer",
        "anchor_question": "내년 비용을 미리 계산해보려는데, 그때 적용될 총보수율이 몇 퍼센트일지 지금 알 수 있나요?",
        "linguistic_archetype": "장기 보유 계획에서 미래 총보수율 유지 전제를 점검하는 질문",
        "profile": ("장기 보유 계획 중", "계획 전제 점검", "현재 정보와 미래 확정값 구분", "앞으로", "현재 정보가 미래 값을 보장한다는 전제", "계획절+정보공백 확인", "planning_check", "conversational", "short"),
    },
    {
        "coverage_cell": "D20-Q12-bounded_answer",
        "anchor_question": "지금 표시된 총보수율 말고 앞으로 적용될 비율까지 이미 확정돼 있는지 궁금합니다.",
        "linguistic_archetype": "계약 직전 상황에서 미래 총보수율 수치의 확정 여부를 묻는 질문",
        "profile": ("계약 체결 직전", "확정 여부 확인", "미래 수치 미확정 점검", "미래", "미래 값이 이미 확정됐다는 전제", "상황절+확정전제 확인", "assumption_check", "beginner", "medium"),
    },
)


def profile_from_spec(spec: dict[str, Any], index: int) -> tuple[dict[str, str], dict[str, str]]:
    situation, speech, gap, temporal, misconception, shape, query_form, register, length = spec["profile"]
    profile = {
        "profile_id": f"{spec['coverage_cell']}-anchor-{index:02d}",
        "user_situation_frame": situation,
        "speech_act": speech,
        "information_gap_mode": gap,
        "temporal_expression": temporal,
        "misconception_type": misconception,
        "sentence_shape": shape,
    }
    return profile, {"context_frame": situation, "query_form": query_form, "register": register, "length_band": length}


def build_anchor_rows(manifest_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Copy only immutable source authority and attach draft linguistic cues."""
    sources: dict[str, list[dict[str, Any]]] = {}
    for cell in v6.TARGET_CELLS:
        rows = [row for row in manifest_rows if row["coverage_cell"] == cell]
        if not rows:
            raise ValueError(f"anchor target cell missing from manifest: {cell}")
        sources[cell] = rows
    offsets: dict[str, int] = {cell: 0 for cell in v6.TARGET_CELLS}
    records: list[dict[str, Any]] = []
    for index, spec in enumerate(ANCHOR_SPECS, start=1):
        cell = spec["coverage_cell"]
        source = deepcopy(sources[cell][offsets[cell] % len(sources[cell])])
        offsets[cell] += 1
        profile, controls = profile_from_spec(spec, index)
        source["anchor_source_manifest_request_id"] = source["remediation_request_id"]
        source["remediation_request_id"] = f"P49-2H-4D-D-ANCHOR-{index:04d}"
        source.update(controls)
        source["bounded_diversity_profile"] = profile
        source["bounded_linguistic_anchor"] = {
            "anchor_id": f"P49-2H-4D-D-ANCHOR-TEXT-{index:04d}",
            "anchor_question": spec["anchor_question"],
            "linguistic_archetype": spec["linguistic_archetype"],
            "authoring_status": "drafted_by_codex",
            "human_review_status": "human_review_required",
        }
        source["anchor_pilot_status"] = "draft_pending_human_review"
        source["anchor_pilot_cell"] = cell
        records.append(source)
    return records


def preflight(
    anchor_rows: list[dict[str, Any]],
    semantic_rows: list[dict[str, Any]],
    comparison_questions: list[str],
) -> dict[str, Any]:
    """Validate anchor semantics and caller consumption with zero HCX calls."""
    failures: list[dict[str, Any]] = []
    for row in anchor_rows:
        try:
            adapted = bridge.adapt_remediation_record(row, semantic_rows)
            caller_input = bridge.caller_input_for(adapted, comparison_questions)
            preservation = bridge.preservation_findings(row, adapted)
            diversity = bridge.diversity_prompt_findings(row, caller_input)
            semantic = semantic_question_findings(
                row["bounded_linguistic_anchor"]["anchor_question"], adapted["semantic_request"]
            )
            if preservation or diversity or semantic:
                failures.append(
                    {
                        "remediation_request_id": row["remediation_request_id"],
                        "preservation_findings": preservation,
                        "diversity_prompt_findings": diversity,
                        "anchor_semantic_findings": semantic,
                    }
                )
        except (KeyError, ValueError) as exc:
            failures.append({"remediation_request_id": row["remediation_request_id"], "adapter_error": str(exc)})
    return {
        "external_hcx_calls": 0,
        "requested": len(anchor_rows),
        "preservation_prompt_and_semantic_pass": len(anchor_rows) - len(failures),
        "failures": failures,
        "human_review_required": len(anchor_rows),
        "hcX_execution_allowed": False,
    }


def write_new(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite linguistic-anchor artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--comparison-pool", type=Path, default=COMPARISON_POOL)
    parser.add_argument("--candidate", type=Path, action="append")
    parser.add_argument("--expected-promoted-pass", type=int, default=294)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()

    manifest_rows = bridge.read_jsonl(args.manifest)
    candidate_rows = v6.read_many(args.candidate or list(v6.DEFAULT_CANDIDATES))
    promoted = v6.promoted_passes(candidate_rows)
    if len(promoted) != args.expected_promoted_pass:
        parser.error(f"expected {args.expected_promoted_pass} promoted PASS candidates; found {len(promoted)}")
    immutable = [row for row in bridge.read_jsonl(args.comparison_pool) if row.get("validation_status") == "pass"]
    if len(immutable) != 133:
        parser.error(f"expected 133 immutable PASS candidates; found {len(immutable)}")
    anchor_rows = build_anchor_rows(manifest_rows)
    current_pool = [*immutable, *promoted.values()]
    preflight_audit = preflight(
        anchor_rows,
        bridge.read_jsonl(bridge.SEMANTIC_REQUESTS),
        [row["question"] for row in current_pool],
    )
    dedup_inputs = [
        {
            "remediation_request_id": row["remediation_request_id"],
            "validation_status": "pass",
            "generation_status": "not_generated_anchor_draft",
            "question": row["bounded_linguistic_anchor"]["anchor_question"],
        }
        for row in anchor_rows
    ]
    dedup = bridge.full_set_dedup_audit(current_pool, dedup_inputs, bridge.read_jsonl(bridge.FROZEN_SEED))
    collision_count = sum(
        len(dedup[key])
        for key in ("exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions")
    )
    source_ids = {row["remediation_request_id"] for row in manifest_rows}
    audit = {
        "stage": "P49-2H-4D-D Linguistic Anchor Pilot",
        "external_hcx_calls": 0,
        "source_manifest": str(args.manifest),
        "source_manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "source_manifest_modified": False,
        "current_accepted_quality_pool": len(current_pool),
        "anchor_count": len(anchor_rows),
        "anchor_count_by_cell": {
            cell: sum(row["coverage_cell"] == cell for row in anchor_rows) for cell in v6.TARGET_CELLS
        },
        "authoring_status": "drafted_by_codex",
        "human_review_status": "human_review_required",
        "source_ids_valid": all(row["anchor_source_manifest_request_id"] in source_ids for row in anchor_rows),
        "preflight": preflight_audit,
        "anchor_full_set_dedup": dedup,
        "anchor_full_set_dedup_pass": collision_count == 0,
        "anchor_hcx_execution_allowed": False,
        "batch_07_execution_allowed": False,
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }
    write_new(args.output, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in anchor_rows))
    write_new(args.audit_output, json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "external_hcx_calls": 0,
                "anchor_count": len(anchor_rows),
                "preflight_pass": preflight_audit["preservation_prompt_and_semantic_pass"],
                "dedup_pass": audit["anchor_full_set_dedup_pass"],
                "human_review_status": audit["human_review_status"],
                "output": str(args.output),
                "audit_output": str(args.audit_output),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
