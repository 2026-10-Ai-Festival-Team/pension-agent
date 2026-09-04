"""Freeze P37: a fresh Closed factual holdout after P36-B.

P37 changes syntactic structure, indirect phrasing, and factual composition
while reusing only independently verified source contracts from P34.  It must
be frozen before any P37 preparation run.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

try:
    from build_p34_closed_holdout import SPECS as P34_SPECS
except ModuleNotFoundError:  # pragma: no cover
    from scripts.build_p34_closed_holdout import SPECS as P34_SPECS


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "evaluation/p37_closed_holdout_manifest.json"


def _normalise_question(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", value).casefold()


# These variants intentionally avoid P34--P36's previously exercised phrases
# (for example 연저, 중간에 찾기, 세금을 나중에, 지수를 따라간다).  The
# evidence contract is inherited only after each P34 source group was manually
# verified as a factual answer source.
QUESTION_VARIANTS = {
    "P34-001": (
        "P37-001",
        "DB의 퇴직급여 액수는 무엇으로 산정되고, DC 적립금 운용 결정을 맡는 사람은 누구인가요? 회사가 DC에 적립해야 하는 기준도 함께 설명해 주세요.",
        "산정 기준·운용 결정자·회사 적립 기준을 다른 문장 구조로 결합했다.",
    ),
    "P34-002": (
        "P37-002",
        "가입자 대상 제도 안내 교육의 시행 책임은 누구에게 있나요? 최소 실시 주기와 전문기관 대행 가능 여부도 구분해 주세요.",
        "책임/주기/대행이라는 간접 표현으로 교육의 세 factual axis를 요구한다.",
    ),
    "P34-003": (
        "P37-003",
        "퇴직연금 계좌에서 ETF를 직접 주문할 수 있는 범위와, 수익률 변동을 두 배로 키우거나 역방향으로 따르도록 만든 ETF의 제한을 나눠 설명해 주세요.",
        "레버리지·인버스 명칭 없이 배수/역방향 상품 특성으로 restriction을 묻는다.",
    ),
    "P34-004": (
        "P37-004",
        "개인용 연금 저축 계좌만 활용한 경우와 개인형 퇴직연금까지 함께 납입한 경우에 공제 가능한 납입액 상한은 어떻게 달라지나요?",
        "비정형 계좌 표현과 두 scope의 동일 tax field를 비교한다.",
    ),
    "P34-005": (
        "P37-005",
        "일반 투자계좌에서 운용 이익이 생기면 세금은 언제 부과되고, 연금계좌 안 운용 이익은 언제 과세되나요? 세금이 사라지는 것인지도 구분해 주세요.",
        "과세이연이라는 용어 없이 과세 시점과 면제 오해를 함께 묻는다.",
    ),
    "P34-006": (
        "P37-006",
        "한국 거래소에 등록된 해외 ETF를 통상 계좌로 보유할 때와 연금계좌에서 운용할 때, 매매 이익과 분배금의 과세 시점은 어떻게 다른가요?",
        "일반계좌를 통상 계좌로, 국내상장을 거래소 등록으로 바꾼 tax comparison이다.",
    ),
    "P34-007": (
        "P37-007",
        "연금저축과 IRP에서 55세 전 자금을 꺼낼 수 있는 범위가 같은가요? IRP에만 적용되는 법정 사유와 인출 세율을 함께 알려주세요.",
        "계좌별 인출 가능 범위·법정사유·세금을 한 문장에 결합한다.",
    ),
    "P34-008": (
        "P37-008",
        "DC 적립금을 근무 중에 사용하려면 법에서 정한 이유만 충족하면 되나요? 접수 과정과 확인 문서도 필요한지 알려주세요.",
        "중도인출 직접 용어 없이 재직 중 사용·확인 문서로 condition/procedure를 묻는다.",
    ),
    "P34-009": (
        "P37-009",
        "ISA가 종료된 자금을 연금계좌에 넣을 수 있는 허용 기한은 언제까지이고, 추가 세액공제는 어떤 계산과 한도를 따르나요?",
        "만기/이전 직접 표현 없이 종료 event·허용 기한·계산을 사용한다.",
    ),
    "P34-010": (
        "P37-010",
        "보유 펀드를 매각하지 않은 상태로 퇴직연금 운영 금융기관을 변경하려면 어떤 이전 방식이 적용되나요? DB·DC 재직자와 IRP의 접수 경로도 비교해 주세요.",
        "실물이전/사업자 직접어 없이 매각 없는 기관 변경과 account별 접수를 묻는다.",
    ),
    "P34-011": (
        "P37-011",
        "퇴직연금에서 ETF를 직접 매매할 수 있다는 규칙과 가격 움직임을 배가하거나 반대로 추적하는 ETF의 제한은 같은 뜻인가요?",
        "직접매매와 레버리지/인버스 제한을 다른 predicate로 분리한다.",
    ),
    "P34-012": (
        "P37-012",
        "DB 자산을 실제로 관리하는 쪽과 DC의 운용방법 선택 주체는 각각 누구인가요? 두 제도의 퇴직급여 계산 원리도 비교해 주세요.",
        "운용 주체와 급여 calculation을 주체/원리 표현으로 결합한다.",
    ),
    "P34-013": (
        "P37-013",
        "KR510902773M의 현재 위험 분류 단계와, 시장 여건이나 운용 결과에 따라 그 분류가 달라질 여지가 있는지를 확인해 주세요.",
        "위험등급과 변경 가능성을 분류 단계/변동 여지로 분리한다.",
    ),
    "P34-014": (
        "P37-014",
        "KR5127450215의 성과 기준이 되는 지수는 무엇이며, 주식성 자산에는 최대 어느 정도까지 편입할 수 있나요?",
        "지수추종/투자전략 대신 성과 기준, 자산비중 대신 편입 상한을 사용한다.",
    ),
    "P34-015": (
        "P37-015",
        "KR510902773M C-e의 연 단위 보수 비율과 일정 기간 투자했을 때 금액으로 적힌 비용은 각각 무엇을 뜻하나요? 두 수치를 같은 방식으로 보면 안 되는 이유도 알려주세요.",
        "총보수율과 기간별 비용 예시의 field boundary를 단위/기간/금액으로 묻는다.",
    ),
    "P34-016": (
        "P37-016",
        "KR510902773M과 KR510902777M의 투자위험 분류 숫자를 나란히 제시하고, 숫자가 작을수록 위험이 커지는지 판단해 주세요.",
        "두 product risk value와 ordinal direction을 별도 factual requirement로 둔다.",
    ),
    "P34-017": (
        "P37-017",
        "KR5114420022와 KR5114450222의 안정성 등급 표시는 각각 몇 단계인가요? 상대적으로 위험이 낮다고 볼 상품도 근거와 함께 비교해 주세요.",
        "위험등급 대신 안정성 단계와 상대 위험 판단으로 product comparison을 시험한다.",
    ),
    "P34-018": (
        "P37-018",
        "KR5120420039와 KR5120420091의 리스크 분류 단계를 각각 알려주고, 그중 위험 수준이 더 낮게 표시된 상품을 찾아 주세요.",
        "투자위험 분류와 낮은 단계 표현을 리스크/위험 수준으로 바꾼 two-product factual comparison이다.",
    ),
}


def _specs() -> tuple[dict, ...]:
    return tuple(
        {**base, "question_id": qid, "question": question, "freshness_note": note}
        for base in P34_SPECS
        for qid, question, note in (QUESTION_VARIANTS[base["question_id"]],)
    )


def _existing_questions() -> list[tuple[str, str]]:
    records = []
    paths = [*sorted((ROOT / "evaluation").glob("*.json")), *sorted((ROOT / "evaluation").glob("*.jsonl"))]
    for path in paths:
        # P37 runtime/regression files reproduce frozen P37 questions and are
        # not prior question banks.  Tests may monkeypatch MANIFEST_PATH.
        if path.name.startswith("p37") or path.name == MANIFEST_PATH.name:
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
    declared = {chunk_id for spec in specs for group in spec["evidence_groups"] for chunk_id in group}
    missing = sorted(declared - corpus_ids)
    if missing:
        raise SystemExit(f"P37 declares missing corpus chunk IDs: {missing}")
    normalized = {_normalise_question(spec["question"]): spec["question_id"] for spec in specs}
    if len(normalized) != len(specs):
        raise SystemExit("P37 has duplicate normalised questions")
    overlaps = [
        {"new_question_id": normalized[_normalise_question(question)], "prior_file": path, "prior_question": question}
        for path, question in _existing_questions()
        if _normalise_question(question) in normalized
    ]
    if overlaps:
        raise SystemExit("P37 has exact normalised question overlap: " + json.dumps(overlaps, ensure_ascii=False))

    manifest = {
        "version": "1.0",
        "status": "frozen_before_pre_hcx_execution",
        "purpose": "P37 fresh Closed factual front-end generalisation after P36-B; no HCX before the pre-HCX gate.",
        "candidate": "P36-B generalized canonicalization candidate",
        "scope": {
            "included": ["institution", "tax", "procedure", "compound closed", "product factual", "product factual comparison"],
            "excluded": ["personalised recommendation", "suitability", "clarify", "abstain", "prompt injection", "external real-time information"],
        },
        "denominators": {"total": len(specs), "answerable": len(specs), "unsupported": 0},
        "pre_hcx_go_criteria": {
            "semantic_requirement_coverage": 1.0,
            "evidence_sufficiency": 1.0,
            "original_primary": 1.0,
            "source_relevance_exact_or_semantic_equivalent": 1.0,
            "partial": 0,
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
        "declared_gold_chunk_ids": len(declared),
        "missing_declared_gold_chunk_ids": 0,
        "group_counts": dict(sorted(Counter(spec["category"] for spec in specs).items())),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        label = str(MANIFEST_PATH.relative_to(ROOT))
    except ValueError:  # unit tests use a temporary output path
        label = str(MANIFEST_PATH)
    print(json.dumps({"manifest": label, "sha256": manifest["manifest_sha256"], **manifest["validation"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
