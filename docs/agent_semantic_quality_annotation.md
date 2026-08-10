# P3: Semantic Quality 1차 Annotation

## 범위와 분모

P2 run (`SHA-256: 0af114e2e07ae041f9749fc455c7a0d3396ed2ac859690542886997a56f5ec7f`)의 실제 answer, cited chunk, retrieved context를 1차 검토했다. 이 문서는 시스템 변경이나 튜닝 결과가 아니라 현재 품질의 관측값이다.

```text
40 total
├─ 2 unsupported policy response
├─ 38 answerable
│  ├─ 6 HCX transport / malformed JSON failure       ← semantic 분모 제외
│  ├─ 1 citation rejection                           ← semantic 분모 제외
│  └─ 31 accepted answer                             ← P3 semantic 분모
```

라벨은 answer와 context를 직접 대조한 assistant-assisted 1차 검토다. 세제·제도처럼 해석 민감도가 높은 사례는 최종 발표 수치로 사용하기 전에 팀원의 독립적인 2차 검토가 필요하다.

## 라벨 기준

| 축 | 값 |
|---|---|
| Retrieval sufficiency | `full` / `partial` / `none` |
| Answer correctness | `correct` / `minor_error` / `major_error` |
| Requirement coverage | `full` / `partial` / `none` |
| Grounding | `fully_supported` / `partially_supported` / `unsupported` |
| Unsupported claim | `none` / `minor` / `major` |
| Information-limit handling | `appropriate` / `inappropriate` / `not_applicable` |

`Grounding`은 answer가 말한 claim을 cited chunk가 지지하는지를 본다. 질문과 무관한 claim이라도 cited chunk가 그 claim을 지지할 수 있으므로, `Answer correctness`와 별도로 기록한다.

## 31개 accepted answer 결과

| ID | Retrieval | Correctness | Coverage | Grounding | Unsupported claim | Limit | Primary attribution |
|---|---|---|---|---|---|---|---|
| R-001 | full | correct | full | fully_supported | none | appropriate | - |
| R-002 | full | major_error | full | partially_supported | major | appropriate | Top-10의 동등한 DC 산정 표 대신 DB→DC 전환 계산식을 일반 DC 산정식으로 사용 |
| R-003 | full | correct | full | fully_supported | none | appropriate | - |
| R-004 | full | correct | full | fully_supported | none | appropriate | - |
| R-005 | full | minor_error | full | fully_supported | minor | appropriate | DB 설명의 ‘매년 정해진 금액’ 표현이 근거보다 좁음 |
| R-006 | full | correct | full | fully_supported | none | appropriate | - |
| R-007 | full | correct | full | fully_supported | none | appropriate | - |
| R-008 | full | correct | full | fully_supported | none | appropriate | gold가 아니어도 ISA 전환 관련 동등 근거 사용 |
| R-009 | full | correct | full | fully_supported | none | appropriate | - |
| R-010 | partial | minor_error | partial | partially_supported | minor | appropriate | 2.2%만 제시하고 연금외수령 16.5% 등 핵심 세금 조건 누락 |
| R-011 | full | major_error | none | fully_supported | none | inappropriate | gold 세금 근거가 Top-10에 있었지만 과세 시점 대신 압류 금지 문서를 선택 |
| R-013 | full | major_error | partial | partially_supported | major | appropriate | IRP 의무이전 예외를 누락해 ‘반드시’라고 단정 |
| R-014 | full | correct | full | fully_supported | none | appropriate | 회사가 계약한 금융기관 등 조건은 근거 내에 있음 |
| R-015 | full | correct | partial | fully_supported | none | appropriate | ‘방법’ 질문에 납입 방식·한도만 답해 절차 설명 부족 |
| R-018 | full | correct | full | fully_supported | none | appropriate | - |
| R-019 | partial | correct | partial | fully_supported | none | appropriate | 법정사유·구체 요건 대신 ‘일정 조건’만 제시 |
| R-020 | full | correct | partial | fully_supported | none | appropriate | 무주택·본인 명의 조건을 생략 |
| R-021 | full | correct | full | fully_supported | none | appropriate | - |
| R-022 | full | correct | full | fully_supported | none | appropriate | - |
| R-023 | full | correct | full | fully_supported | none | appropriate | - |
| R-025 | full | correct | full | fully_supported | none | appropriate | - |
| R-026 | full | correct | full | fully_supported | none | appropriate | - |
| R-027 | full | major_error | full | partially_supported | major | appropriate | 원리금보장 운용방법과 채권형 펀드의 분류를 같은 것으로 잘못 요약 |
| R-028 | partial | major_error | none | unsupported | major | inappropriate | 투자대상·운용전략 질문에 일반 가격변동 문장만 답함 |
| R-029 | full | correct | full | fully_supported | none | appropriate | 위험등급 숫자 방향은 표현상 오해 소지 있으나 cited 표와 실질적으로 일치 |
| R-030 | full | correct | full | fully_supported | none | appropriate | - |
| R-031 | full | correct | full | fully_supported | none | appropriate | - |
| R-032 | full | correct | full | fully_supported | none | appropriate | - |
| R-036 | full | correct | full | fully_supported | none | appropriate | gold와 다른 동등한 같은 상품 설명서 근거 사용 |
| R-037 | none | major_error | none | fully_supported | none | inappropriate | DB/DC 운용 주체 비교 대신 압류보호 답변 |
| R-038 | full | correct | full | fully_supported | none | appropriate | gold와 다른 동등한 IRP 중도인출 근거 사용 |

