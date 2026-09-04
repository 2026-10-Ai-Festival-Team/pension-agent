# 답변 품질 평가 스키마

## 목적

이 평가는 시스템의 HCX 호출 성공률과 답변의 의미적 품질을 분리한다. retrieval·citation contract는 코드로 측정하고, 사실성·수치·claim-to-evidence 대응은 생성된 답변을 보고 사람이 판정한다. 평가 파이프라인에는 HyperCLOVA X 외의 LLM을 사용하지 않는다.

## 실행 흐름

```text
40문항 HCX E2E run (Git 제외 diagnostics)
→ review packet 생성 (답변·검색 근거·gold 근거 병렬 표시)
→ 수동 라벨링
→ run SHA-256 검증 후 집계
```

`answer_sha256`과 `run_sha256`은 라벨이 정확히 어떤 생성 답변과 평가 실행에 대응하는지 확인한다. answer 원문과 검색 근거는 사측 문서 내용이므로 `data/diagnostics/`에서만 다룬다.

## 자동 측정

| 항목 | 정의 |
|---|---|
| Direct evidence hit@10 | answerable 질문의 gold relevance=2 chunk가 Top-10에 하나 이상 있는지 |
| All evidence hit@10 | `evidence_requirement=all` 질문의 gold direct chunk가 모두 Top-10에 있는지 |
| Unlabeled retrieved chunks | gold relevant set 밖의 Top-10 수. gold가 완전한 비관련성 라벨이 아니므로 `irrelevant`로 단정하지 않음 |
| Citation contract | cited ID가 선택된 context ID이고 최종 answer에 표시됐는지 |
| Policy path | unsupported, evidence rejection, generation/citation rejection, generated answer를 구분 |

## 수동 라벨

각 필드는 `pass`, `fail`, `not_applicable`, `not_reviewed` 중 하나다.

| Field | 판정 기준 |
|---|---|
| `factual_correctness` | 답변의 사실이 선택·인용 근거와 일치하는가 |
| `numeric_fidelity` | 세율·금액·연령·기간 등 수치가 근거 그대로인가 |
| `requirement_coverage` | 질문이 요구한 조건·절차·설명 항목을 빠뜨리지 않았는가 |
| `evidence_grounding` | citation ID가 valid한 것에 더해, answer claim을 실제로 지지하는가 |
| `hallucination` | 문서 밖 사실·수치·상품코드가 없는가 (`pass` = 없음) |
| `premise_correction` | 잘못된 질문 전제를 필요할 때 교정했는가 |
| `comparison_coverage` | 비교·복합 질문에서 대상별 근거를 모두 다뤘는가 |
| `information_limit_handling` | 근거 부족 시 한계 고지·확인 질문·정책 거절이 적절한가 |

`HCX Accepted Answer Rate`는 이 수동 라벨의 정확성 점수와 절대 합산하지 않는다. transport/429/JSON/citation rejection은 semantic-quality 분모에서 제외하고 별도 운영 지표로 보고한다.

## 명령

```bash
python scripts/evaluate_agent_hcx.py \
  --output data/diagnostics/agent_hcx_quality_run.json \
  --report data/diagnostics/agent_hcx_quality_transport.md

python scripts/build_answer_quality_review_packet.py \
  --run data/diagnostics/agent_hcx_quality_run.json \
  --output data/diagnostics/answer_quality_review_packet.jsonl \
  --summary data/diagnostics/answer_quality_automated_summary.json
```

라벨링 완료 후 packet의 `review` 값을 채운 복사본을 전달하고 다음을 실행한다.

```bash
python scripts/summarize_answer_quality.py \
  --run data/diagnostics/agent_hcx_quality_run.json \
  --reviews data/diagnostics/answer_quality_reviewed.jsonl \
  --output data/diagnostics/answer_quality_manual_summary.json
```
