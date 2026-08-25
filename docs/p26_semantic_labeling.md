# P26-S: P26 후보 경로 의미 품질 수동 라벨링

## 목적과 범위

P26에서 이미 실행된 40개 응답만 대상으로 의미 품질을 수동 검토했다. HCX를 재호출하거나 Router, RequirementBuilder, Retriever, Prompt, Citation Validator를 변경하지 않았다.

- 실행 원본: `evaluation/p26_candidate_execution.jsonl`
- 실행 원본 SHA-256: `c222cade58a6e755de8b77936600e5bf9e718a4674719f28c2e9960b1eda672f`
- 라벨 파일: `evaluation/p26_semantic_labels.json`
- 라벨 파일 SHA-256: `ca8c410f3d2b81cc3043567ab52d4876e3daf5b012a4b93ad7c8650fb3060a1d`
- 방법: `answer_hash`별 답변, 실제 `cited_chunk_ids`, 원문 chunk를 대조한 1차 수동 검토

`citation_valid`는 인용 ID가 전달된 Context에 존재한다는 계약 검증일 뿐이다. 본 라벨링은 별도로 답변의 사실성, 질문 요구사항 충족, claim의 실제 근거 지지 여부를 판정한다.

## 라벨 정의

| 축 | 값 |
| --- | --- |
| 의미 정확성 | `correct` / `partial` / `incorrect` / `not_evaluable` |
| 요구사항 충족 | `full` / `partial` / `missing` |
| 근거성 | `fully_supported` / `partially_supported` / `unsupported` |
| 정책 동작 | `correct` / `incorrect` / `n/a` |
| Strict Useful | 정확, 요구사항 전체 충족, 근거 완전 지지, 정책 문제 없음일 때 `true` |

`not_evaluable`은 구조화 출력 실패 또는 생성 전 정책 차단으로 답변 의미를 판정할 수 없는 경우에만 사용했다.

## 결과

### 전체 40문항

| 지표 | 결과 | 해석 |
| --- | ---: | --- |
| API 정상 처리 | 40/40 | API 예외 없음 |
| Provider 429 / retry exhaustion | 0 / 0 | 6초 hard pacing이 이번 실행에서는 안정적 |
| 구조화 출력·인용 계약 통과 | 35/35 | HCX가 실제 생성한 35개 답변은 모두 유효한 chunk ID를 인용 |
| 구조화 출력 실패 | 2 | R-004, R-035. HTTP 200이지만 schema 계약 실패 |
| 정책 차단 | 3 | R-019, R-039, R-040 |
| 의미 정확 `correct` | 28/35 | 생성·인용 통과 답변 기준 80.0% |
| 요구사항 전체 충족 | 28/35 | 생성·인용 통과 답변 기준 80.0% |
| claim 완전 근거 지지 | 33/35 | 생성·인용 통과 답변 기준 94.3% |
| **Strict E2E Useful** | **28/38** | **73.7%, 기존 answerable 분모 유지** |

`28/38`은 2개의 원래 unsupported 질문(R-039, R-040)을 제외한 기존 비교 분모를 유지한 값이다. R-019는 평가셋상 answerable 질문이므로 분모에 남겼고, 수동 검토 결과 이 차단은 정당하지 않았다.

### 이전 기준선과 비교

| 실행 | Strict E2E Useful | 비고 |
| --- | ---: | --- |
| P16 baseline | 20/38 (52.6%) | 기존 기본 경로 |
| P22 controlled | 23/38 (60.5%) | Provider 통제 실행 |
| **P26 candidate** | **28/38 (73.7%)** | P24-B 후보 경로 + provenance/금융 정책 + P25-A + 6초 pacing |

P26은 P22보다 5문항, P16보다 8문항 높은 Strict Useful을 기록했다. 이 값은 1차 수동 라벨 결과이므로 세제·제도·상품 문항은 배포 승격 전에 독립 2차 검토가 필요하다.

### Compound 경로

P26 실행 artifact의 `route=compound`는 11문항이었다.

| 지표 | 결과 |
| --- | ---: |
| Compound Strict Useful | **7/11 (63.6%)** |
| 이전 기준의 compound useful | 2건 |
| P24-B 대상 Strict Useful | **3/4** |

P24-B 대상별 결과는 다음과 같다.

