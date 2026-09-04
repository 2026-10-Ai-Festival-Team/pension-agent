# P19: Dynamic RequirementBuilder Coverage & Product-field Matcher

## 목적과 고정 범위

P18 shared preparation path에서 확인된 실제 동적 baseline을 개선했다. 목표는
question-ID static case를 사용하지 않고 dynamic `RequirementBuilder`와 field-aware
matcher만으로 compound plan coverage, known false rejection, known unsafe pass를
개선하는 것이다.

고정한 항목은 다음과 같다.

- 공용 `ConditionalRoutingShadowAgent.prepare()` 경로
- frozen Corpus / Simple BM25 / `pension-v1`
- route-specific gate와 Fail-Closed 정책
- HCX, prompt, citation validator, production `PensionAgent`

HCX는 호출하지 않았다.

## P19-A: Dynamic requirement coverage

정적 R-ID case를 복사하지 않고 질문의 subject와 requested attribute 조합에서 다음
general-purpose plan을 만들었다.

| 질문 구조 | Dynamic plan |
|---|---|
| DB/DC 퇴직급여 산정 | DB 급여 산정 + DC 급여 산정 |
| DB→DC 전환 | 전환 가능 여부 + 규약·동의 조건 또는 산정 |
| 퇴직금 vs 퇴직연금 | 지급 방식 + 금융기관 적립/지급 방식 |
| 원리금보장 vs 채권형 | 각 분류 근거 |
| 연금계좌 해지 세금 | 가산세 + 연금외수령 과세 + 예외 |
| DC 중도인출 사유 + 절차/서류 | 사유 + 절차 |
| 회사/근로자 운용 대비 | DB 운용 + DC 운용 |

`중도인출 사유 + 절차/서류`는 단일 법정사유 질문보다 먼저 판별한다. 따라서 복수 요구를
단일 slot으로 축소하지 않는다. DB/DC 운용 주체는 두 evidence slot을 검증하지만 질문 자체는
하나의 직접 사실을 묻는 simple route로 유지한다.

## P19-B: Product-field matcher

기존 `상품코드 + 필드명` lexical match만으로는 목차, 빈 위험등급 변경표, 일반적인
“투자대상이 되는 자산가치” 문장도 실제 투자대상/운용전략 evidence로 통과할 수 있었다.

각 product-field slot에 다음 최소 제약을 추가했다.

- 목차 block은 field evidence에서 제외
- 투자대상: 실제 투자대상 설명 신호(`투자비율`, `주된 투자대상`, `주로 투자`, `이상 투자`) 필요
- 투자전략: 실제 전략·운용 행위 신호 필요
- 위험등급: `1`~`6` 등급의 실제 값 필요하며 `2 등급` 같은 PDF whitespace 변형도 허용
- 동일 product code와 요청 field가 아닌 문구로 slot을 만족시키지 않음

이는 product 특성을 추정하거나 특정 product code에 예외를 둔 것이 아니라, field name이
실제 field value/설명으로 연결되는지를 검증하는 규칙이다.

## Shared-path Full-40 결과

| Metric | P18 baseline | P19 |
|---|---:|---:|
| Shared preparation parity | 40 / 40 | **40 / 40** |
| Routing accuracy | 39 / 40 | **39 / 40** |
| Compound recall | 11 / 12 | **11 / 12** |
| Unsupported recall | 2 / 2 | **2 / 2** |
| Compound dynamic requirement plan | 6 / 12 | **12 / 12** |
| Known false rejection | 4 | **0** |
| Known unsafe pass | 2 | **0** |

P18에서 false rejection이었던 R-002/R-005/R-006/R-027은 각각 dynamic plan과 complete
evidence selection을 갖게 됐다. R-019는 DC 중도인출 법정사유 slot이 불충분한 경우
simple fallback으로 통과하지 않고 reject한다. R-028은 목차/일반 문장을 투자대상으로 오인하지
않으므로 현재 후보가 충분하지 않으면 Fail-Closed한다. R-037도 압류 문서의 흩어진 DB/DC
단어가 운용 주체 evidence로 통과하지 않는다.

## 독립 회귀

P13 development regression과 P15 mini-holdout을 HCX 없이 다시 실행했다.

| Set | Routing | Compound recall | Unsupported recall | False rejection | Unsafe pass | Slot recall |
|---|---:|---:|---:|---:|---:|---:|
| P13 development (20) | 20 / 20 | 8 / 8 | 4 / 4 | 1 | 0 | 19 / 19 |
| P15 mini-holdout (12) | 12 / 12 | 5 / 5 | 3 / 3 | 0 | 0 | 14 / 14 |

P13 H-005의 한 false rejection은 matcher 완화 문제가 아니다. 해당 상품의 실제
`투자위험등급 2등급` chunk는 Corpus에 있으나 original Top-10과 product-field expansion
Top-5에 들어오지 않았다. 불충분한 chunk를 위험등급 근거로 승인하는 대신, 이번 P19에서는
안전한 reject를 유지했다. 이는 **product-field retrieval recall** backlog이며 P19의
RequirementBuilder/matcher 범위에서 추가로 gate를 완화하지 않는다.

## 결정

P19는 shared-path Full-40의 진입 조건을 충족했다.

```text
parity 40/40
dynamic requirement plan 12/12
known false rejection 0
known unsafe pass 0
routing 39/40
unsupported 2/2
```

다만 HCX Shadow E2E 재실행은 자동으로 수행하지 않았다. P13 H-005 retrieval recall 한계는
다음 검색/필드-index 실험의 분리된 backlog로 남긴다. P20을 실행한다면 P19의 shared-path
configuration을 고정하고, 이 backlog를 semantic/generation 개선으로 오해하지 않도록
question-level로 분리해 보고해야 한다.

## 재현

```bash
PYTHONPATH="$PWD/.venv/lib/python3.9/site-packages" \
  python3 scripts/evaluate_p18_shared_shadow_preparation.py

PYTHONPATH="$PWD/.venv/lib/python3.9/site-packages" \
  python3 scripts/evaluate_p13_holdout.py \
  --requirement-retrieval-top-k 5 \
  --output data/diagnostics/p19_p13_development_regression.jsonl

PYTHONPATH="$PWD/.venv/lib/python3.9/site-packages" \
  python3 scripts/evaluate_p13_holdout.py \
  --questions evaluation/p15_mini_holdout_questions.json \
  --labels evaluation/p15_mini_holdout_labels.json \
  --requirement-retrieval-top-k 5 \
  --output data/diagnostics/p19_mini_holdout_regression.jsonl
```

진단 출력은 원문 context를 포함할 수 있으므로 Git에서 제외한다.
