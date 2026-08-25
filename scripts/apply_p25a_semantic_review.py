"""P25-A raw 결과에 대한 수동 semantic review를 안전한 요약으로 분리한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# 실제 답변을 검토한 뒤 answer hash에 연결한다. answer 본문은 diagnostics 밖으로 내보내지 않는다.
REVIEW = {
    ("R-002", 1): ("pass", "DB·DC 산정 방식의 비교를 직접 설명"),
    ("R-002", 2): ("pass", "DB·DC 산정 방식의 비교를 직접 설명"),
    ("R-002", 3): ("pass", "DB·DC 산정 방식의 비교를 직접 설명"),
    ("R-006", 1): ("pass", "DB→DC 전환 절차와 근로자 대표 고지·동의 조건을 설명"),
    ("R-006", 2): ("partial", "일반 규약 변경 사유가 중심이라 DB→DC 전환 조건의 직접성이 약함"),
    ("R-006", 3): ("partial", "일반 규약 변경 사유가 중심이라 DB→DC 전환 조건의 직접성이 약함"),
}


def _report(payload: dict, labels: list[dict]) -> str:
    summary = payload["summary"]
    semantic_pass = sum(item["semantic_answer_ok"] == "pass" for item in labels)
    partial = sum(item["semantic_answer_ok"] == "partial" for item in labels)
    return "\n".join(
        [
            "# P25-A: HCX Citation Contract 반복 검증",
            "",
            "R-002와 R-006은 각각 한 번 결정한 동일 selected evidence·context 순서를 유지한 채 HCX-007에 3회씩 전달했다. Router, retrieval, gate, FinancialAnswerPolicy, validator는 변경하지 않았다.",
            "",
            "## Citation 계약",
            "",
            f"- JSON/schema 통과: {summary['schema_parse_pass']}/{summary['attempted']}",
            f"- full `chunk_id` 반환 및 validator 통과: {summary['citation_validation_pass']}/{summary['attempted']}",
            f"- R-002: {summary['by_question']['R-002']['full_chunk_id']}/3",
            f"- R-006: {summary['by_question']['R-006']['full_chunk_id']}/3",
            "",
            "## Semantic 수동 검토",
            "",
            f"- 직접적·충분한 답변: {semantic_pass}/6",
            f"- 부분 충족: {partial}/6",
            "- R-006의 2회는 full chunk_id를 정확히 인용했지만, 질문의 DB→DC 전환 조건보다 일반적인 퇴직연금규약 변경 사유를 중심으로 답했다.",
            "",
            "## 판정",
            "",
            "**Citation contract: Pass.** full `chunk_id` exact-copy, JSON/schema, strict validator를 6/6 통과했다. source_id 자동 보정이나 validator 완화는 사용하지 않았다.",
            "",
            "**Generation requirement coverage: Backlog.** R-006의 부분 충족은 citation ID 문제가 아니라, 선택된 근거를 질문 요구에 맞게 우선순위화하는 생성 품질 이슈다. P25-B provider stability와 분리해 후속 E2E semantic 평가에서 다룬다.",
            "",
            "원문 HCX 응답과 answer 본문은 `data/diagnostics`에만 저장한다. 이 보고서와 semantic label에는 hash·판정·사유만 포함한다.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, default=ROOT / "data/diagnostics/p25a_citation_contract_raw.json")
    parser.add_argument("--labels", type=Path, default=ROOT / "evaluation/p25a_semantic_labels.json")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/p25a_citation_contract.md")
    args = parser.parse_args()

    payload = json.loads(args.raw.read_text(encoding="utf-8"))
    labels = []
    for row in payload["rows"]:
        key = (row["question_id"], row["run_no"])
        label, note = REVIEW[key]
        answer = row["parsed_answer"] or ""
        row["semantic_answer_ok"] = label
        labels.append(
            {
                "question_id": key[0],
                "run_no": key[1],
                "answer_sha256": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
                "semantic_answer_ok": label,
                "note": note,
            }
        )
    args.raw.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    args.labels.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.labels.write_text(json.dumps(labels, ensure_ascii=False, indent=2), encoding="utf-8")
    args.report.write_text(_report(payload, labels), encoding="utf-8")
    print(json.dumps({"labels": len(labels), "pass": sum(item["semantic_answer_ok"] == "pass" for item in labels), "partial": sum(item["semantic_answer_ok"] == "partial" for item in labels)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