## Unsupported policy cases

| ID | Response | Information-limit handling | 판정 |
|---|---|---|---|
| R-039 | 개인 IRP 수익률은 문서 근거가 부족하다고 고지 | appropriate | pass |
| R-040 | 투자 기간·위험 성향·운용 목적을 질문 | appropriate | pass |

## 집계

분모는 accepted answer 31개다.

| Metric | 결과 |
|---|---:|
| Retrieval sufficiency: full | 27/31 (87.1%) |
| Retrieval sufficiency: partial / none | 3 / 1 |
| Semantic correctness: correct | 23/31 (74.2%) |
| Semantic correctness: minor / major error | 2 / 6 |
| Requirement coverage: full | 23/31 (74.2%) |
| Requirement coverage: partial / none | 5 / 3 |
| Fully supported grounding | 26/31 (83.9%) |
| Partially supported / unsupported grounding | 4 / 1 |
| No unsupported claim | 25/31 (80.6%) |
| Minor / major unsupported claim | 2 / 4 |
| Information-limit handling inappropriate | 3/31 |
| Unsupported policy handling | 2/2 |

Strict하게 `correct` + `full coverage` + `fully supported grounding`을 모두 만족한 answer는 20개다. 따라서 현재 run의 **End-to-End Useful Answer Rate (strict)** 는 `20 / 38 = 52.6%`다. 이 값은 HCX Accepted Answer Rate와 다르며, transport·format·citation 거부 7건은 분자에 포함하지 않고 answerable 38개를 분모로 둔다.

## Failure attribution 및 다음 우선순위

| Failure family | Cases | 해석 |
|---|---|---|
| Multi-evidence / retrieval completeness | R-002, R-010, R-019, R-020 | 필요한 조건 또는 복수 근거가 Top-10/선택 context에서 누락·희석 |
| Wrong-context answer despite valid citation | R-011, R-037 | citation은 실제 claim을 지지하지만 질문 의도와 무관 |
| Evidence policy / conditional answer | R-013 | retrieved evidence 안의 예외·조건을 답변이 누락 |
| Table/section interpretation | R-027, R-028 | 표의 분류 또는 상품의 핵심 항목을 잘못 읽거나 답변 범위를 벗어남 |
| Coverage-only omission | R-015, R-019, R-020 | 사실은 맞지만 질문의 조건·절차를 완결하지 못함 |

다음 개선은 이 결과를 바탕으로 하나만 선택해야 한다. 가장 직접적인 후보는 복합·조건 질의에서 gold/equivalent evidence가 모두 선택되도록 하는 **multi-evidence orchestration** 이다. 단, P3 결과만으로 retrieval 튜닝을 시작하지 않고, 위 1차 라벨의 팀원 2차 검토를 마친 뒤 결정한다.
