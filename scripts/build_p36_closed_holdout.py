"""Freeze P36, a new Closed factual holdout, before any P36 execution.

P36 intentionally reuses verified corpus facts but not prior question wording.
It tests concept composition rather than P35's exact aliases: the candidate
must generalise from a fresh Korean surface form into the same factual
requirement schemas.  Running the companion evaluator is prohibited until
this manifest has been written and hashed.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

try:  # Support both ``python scripts/...`` and test-package imports.
    from build_p34_closed_holdout import SPECS as P34_SPECS
except ModuleNotFoundError:  # pragma: no cover - import mode dependent
    from scripts.build_p34_closed_holdout import SPECS as P34_SPECS


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "evaluation/p36_closed_holdout_manifest.json"


def _normalise_question(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", value).casefold()


# These are newly authored P36 surface forms, not paraphrases used as agent
# rules. The source schemas and evidence groups remain the pre-verified P34
# factual contracts; each question changes the expression or composition being
# tested while retaining a Closed, document-answerable answer.
QUESTION_VARIANTS = {
    "P34-001": (
        "P36-001",
        "DB와 DC에서 적립금 관리는 각각 누가 맡고, 퇴직 뒤 받는 금액은 어떤 기준으로 정해지나요? DC에 회사가 넣어야 하는 최소 금액도 함께 알려주세요.",
        "운용 주체·급여 산정·회사 부담금의 세 축을 ‘관리/받는 금액’ 표현으로 결합했다.",
    ),
    "P34-002": (
        "P36-002",
        "가입자 교육은 누가 책임지고 시행하나요? 1년에 최소 몇 번인지와 교육 업무를 전문기관에 위임할 수 있는지도 궁금합니다.",
        "직접 실시/외부 맡김 대신 책임·위임이라는 표현으로 교육의 세 requirement를 묻는다.",
    ),
    "P34-003": (
        "P36-003",
        "DC나 IRP에서 일반 ETF 주문을 직접 낼 수 있다면, 두 배로 움직이거나 반대로 움직이는 ETF도 제한 없이 살 수 있나요?",
        "레버리지·인버스의 명칭 없이 상품 특성을 이용해 허용 범위와 제한을 분리한다.",
    ),
    "P34-004": (
        "P36-004",
        "개인연금 저축계좌에만 납입한 경우와 개인형퇴직연금까지 보탠 경우를 비교하면, 세액공제 대상으로 잡히는 납입액 한도는 각각 어디까지인가요?",
        "연금저축/IRP의 정식 명칭이 아닌 확장 표현과 ‘대상 납입액’ 범위를 사용한다.",
    ),
    "P34-005": (
        "P36-005",
        "연금계좌에서 운용수익에 세금을 바로 떼지 않는다고 하면 영영 안 낸다는 뜻인가요? 일반계좌와 비교해 실제 과세되는 때를 설명해 주세요.",
        "과세이연과 ‘세금을 나중에 낸다’ 대신 운용수익·즉시 원천징수 여부로 시점 개념을 묻는다.",
    ),
    "P34-006": (
        "P36-006",
        "국내 거래소에 상장된 해외 ETF의 이익과 분배금을 계좌 밖에서 보유할 때와 연금계좌에 담을 때, 과세 시점이 어떻게 달라지나요?",
        "매매차익/분배금과 일반계좌를 ‘계좌 밖’ 표현으로 바꾸고 두 소득 흐름을 결합했다.",
    ),
    "P34-007": (
        "P36-007",
        "퇴직 전에 연금저축 돈은 일부 인출할 수 있다는데 IRP도 가능한가요? 두 계좌의 허용 사유와 인출 때 세금 기준을 나눠 알려주세요.",
        "‘중간에 찾기’ 없이 퇴직 전·일부 인출이라는 별도 표현으로 계좌별 조건과 과세를 요구한다.",
    ),
    "P34-008": (
        "P36-008",
        "DC 적립금을 퇴직 전에 꺼내려면 어떤 법정 요건을 봐야 하나요? 사유가 있더라도 제출 절차와 입증자료가 필요한지도 알려주세요.",
        "중도인출의 동의어 대신 ‘퇴직 전 꺼내기’와 입증자료를 사용해 조건·절차를 함께 검증한다.",
    ),
    "P34-009": (
        "P36-009",
        "ISA가 끝난 뒤 그 자금을 연금계좌로 이전 납입하려면 마감일이 언제이고, 추가 세액공제 금액은 어떤 산식과 한도로 정해지나요?",
        "‘넘길’ 없이 이전 납입·마감일·산식이라는 표현으로 ISA 두 requirement를 묻는다.",
    ),
    "P34-010": (
        "P36-010",
        "보유 중인 펀드를 환매하지 않은 채 퇴직연금 사업자만 바꾸는 경우, 재직 중인 DB·DC와 IRP는 신청 경로가 어떻게 구분되나요?",
        "실물이전이라는 명칭을 쓰지 않고 보유상품 유지·사업자 변경의 절차 차이를 묻는다.",
    ),
    "P34-011": (
        "P36-011",
        "퇴직연금 안의 ETF는 직접 거래가 가능하다고 들었습니다. 그렇다면 상승·하락 배수를 추종하는 ETF도 같은 대상에 포함되나요?",
        "ETF 제한을 ‘배수 추종’의 의미로 표현해 직접거래와 제한 상품을 동시에 요구한다.",
    ),
    "P34-012": (
        "P36-012",
        "DB에서는 회사와 가입자 중 누가 적립금을 운용하고, DC에서는 누가 운용방법을 정하나요? 두 제도의 퇴직급여 계산 기준도 같이 비교해 주세요.",
        "DB/DC의 운용 역할을 주체별 질문으로 풀고 급여 산정 축을 결합했다.",
    ),
    "P34-013": (
        "P36-013",
        "KR510902773M의 현재 투자위험 분류는 몇 단계인가요? 운용 실적이나 시장 조건에 따라 나중에 다시 조정될 수 있는지도 확인해 주세요.",
        "‘위험등급몇등급’·‘계속 고정’ 대신 분류 단계와 재조정 가능성으로 두 factual claim을 요구한다.",
    ),
    "P34-014": (
        "P36-014",
        "KR5127450215는 특정 지수 성과를 반영하도록 설계된 상품인가요? 주식 관련 자산 편입 비율의 상한도 제시해 주세요.",
        "지수추종/지수를 따라감 대신 성과 반영 설계와 편입 상한으로 전략·비율을 묻는다.",
    ),
    "P34-015": (
        "P36-015",
        "KR510902773M C-e 문서의 매년 적용되는 총보수율과 3년 보유를 가정한 비용 금액은 왜 같은 단위로 읽으면 안 되나요?",
        "총보수와 기간별 예시를 비율·보유 가정·금액이라는 다른 field-boundary 표현으로 분리한다.",
    ),
    "P34-016": (
        "P36-016",
        "KR510902773M과 KR510902777M의 위험 분류 숫자를 각각 확인하고, 숫자가 낮은 쪽이 더 높은 위험을 뜻하는지도 비교해 주세요.",
        "두 코드의 등급값과 ordinal direction을 ‘위험 분류 숫자’로 묻는다.",
    ),
    "P34-017": (
        "P36-017",
        "KR5114420022와 KR5114450222는 각각 몇 단계 위험으로 표시돼 있나요? 그중 보수적으로 분류된 쪽이 어느 상품인지 근거와 함께 비교해 주세요.",
        "‘더 비싼 위험등급’ 대신 등급 단계와 보수적 분류를 사용한 two-product factual comparison이다.",
    ),
    "P34-018": (
        "P36-018",
        "KR5120420039와 KR5120420091의 투자위험 분류를 각각 제시하고, 더 낮은 위험 단계로 적힌 상품을 골라 주세요.",
        "안전 쪽 등급 대신 직접적인 위험 단계 비교를 사용하되 두 값 모두 요구한다.",
    ),
}


def _specs() -> tuple[dict, ...]:
    rows = []
    for base in P34_SPECS:
        question_id, question, freshness_note = QUESTION_VARIANTS[base["question_id"]]
        rows.append({**base, "question_id": question_id, "question": question, "freshness_note": freshness_note})
    return tuple(rows)


def _existing_questions() -> list[tuple[str, str]]:
    records = []
    # Keep the already frozen P36 manifest out of a builder self-check (and
    # keep the same behaviour when tests monkeypatch ``MANIFEST_PATH``).
    excluded = {
        MANIFEST_PATH.name,
        "p36_closed_holdout_manifest.json",
        "p36_closed_pre_hcx.json",
        "p36_current_evidence_revalidation.json",
    }
    paths = [*sorted((ROOT / "evaluation").glob("*.json")), *sorted((ROOT / "evaluation").glob("*.jsonl"))]
    for path in paths:
        # P36 execution/regression artifacts reproduce the frozen P36
        # questions by design.  They are not prior question banks and must
        # not make the builder's self-overlap test fail.
        if path.name in excluded or path.name.startswith("p36"):
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
        raise SystemExit(f"P36 declares missing corpus chunk IDs: {missing}")
    normalized = {_normalise_question(spec["question"]): spec["question_id"] for spec in specs}
    if len(normalized) != len(specs):
        raise SystemExit("P36 has duplicate normalised questions")
    overlaps = [
        {"new_question_id": normalized[_normalise_question(question)], "prior_file": path, "prior_question": question}
        for path, question in _existing_questions()
        if _normalise_question(question) in normalized
    ]
    if overlaps:
        raise SystemExit("P36 has exact normalised question overlap: " + json.dumps(overlaps, ensure_ascii=False))

    manifest = {
        "version": "1.0",
        "status": "frozen_before_pre_hcx_execution",
        "purpose": "P36 fresh holdout: Closed factual front-end generalisation after P35-B. No HCX before the pre-HCX gate.",
        "candidate": "P35-B deterministic Closed front-end regression candidate",
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
        manifest_label = str(MANIFEST_PATH.relative_to(ROOT))
    except ValueError:  # Unit tests use a temporary output path.
        manifest_label = str(MANIFEST_PATH)
    print(json.dumps({"manifest": manifest_label, "sha256": manifest["manifest_sha256"], **manifest["validation"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
