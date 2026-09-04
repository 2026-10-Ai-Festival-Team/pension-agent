"""Freeze P35, a fresh Closed factual holdout, before executing candidate code.

P35 reuses only corpus facts, never prior questions or their responses.  Its
new surface forms test Korean colloquialisms, abbreviations, spacing variants,
implicit comparisons, and multi-requirement wording.  It is frozen before any
P35 preparation result exists.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from build_p34_closed_holdout import SPECS as P34_SPECS


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "evaluation/p35_closed_holdout_manifest.json"


def _normalise_question(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", value).casefold()


# The factual schemas and original-evidence assertions are defined before the
# new questions are run.  Every question is a newly authored surface form; no
# P34 question text is reused.
QUESTION_VARIANTS = {
    "P34-001": (
        "P35-001",
        "DB/DC에서 회사가 돈을 굴려주는 쪽과 퇴직급여를 계산하는 방식, 그리고 DC 회사 부담금 기준을 한 번에 구분해 주세요.",
        "구어체 ‘회사에서 굴려주는 거’와 세 가지 DB/DC factual 축을 결합했다.",
    ),
    "P34-002": (
        "P35-002",
        "퇴직연금 가입자 교육을 회사가 매번 직접 해야 하나요? 외부 기관에 맡길 수 있는지와 최소 연간 횟수도 알려주세요.",
        "직접 실시·외부 위탁·주기를 간접 질문으로 표현했다.",
    ),
    "P34-003": (
        "P35-003",
        "IRP에서 ETF를 직접 고를 수 있다면 레버리지 ETF나 인버스 ETF도 똑같이 살 수 있다는 뜻인가요?",
        "직접 거래 허용과 제한 상품을 동일 규칙으로 오해하는 전제를 사용했다.",
    ),
    "P34-004": (
        "P35-004",
        "연저만 납입할 때와 연저+IRP로 넣을 때 세액 공제한도는 왜 따로 계산하며 각각 얼마인가요?",
        "연금저축 축약어와 띄어쓰기 변형을 사용했다.",
    ),
    "P34-005": (
        "P35-005",
        "일반 계좌보다 연금계좌에서 세금을 나중에 낸다는 말은 세금이 없어지는 것인가요, 아니면 내는 시점만 미뤄지는 것인가요?",
        "과세이연이라는 정식 용어 없이 과세 시점을 질문했다.",
    ),
    "P34-006": (
        "P35-006",
        "국내 상장 해외 ETF의 매매차익·분배금은 일반계좌와 연금저축/IRP에서 세금이 붙는 때가 어떻게 달라요?",
        "계좌 표기와 소득 항목을 축약·구어체로 바꿨다.",
    ),
    "P34-007": (
        "P35-007",
        "연금저축처럼 IRP도 필요한 금액만 중간에 찾을 수 있나요? 중도 인출사유와 세금 처리의 차이도 같이 알려주세요.",
        "‘중간에 찾기’와 띄어쓰기 변형으로 인출 비교를 표현했다.",
    ),
    "P34-008": (
        "P35-008",
        "DC에 쌓인 돈을 중간에 찾기 전에는 법정 사유만 확인하면 되나요, 신청서와 증명 서류도 챙겨야 하나요?",
        "중도인출을 ‘중간에 찾기’로, 증빙을 ‘증명 서류’로 바꿨다.",
    ),
    "P34-009": (
        "P35-009",
        "ISA 만기 돈을 연저나 IRP로 넘길 때 며칠 안에 해야 하고, 세액공제는 어떤 계산으로 더 인정되나요?",
        "ISA 이전 기한과 추가 공제를 구어체·축약어로 묻는다.",
    ),
    "P34-010": (
        "P35-010",
        "퇴직연금 상품을 팔지 않고 금융회사만 바꾸는 실물이전은 DB/DC와 IRP에서 신청하는 길이 어떻게 다른가요?",
        "실물이전 정의 대신 ‘안 팔고 금융회사만 바꾸기’로 표현했다.",
    ),
    "P34-011": (
        "P35-011",
        "DB/DC나 IRP 계좌에서 ETF를 고를 때 직접 매매가 된다고 해서 인버스·레버리지도 허용된다고 보면 안 되나요?",
        "DB/DC 축약 표기와 전제 교정형 문장으로 제한을 묻는다.",
    ),
    "P34-012": (
        "P35-012",
        "DB와 DC는 누가 적립금을 운용하고, 퇴직급여는 어떤 기준으로 정해지는지 두 가지를 같이 비교해 주세요.",
        "한 문장에 운용 주체와 급여 결정이라는 복수 factual requirement를 넣었다.",
    ),
    "P34-013": (
        "P35-013",
        "KR510902773M 위험등급몇등급인가요? 시장 상황이 바뀌어도 이 등급은 계속 고정인가요?",
        "띄어쓰기 없는 위험등급 표현과 미래 변경 조건을 결합했다.",
    ),
    "P34-014": (
        "P35-014",
        "KR5127450215는 지수를 따라가는 상품인가요? 주식 관련 자산은 최대 어느 비중까지 담을 수 있나요?",
        "지수추종을 ‘지수를 따라감’으로, 투자비율을 간접 질문으로 바꿨다.",
    ),
    "P34-015": (
        "P35-015",
        "KR510902773M C-e의 연간 총보수와 3년 비용 예시는 같은 숫자라고 보면 되나요?",
        "총보수와 기간별 비용 예시의 field boundary를 짧은 구어체로 묻는다.",
    ),
    "P34-016": (
        "P35-016",
        "KR510902773M이랑 KR510902777M 중 위험등급 숫자가 더 작은 쪽이 더 위험한 상품인지, 두 등급을 함께 확인해 주세요.",
        "위험등급 숫자 방향을 포함한 간접 비교를 사용했다.",
    ),
    "P34-017": (
        "P35-017",
        "KR5114420022보다 KR5114450222가 더 비싼 위험등급인가요? 두 상품의 등급 표시를 근거로 비교해 주세요.",
        "‘더 높은 위험’을 ‘더 비싼 위험등급’이라는 구어체 비교로 바꿨다.",
    ),
    "P34-018": (
        "P35-018",
        "KR5120420039와 KR5120420091 중 설명서 기준으로 더 안전 쪽 등급으로 적힌 것은 무엇이며 각각 몇 등급인가요?",
        "낮은 위험을 ‘안전 쪽 등급’으로 간접 표현하되 factual 등급을 모두 요구한다.",
    ),
}


def _specs() -> tuple[dict, ...]:
    rows = []
    for base in P34_SPECS:
        question_id, question, freshness_note = QUESTION_VARIANTS[base["question_id"]]
        rows.append({
            **base,
            "question_id": question_id,
            "question": question,
            "freshness_note": freshness_note,
        })
    return tuple(rows)


def _existing_questions() -> list[tuple[str, str]]:
    records = []
    excluded = {
        MANIFEST_PATH.name,
        "p35_closed_pre_hcx.json",
        "p35_current_evidence_revalidation.json",
    }
    for path in [*sorted((ROOT / "evaluation").glob("*.json")), *sorted((ROOT / "evaluation").glob("*.jsonl"))]:
        if path.name in excluded:
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        candidates = raw.get("questions", raw.get("rows", [])) if isinstance(raw, dict) else raw
        if not isinstance(candidates, list):
            continue
        for record in candidates:
            if isinstance(record, dict) and isinstance(record.get("question"), str):
                records.append((str(path.relative_to(ROOT)), record["question"]))
    return records


def main() -> None:
    specs = _specs()
    corpus_ids = {
        json.loads(line)["chunk_id"]
        for line in (ROOT / "data/parsed/chunks.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    declared_ids = {chunk_id for spec in specs for group in spec["evidence_groups"] for chunk_id in group}
    missing = sorted(declared_ids - corpus_ids)
    if missing:
        raise SystemExit(f"P35 declares missing corpus chunk IDs: {missing}")

    ids_by_normalized_question = {_normalise_question(spec["question"]): spec["question_id"] for spec in specs}
    if len(ids_by_normalized_question) != len(specs):
        raise SystemExit("P35 has duplicate normalised questions")
    overlaps = [
        {"new_question_id": ids_by_normalized_question[_normalise_question(question)], "prior_file": path, "prior_question": question}
        for path, question in _existing_questions()
        if _normalise_question(question) in ids_by_normalized_question
    ]
    if overlaps:
        raise SystemExit("P35 has exact normalised question overlap: " + json.dumps(overlaps, ensure_ascii=False))

    manifest = {
        "version": "1.0",
        "status": "frozen_before_pre_hcx_execution",
        "purpose": "P35 fresh holdout: Closed factual pre-HCX generalisation after P34-B. No HCX before the pre-HCX gate.",
        "candidate": "P34-B closed pre-HCX certified candidate",
        "scope": {
            "included": ["institution", "tax", "procedure", "compound closed", "product factual", "product factual comparison"],
            "excluded": ["personalised recommendation", "suitability", "clarify", "abstain", "prompt injection", "external real-time information"],
        },
        "denominators": {"total": len(specs), "answerable": len(specs), "unsupported": 0},
        "pre_hcx_go_criteria": {
            "requirement_plan_coverage": 1.0,
            "evidence_sufficiency": 1.0,
            "source_relevance_exact_or_manual_equivalent": 1.0,
            "wrong_scope": 0,
        },
        "questions": [
            {
                **spec,
                "answerability": "answerable",
                "expected_policy_behavior": "answer_with_source",
                "required_original_sources": sorted({chunk_id.split("-", 1)[0] for group in spec["evidence_groups"] for chunk_id in group}),
                "acceptable_equivalent_evidence": sorted({chunk_id for group in spec["evidence_groups"] for chunk_id in group}),
            }
            for spec in specs
        ],
    }
    canonical = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    manifest["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
    manifest["validation"] = {
        "exact_normalised_overlap_with_prior_evaluation_files": 0,
        "declared_gold_chunk_ids": len(declared_ids),
        "missing_declared_gold_chunk_ids": 0,
        "group_counts": dict(sorted(Counter(spec["category"] for spec in specs).items())),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(MANIFEST_PATH.relative_to(ROOT)), "sha256": manifest["manifest_sha256"], **manifest["validation"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
