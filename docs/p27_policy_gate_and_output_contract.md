# P27: R-019 정책 차단 및 구조화 출력 계약 격리 검증

## 목적

P26-S에서 확인된 시스템성 실패만 분리해 수정·검증했다.

- P27-A: R-019의 false rejection
- P27-B: R-004·R-035의 HTTP 200 구조화 출력 실패

이번 단계에서는 Retriever, P24-B matcher, Router의 전역 규칙, Citation Validator, provenance 정책, 6초 pacing을 변경하지 않았다. 기본 `PensionAgent`도 변경하지 않았고 P26 candidate 경로만 검증했다.

## P27-A — R-019 false rejection

### 원인

R-019는 `DC형에서 중도인출을 하려면 어떤 조건을 충족해야 하나요?`라는 질문이다. selected Context에는 다음의 직접 원문 근거가 있었다.

```text
DC제도 | ... | 법정사유 충족시 중도인출 가능
```

하지만 기존 `dc_withdrawal_conditions` 슬롯은 `무주택`, `요양`, `파산`처럼 IRP 문서의 개별 사유까지 요구했다. DB/DC 비교표는 이 사유를 열거하지 않으므로, 원문 근거가 있어도 슬롯 매칭이 실패했다.

### 최소 수정

`dc_withdrawal_conditions` 슬롯을 다음의 직접 의미 조건으로 바꿨다.

```text
기존: DC 에서 중도인출 + 무주택/요양/파산
변경: DC + 중도인출 + 법정사유
```

모든 세 용어가 같은 근거 범위에서 확인되어야 하며, 정책을 전역 완화하거나 IRP 사유를 DC 근거로 자동 대체하지 않는다.

### 오프라인 회귀

| 항목 | 결과 |
| --- | --- |
| Full-40 preparation 변화 | R-019 한 건만 변경 |
| R-019 gate | `simple_requirements_incomplete` → `simple_requirements_complete` |
| R-039 개인 계좌 조회 | 계속 `unsupported`, 차단 유지 |
| R-040 무조건 추천 | 계속 `unsupported`, 차단 유지 |
| P24-B 대상 R-010/R-024/R-028/R-037 | 모두 gate 통과 유지 |
| P15 mini-holdout 회귀 | 0건 |

### 실제 HCX-007 격리 호출

R-019는 HTTP 200으로 실제 호출됐고, 다음처럼 원문 표의 `chunk_id`를 인용해 답했다.

```text
DC형에서 중도인출을 하기 위해서는 법정사유를 충족해야 합니다.
```

따라서 P27-A는 **Go**다.

## P27-B — R-004·R-035 구조화 출력 계약

### P26 원인 분류

두 P26 실패는 JSON 문법 오류가 아니었다. HCX가 HTTP 200과 함께 아래 형태를 반환했다.

```json
{"answer":"","cited_chunk_ids":[]}
```

즉 원인은 `malformed_json`이 아니라 `empty_answer + empty_cited_chunk_ids`라는 **빈 출력 계약 위반**이다. 기존 strict parser가 이 응답을 거부한 동작 자체는 옳았다.

### 최소 수정

1. Generation prompt에 빈 `answer`와 빈 `cited_chunk_ids`를 명시적으로 금지했다.
2. 빈 JSON이 다시 오면 parser를 완화하지 않고 다음 진단 값을 남긴 채 실패시킨다.

```text
response_contract_failures:
- empty_answer
- empty_cited_chunk_ids
```

3. 기존 API/테스트 계약의 `citation_validation_reason=missing_citation`과 `returned_cited_chunk_ids=[]`는 유지했다.

### 실제 HCX-007 격리 호출

| 문항 | 최종 출력 계약 | 의미 품질 판정 | 해석 |
| --- | --- | --- | --- |
| R-035 | 유효 JSON·유효 인용 | 별도 재라벨 필요 | P26의 빈 JSON은 재발하지 않았다. 다만 original gold retrieval miss 문제와는 별개다. |
| R-004 | 재시도 후 유효 JSON·유효 인용 | 아직 미흡 | 첫 attempt는 `답변:` 형식의 일반 문장으로 JSON 계약을 어겼고, 제한 재시도 후 JSON으로 회복했다. 최종 답변은 직접 근거가 있는데도 정보가 없다고 해 semantic 개선으로 계산하지 않는다. |

이 결과는 빈 JSON을 방치하지 않고 strict contract를 유지한 채 recover할 수 있음을 보인다. 그러나 R-004의 첫 attempt에서 형식 모드 이탈이 있었으므로, **P27-B를 Full-40 구조화 출력 안정성 인증으로 선언하지는 않는다.** 다음 controlled E2E에서 schema 실패율을 다시 집계해야 한다.

## 검증

```text
pytest: 190 passed
```

추가 회귀 테스트는 다음을 고정한다.

- DC 법정사유 표만으로 R-019 requirement slot을 충족하는지
- 빈 answer·빈 인용 배열을 strict parser가 거부하고 세부 원인을 남기는지
- prompt가 빈 JSON을 명시적으로 금지하는지

## P27 결론

| 축 | 판정 |
| --- | --- |
| P27-A R-019 false rejection | **Go** |
| P27-B 빈 JSON 진단·계약 강화 | **Go (격리 검증)** |
| P27-B Full-40 schema 안정성 | 아직 미인증 |
| 기본 Agent production 승격 | 보류 |

다음 우선순위는 큰 구조 변경이 아니라 P26-S에서 남은 실제 generation 품질 문제다. R-006, R-010, R-034, R-038의 요구사항 누락, R-008의 조건·수치 혼동, R-011의 질문 무관 답변, R-033의 상품 필드 혼동을 P28 generation-quality 진단 대상으로 분리한다. R-004·R-035는 다음 controlled E2E에서 구조화 출력 실패와 semantic quality를 별도로 재라벨링한다.
