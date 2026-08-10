# P4: Semantic Relevance & Evidence Completeness 진단

## 목적

P3에서 확인된 semantic error 8건과 `evidence_requirement=all` 3문항을 대상으로, 다음 경로의 실패 위치를 재확인했다. 이 단계에서는 Retriever, Agent, prompt, HCX client를 변경하지 않았다.

```text
query requirement
→ Top-10 retrieved evidence
→ generator가 선택한 evidence
→ answer relevance·coverage
```

상세 case inventory는 [p4_semantic_failure_cases.json](/Users/jun/Desktop/연금Agent대회/evaluation/p4_semantic_failure_cases.json)에 있다.

## 핵심 정정: exact-gold와 evidence completeness는 다르다

기존 `all-evidence@10 = 0/3`은 **사전에 지정한 exact gold chunk ID가 모두 Top-10에 없었다**는 뜻이다. 세 문항 모두 의미적으로 같은 결론은 아니다.

| Case | Exact gold all@10 | 실제 requirement coverage | 결론 |
|---|---:|---|---|
| R-002 | fail | Top-10에 DB 계산 근거와 동등한 DC 산정 표 존재 | 검색 자체보다 evidence selection·generation 해석 문제 |
| R-024 | fail | 투자대상·위험등급 근거 모두 없음 | 실제 retrieval missing |
| R-036 | fail | 같은 상품 요약정보 한 chunk가 기준일·운용전략 모두 제공 | semantic retrieval success |

따라서 exact gold hit 지표는 유지하되, 복합 질문의 개선 전 진단에서는 topic-level equivalent evidence 판정을 함께 사용해야 한다.

## 8개 semantic error의 primary cause

| Primary cause | Cases | Count |
|---|---|---:|
| `generation_misread` | R-002, R-005, R-013, R-027 | 4 |
| `evidence_incomplete` | R-010 | 1 |
| `answer_irrelevance` | R-011 | 1 |
| `retrieval_irrelevant` | R-028 | 1 |
| `retrieval_missing` | R-037 | 1 |

R-011은 특히 중요하다. 세금 납부 시점 gold 표가 Top-10 7위에 존재했지만, HCX가 압류 금지 문서를 선택했다. 즉 valid citation만으로는 query relevance를 보장할 수 없다.

## 필요 요구항목과 evidence 상태

| Case | Required topics | Top-10 | Selected citation | Answer |
|---|---|---|---|---|
| R-002 | DB 산정, DC 산정, 차이 | full (equivalent 포함) | partial | DC 산정식 오해 |
| R-010 | 가산세, 연금외수령 과세, 예외 | partial | partial | 16.5% 등 누락 |
| R-011 | IRP 이전, 과세 시점, 과세이연 | full | none | 압류 답변으로 이탈 |
| R-013 | 의무이전 원칙, 예외 | full | full | 예외를 생략 |
| R-027 | 원리금보장 분류, 채권형 펀드 분류 | full | full | 두 행을 같은 분류로 오독 |
| R-028 | 투자대상, 운용전략 | none | none | 일반 가격변동 문장 |
| R-037 | DB 운용 주체, DC 운용 주체, 비교 | none | none | 압류보호 답변 |

## 우선순위 결정

현재 8개 오류의 다수는 Retriever가 근거를 전혀 찾지 못한 경우가 아니다.

- retrieval primary failure: R-028, R-037 (2건)
- evidence incomplete: R-010 (1건)
- retrieved evidence가 있었지만 generator가 잘못 선택·해석·요구를 생략: R-002, R-005, R-011, R-013, R-027 (5건)

따라서 다음 구현은 BM25의 전역 튜닝이 아니라, **질문별 requirement coverage를 사용해 context를 고르는 multi-evidence orchestration**을 우선 검토하는 것이 근거가 있다. 다만 P4는 진단 단계이므로 아직 sub-query decomposition, reranking, prompt 변경을 적용하지 않는다.

## P5 실험 가설

다음 실험은 아래를 모두 보존한 작은 범위여야 한다.

- corpus, BM25 파라미터, `pension-v1`, citation fail-closed 유지
- comparison/compound query에서 required topic별 evidence를 최소 하나씩 선택
- topic coverage가 부족하면 HCX 호출 대신 근거 한계를 고지
- R-002, R-011, R-013, R-027에서 선택 context와 answer relevance가 개선되는지 dev에서만 측정
- R-024, R-028, R-037은 retrieval missing으로 별도 추적하고, test 결과를 보고 튜닝하지 않음
