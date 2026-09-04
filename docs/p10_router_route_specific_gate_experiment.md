# P10: Router + Route-specific Gate 구현 실험

## 범위

P10은 production `PensionAgent`에 연결하지 않은 experimental Router/Gate 구현이다.

1. P10-A: Korean-boundary-safe entity extraction
2. P10-B: deterministic `simple` / `compound` / `unsupported` Router
3. P10-C: route-specific evidence gate

Retriever, Corpus, BM25, prompt, HCX 호출 경로, existing EvidenceAssessor와 validator는 변경하지 않았다.

## P10-A: entity extraction

새 `EntityExtraction`은 `DB`, `DC`, `IRP`, `연금저축`, 상품코드, 세제 의도, 비교 신호를 결정적으로 기록한다.

- `DB형`, `DC형`, `IRP로`처럼 한국어 조사와 붙은 ASCII 약어를 인식한다.
- `DB·DC`, `DB/DC`, `DB, DC` 기호 결합을 인식한다.
- `DBMS`, `DCON` 같은 ASCII 부분문자열은 account entity로 인식하지 않는다.
- legacy `QueryAnalysis.entities`, `requires_comparison`과 existing Agent gate는 P10-A에서 변경하지 않았다.

## P10-B Router

| Route | Rule-based 조건 |
|---|---|
| `unsupported` | personal account 또는 user-condition recommendation |
| `compound` | 복수 entity 비교, 복수 독립 요구 항목, 해지+세제 조건 |
| `simple` | 하나의 direct fact 또는 하나의 표로 완결되는 질문 |

예외적으로 R-001처럼 DB/DC를 포함해도 하나의 비교 표가 같은 축(운용 주체)을 완결하면 `simple`로 둔다. 이는 “entity 수만으로 compound를 결정하지 않는다”는 통제다.

## P10-C Route-specific Gate

```text
simple
→ Top-10에 evidence가 존재하고 product-code 일치 시 통과

compound
→ requirement slot별 evidence를 모두 선택할 수 있을 때만 통과

unsupported
→ generation 전 차단
```

Compound gate는 P5의 requirement slot과 동일한 deterministic selector를 사용한다. 이 구현은 실험용이며 current Agent의 non-empty-context gate를 교체하지 않는다.

## Offline 결과: P9 gold routing set

| Metric | P9 current | P10 experimental |
|---|---:|---:|
| Routing accuracy | 10/15 (66.7%) | 15/15 (100%) |
| Routing misclassification | 5 | 0 |
| Gate false rejection | 0 | 0 |
| Gate unsafe pass | 4 | 0 |

P10 compound gate는 R-010, R-024, R-028, R-037을 incomplete로 차단했다. P10 simple gate는 R-009을 통과시켜 P8-B에서 발생한 experimental compound-gate false rejection을 제거했다.

## 해석과 한계

이 결과는 **P9의 15개 dev-oriented gold routing set에 대한 offline 결과**다. Rule이 그 subset의 문구와 P5 requirement case에 맞춰져 있으므로, 100%를 일반화하거나 production 성능으로 보고하면 안 된다.

특히 아직 검증되지 않은 항목은 다음과 같다.

- 40개 전체 질문과 test split의 route generalization
- HCX generation·citation·semantic E2E 품질
- R-004의 simple selection failure
- R-001 structured-output failure
- R-024 retrieval missing의 별도 해결

## 결정

**Experimental pass / production integration 보류.**

다음 단계에서 이 Router/Gate를 별도 integration branch에 연결하더라도, 먼저 전체 40문항 offline routing/gate 평가와 limited HCX E2E canary를 수행해야 한다. 현재 단계는 production 구현을 승인하지 않는다.

## 변경 파일

- `src/orchestration/query_analyzer.py`
- `src/experiments/routing_gate.py`
- `scripts/evaluate_p10_routing_gate.py`
- `tests/orchestration/test_query_entity_extraction.py`
- `tests/experiments/test_routing_gate.py`
