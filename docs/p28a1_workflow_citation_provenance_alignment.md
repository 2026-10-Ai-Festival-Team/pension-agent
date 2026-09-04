# P28-A1: Workflow Citation/Provenance Contract Alignment

## 목적

P28-A에서 Verifier와 Repair가 P27-E의 `selected context ∩ original ∩ primary` 인용 경계를 일관되게 상속하지 못해 발생한 citation/provenance 실패를 제거한다. Planner, Retrieval, Gate, Writer의 의미 품질 규칙은 변경하지 않았다.

## 구현

- Retrieval/Gate 직후 `FrozenEvidenceBundle`을 만든다.
- bundle에는 selected context 중 `source_type=original` 및 `authority_level=primary`인 근거와 해당 `chunk_id`만 보관한다.
- Writer, Verifier, Repair는 bundle의 context를 동일하게 재사용한다. 새 검색이나 새 근거 추가는 허용하지 않는다.
- HCX-007 Native Structured Outputs의 `cited_chunk_ids.items.enum`을 매 호출마다 bundle의 허용 `chunk_id`로 생성한다.
- 기존 strict parser와 애플리케이션 citation validator는 유지한다. source ID 자동 변환, fuzzy 보정, validator 완화는 없다.
- Verifier의 REVISE 문구는 누락 항목을 지적하는 진단일 뿐, Repair에 새로운 금융 사실을 공급하지 않도록 명시했다.

## HCX 없는 계약 테스트

다음을 unit test로 고정했다.

- augmented ID와 selected context 밖 ID를 Writer/Repair 허용 집합에서 제외
- Verifier의 Native Schema에도 동일한 `enum`을 적용
- context 목록과 허용 ID 목록의 불일치 및 중복 ID를 거부
- 단계별 boundary violation에 Writer/Verifier/Repair stage를 남김

관련 테스트와 전체 회귀 결과: `199 passed`.

## 5문항 Citation Contract 재호출

대상은 `R-006`, `R-019`, `R-011`, `R-035`, `R-002`(control)이며, HCX-007 Native Structured Outputs와 6초 hard pacing을 유지했다.

| 항목 | 결과 |
|---|---:|
| Schema/HTTP 200 | 5/5 |
| Writer citation subset | 5/5 |
| Verifier citation subset | 5/5 |
| Repair citation subset (repair 4건) | 4/4 |
| primary-original citation | 5/5 |
| 자동 ID 보정 / validator 완화 | 0 |
| R-002 contract regression | 0 |

## 동일 P28-A 12문항 재실행

진단 산출물: `data/diagnostics/p28a1_contract_alignment_12cases.json`.

| 항목 | 결과 |
|---|---:|
| Cases | 12/12 |
| Workflow errors | 0 |
| Writer/Verifier schema success | 12/12 |
| Writer/Verifier/Repair/final citation subset | 12/12 |
| final primary-original citation | 12/12 |
| Repairs | 7 |
| HCX calls | 31 |
| 429 / provider exhaustion | 0 |

## 의미 품질 A/B

새 answer hash 기준 수동 라벨은 `evaluation/p28a1_semantic_labels.json`에 기록했다.

| 집합 | P27-E single-pass | P28-A1 workflow | 변화 |
|---|---:|---:|---:|
| backlog 8개 strict useful | 0/8 | 1/8 | +1 |
| control 4개 strict useful | 4/4 | 4/4 | 0 |

`R-010`은 연금외수령 과세, 해지가산세 없음, 부득이한 사유 예외까지 답해 strict useful로 전환됐다. `R-006`, `R-019`, `R-034`, `R-011`, `R-033`, `R-035`, `R-038`은 각각 requirement omission, numeric/product-field confusion, answer irrelevance가 남았다.

Verifier가 오류 신호를 낸다고 해서 Repair가 의미 품질을 반드시 개선하지는 않았다. 예를 들어 `R-011`, `R-035`는 repair 후에도 질문의 핵심 요구를 답하지 못했다. 반면 control 4개는 의미 회귀 없이 유지됐다.

## 판정

**Citation/Provenance Contract: Go**

모든 workflow 단계가 P27-E의 `primary-original + selected-subset + strict validator` 계약 안에서 동작했다.

**Selective Workflow Semantic Expansion: No-Go**

12문항에서 control 회귀는 없었지만 backlog 개선은 1/8에 그쳐, 사전 기준인 3~4개 strict useful 전환에 미달했다. 따라서 Full-40 workflow 확장은 하지 않는다. 이후 개선은 Verifier의 단순 오류 감지보다, requirement coverage와 product-field 의미 구분을 실제 답변으로 반영하는 generation 전략을 별도 실험으로 다룬다.