| 문항 | P23 원인 | P26 근거 전달 | P26 의미 결과 |
| --- | --- | --- | --- |
| R-010 | evidence incomplete | 성공 | partial — 해지수수료만 답하고 세금상 불이익·예외 누락 |
| R-024 | retrieval missing | 성공 | strict useful |
| R-028 | matcher failure | 성공 | strict useful |
| R-037 | retrieval missing | 성공 | strict useful |

따라서 P24-B는 4개 대상 중 3개에서 실제 E2E 의미 품질 개선으로 이어졌다. R-010은 Retriever나 Matcher 문제가 아니라 생성 단계의 요구사항 누락으로 남았다.

## 실패 분류

| 유형 | 문항 | 의미 |
| --- | --- | --- |
| 구조화 출력 실패 | R-004, R-035 | HTTP 200 응답이었으나 HCX 출력이 Answer 계약을 만족하지 못함 |
| 정책 false rejection | R-019 | 선택 Context에 `DC 법정사유 충족 시 중도인출 가능` 근거가 있는데 생성 전 차단됨 |
| 요구사항 누락 | R-006, R-010, R-034, R-038 | 일부 주장은 맞지만 질문의 필수 조건·수치·사유를 모두 답하지 못함 |
| 수치·조건 혼동 | R-008 | ISA 만기 이전의 조건부 한도를 일반 IRP 세액공제 한도처럼 답함 |
| 질문 무관 답변 | R-011 | 인용 claim은 존재하지만 IRP 이전 후 과세 시점 질문에 답하지 않음 |
| 상품 필드 혼동 | R-033 | 인용 표에 위험등급이 있는데도 정보를 제공할 수 없다고 응답 |
| 정상 정책 차단 | R-039, R-040 | 개인 계좌 수익률 조회 및 개인 조건 없는 단일 상품 추천 요청을 보수적으로 차단 |

R-011은 이번 라벨링의 중요한 예시다. 인용 ID는 유효하고 ‘압류’ 관련 claim도 원문에 존재하지만, 과세 시점이라는 질문 의도와 맞지 않는다. 따라서 Citation Validation과 Query–Evidence–Answer relevance 검증은 별도 계층으로 유지해야 한다.

## 정책 차단 재판정

| 문항 | P26 정책 결과 | 수동 판정 | 이유 |
| --- | --- | --- | --- |
| R-019 | 차단 | **incorrect** | 원문 표와 selected Context가 DC 중도인출의 법정사유 조건을 직접 지지함 |
| R-039 | 차단 | correct | 개인 IRP의 현재 수익률은 제공 문서에 없음 |
| R-040 | 차단 | correct | 개인 위험성향·기간 등 조건 없이 단일 최고수익률 상품을 권유할 수 없음 |

따라서 P26 preparation telemetry의 `known false rejection=0`은 기존 진단 집합 기준 결과이고, 실제 답변 의미 기준으로는 R-019 한 건의 false rejection이 확인됐다.

## P26-S 결론

P26 후보 경로는 Provider 안정성, Citation 계약, P24-B 근거 회수·매칭에서 유효했다. 특히 P24-B 대상 3개가 strict useful로 전환되어 conditional retrieval/matcher 후보를 기본 경로로 승격할 충분한 근거가 생겼다.

다만 production 승격은 바로 확정하지 않는다. 다음 backlog를 분리해 처리해야 한다.

1. **P27 Generation Quality**: R-006, R-010, R-034, R-038의 요구사항 누락과 R-008의 조건·수치 혼동을 대상으로, 근거 선택이 아닌 답변 요구사항 충족을 개선한다.
2. **정책 Gate 회귀**: R-019처럼 직접 근거가 선택됐는데 차단되는 경우를 회귀 fixture로 추가한다. Gate를 전역 완화하지 않고 `DC 법정사유 충족`과 같은 semantic-equivalent 근거를 인식하는지 검증한다.
3. **구조화 출력 안정성**: R-004·R-035의 HTTP 200 schema 실패를 provider 성공과 별도로 재현·분류한다.
4. **독립 2차 라벨 검토**: 세제·제도·상품 40문항의 라벨과 Strict Useful을 다른 검토자가 확인한 뒤 최종 발표 수치로 동결한다.
