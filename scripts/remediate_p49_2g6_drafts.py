"""Create P49-2G6 remediation drafts without mutating v4 or Gold Seed v1."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "evaluation/fine_tuning"
V4_POSITIVE = BASE / "p49_draft_gold_training_records_v4.jsonl"
V4_CONTRASTIVE = BASE / "p49_draft_contrastive_records_v4.jsonl"
V5_POSITIVE = BASE / "p49_draft_gold_training_records_v5.jsonl"
V5_CONTRASTIVE = BASE / "p49_draft_contrastive_records_v5.jsonl"
CORPUS = ROOT / "data/parsed/chunks.jsonl"
HEADER_CHUNK = "9175b4d6847de4c3-paragraph_group-f2fb35f40652"


HISTORICAL_FACTS = [
    "2016.07.02: 1등급→3등급; 5단계에서 6단계로 분류체계가 개편되고 최근 3년 주간수익률 변동성이 10% 초과 15% 이하다.",
    "2021.03.31: 3등급→2등급; 최근 3년 주간수익률 변동성이 15% 초과 25% 이하다.",
    "2024.03.28: 2등급→3등급; 최근 3년 주간수익률 변동성이 10% 초과 15% 이하다.",
    "2025.03.28: 3등급→2등급; 산정기준이 표준편차에서 VaR로 바뀌고 최근 3년 일간수익률의 최대손실예상액(VaR) 기반 변동성을 사용한다.",
]
HISTORICAL_ANSWER = (
    "변경 이력은 다음과 같습니다. 2016.07.02에는 1등급에서 3등급으로 바뀌었고, "
    "5단계에서 6단계로의 분류체계 개편 및 최근 3년 주간수익률 변동성 10%초과 15%이하가 사유입니다. "
    "2021.03.31에는 3등급에서 2등급으로 바뀌었고 최근 3년 주간수익률 변동성 15%초과 25%이하가 사유입니다. "
    "2024.03.28에는 2등급에서 3등급으로 바뀌었고 최근 3년 주간수익률 변동성 10%초과 15%이하가 사유입니다. "
    "2025.03.28에는 3등급에서 2등급으로 바뀌었고, 산정기준이 표준편차에서 VaR로 변경되었으며 "
    "최근 3년 일간수익률의 최대손실예상액(VaR)에 따른 수익률변동성이 사유입니다."
)


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write(path: Path, records: list[dict]) -> None:
    path.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8")


def _case(record_id: str) -> str:
    return record_id.rsplit("-", 2)[-2].upper() + "-" + record_id.rsplit("-", 1)[-1]


def _completion(answer: str, cited_chunk_ids: list[str]) -> str:
    return f"[답변] {answer}\n[근거] {', '.join(cited_chunk_ids)}\n[유의사항] 없음"


def _corpus_evidence(chunk: dict) -> dict:
    return {
        "chunk_id": chunk["chunk_id"],
        "text": chunk["text"],
        "provenance": "original_primary",
    }


def _remediate(record: dict, header: dict) -> dict:
    output = json.loads(json.dumps(record, ensure_ascii=False))
    output["schema_version"] = "p49.training_draft.v3"
    output["quality"]["manual_review"] = "pending_p49_2g6_evidence_first_audit"
    key = _case(output["record_id"])

    if key in {"P45-011", "P48-011"}:
        output["direct_evidence"] = [_corpus_evidence(header), *output["direct_evidence"]]
        output["cited_chunk_ids"] = [item["chunk_id"] for item in output["direct_evidence"]]
        output["evidence_anchors"] = ["1,000만원", "1년", "2년", "3년", "5년", "10년"]

    # Evidence names the annual "판매회사 보수" field.  Do not train a
    # stronger sales-fee distinction unless direct sales-fee evidence is added.
    if "판매수수료" in output["question"]:
        output["question"] = output["question"].replace("판매수수료", "판매회사 보수")
        output["completion"] = output["completion"].replace("판매수수료", "판매회사 보수")
        output["quality"]["required_facts"] = [
            fact.replace("판매수수료", "판매회사 보수") for fact in output["quality"]["required_facts"]
        ]
        output["factual_claims"] = [
            fact.replace("판매수수료", "판매회사 보수") for fact in output["factual_claims"]
        ]

    if key == "P47-010":
        output["question"] = output["question"].replace("1년 기준 총보수·비용률", "연간 총보수·비용률")

    if key == "P48-002" and output["record_type"] == "positive_draft":
        output["question"] = "확정기여형 퇴직연금에서 회사 부담금의 법정 최저 기준은 얼마인가요?"

    if output["record_id"] == "contrastive_draft-p47-008":
        output["question"] = "KR5113420012의 현재 위험등급과 향후 변경 가능성만 알려주세요."
        output["unrequested_field_tokens"] = []

    if key == "P46-016":
        output["completion"] = output["completion"].replace("DB제도은", "DB제도는")

    if key == "P48-009":
        output["completion"] = _completion(HISTORICAL_ANSWER, output["cited_chunk_ids"])
        output["quality"]["required_facts"] = HISTORICAL_FACTS
        output["factual_claims"] = HISTORICAL_FACTS
        output["evidence_anchors"] = [
            "2016.07.02", "2021.03.31", "2024.03.28", "2025.03.28",
            "10%초과 15%이하", "15%초과 25%이하", "일간", "VaR",
        ]

    return output


def main() -> None:
    corpus = {chunk["chunk_id"]: chunk for chunk in _rows(CORPUS)}
    header = corpus.get(HEADER_CHUNK)
    if header is None:
        raise RuntimeError(f"missing header-preserving chunk: {HEADER_CHUNK}")
    if not all(token in header["text"] for token in ("1년", "2년", "3년", "5년", "10년")):
        raise RuntimeError("replacement header chunk is not table-integral")
    positive = [_remediate(record, header) for record in _rows(V4_POSITIVE)]
    contrastive = [_remediate(record, header) for record in _rows(V4_CONTRASTIVE)]
    if len(positive) != 19 or len(contrastive) != 19:
        raise RuntimeError("P49-2G6 requires a 19/19 source bundle")
    _write(V5_POSITIVE, positive)
    _write(V5_CONTRASTIVE, contrastive)
    print(json.dumps({"positive": len(positive), "contrastive": len(contrastive), "status": "draft_remediated"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
