# P27-C: Full-40 구조화 출력 안정성 재인증

## 목적

P27-A/B 이후 다음 고정 candidate 조합을 실제 HCX-007로 40문항 재실행했다.

```text
P24-B candidate retrieval/matcher
+ provenance / financial policy
+ P25-A citation contract
+ P27 output contract
+ HCX-007
+ request-start 6초 hard pacing
```

실행 도구의 단일 세션 제한을 피하기 위해 20문항씩 두 배치로 나눴다. 두 배치는 병렬 실행하지 않았고, 배치 안에서는 각각 6초 hard pacing을 적용했으며 배치 사이 간격도 6초보다 길었다.

## 결과

| Go 기준 | 결과 | 판정 |
| --- | ---: | --- |
| API 정상 처리 | 40/40 | 통과 |
| HTTP 429 | 0 | 통과 |
| HTTP 5xx | 0 | 통과 |
| timeout | 0 | 통과 |
| provider retry exhaustion | 0 | 통과 |
| 실제 최소 request-start 간격 | 6101.807ms / 6106.679ms | 통과 |
| 빈 최종 answer | 0 | 통과 |
| 생성 성공 답변의 빈 citation 배열 | 0 | 통과 |
| Citation validator 실패 | 0 | 통과 |
| R-019 정상 통과 | 통과 | 통과 |
| R-039/R-040 안전 차단 | 2/2 | 통과 |
| **JSON/schema failure** | **6** | **실패** |

Provider attempt는 총 51회였고 모두 HTTP 200이었다. 38개 질문이 생성 대상으로 판단됐으며, 이 중 32개만 구조화 출력과 인용 검증까지 통과했다.

## 구조화 출력 실패

실패 문항은 R-001, R-004, R-007, R-011, R-022, R-025다.

모두 `JSONDecodeError`였으며 P27-A의 Gate나 Citation Validator 실패가 아니다. 진단된 출력 형태는 다음 패턴으로 나뉜다.

```text
설명 문장 + JSON 본문
설명 문장 + ```json fenced JSON
문자열 앞뒤의 prose / markdown fence
```

즉 P26에서 확인했던 빈 JSON(`answer=""`, `cited_chunk_ids=[]`)은 이번 실행에서 재발하지 않았지만, HCX-007이 JSON-only 지시를 따르지 않고 출력 모드를 섞는 문제가 Full-40에서 6건 발생했다.

P27의 strict parser는 이 출력을 수용하지 않았으며, Citation Validator나 Fail-Closed 정책을 완화하지 않았다. 이 동작은 안전성 측면에서는 올바르지만, P27-C의 `JSON/schema failure = 0` 인증 조건에는 미달한다.

## R-019 및 정책 경로

R-019는 다음 상태로 복구됐다.

```text
route: simple
evidence_sufficient: true
assessment_reason: simple_requirements_complete
generator_called: true
cited_chunk_ids: [4607500e74afcdf8-table-6f164502cbce]
```

R-039와 R-040은 `unsupported_or_personal_or_conditional`로 생성기 호출 없이 계속 차단됐다.

## 판정

**P27-C: No-Go**

P27-B의 빈 출력 계약 강화는 격리 호출에서는 효과를 보였지만, Full-40에서는 JSON-only 출력 안정성을 인증하지 못했다. 따라서 새 `answer_hash`에 대한 semantic labeling과 P26의 28/38 재현 비교는 진행하지 않는다.

다음 작업은 Planner/Writer/Verifier나 semantic generation 개선이 아니라, 이 6건의 `JSONDecodeError`를 raw output 형태별로 재현·분류하는 구조화 출력 안정성 진단이어야 한다. Parser를 무조건 느슨하게 하거나 Citation Validator를 완화해서 해결하지 않는다.

## 산출물

- `data/diagnostics/p27c_batch_01_raw.json` (Git 제외)
- `data/diagnostics/p27c_batch_02_raw.json` (Git 제외)
- `evaluation/p27c_batch_01_execution.jsonl`
- `evaluation/p27c_batch_02_execution.jsonl`
