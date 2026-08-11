# P14-A/B/C: 지원 범위 분류와 Requirement-First Routing 실험

## 목적과 범위

P13 holdout에서 확인된 unsupported miss, compound miss, requirement-slot 누락을 한
실험 계층에서 분리해 개선했다.

- **P14-A**: 지원 범위 taxonomy를 이용한 unsupported intent detection
- **P14-B**: 복수 evidence requirement 기반 compound routing
- **P14-C**: subject × attribute requirement-slot 생성

변경은 `src/experiments/` 및 experimental Router/Gate에만 적용했다. Production
`PensionAgent`, retrieval/BM25, prompt, HCX, citation validator, Fail-Closed 정책은
변경하지 않았고 HCX 호출도 하지 않았다.

## P14-A: Unsupported intent taxonomy

지원 범위와 단순 evidence 부족을 다음처럼 구분했다.

| Category | 정책 |
|---|---|
| `personal_account_lookup` | 개인/소속 회사 계좌의 잔액·수익률·보유 현황은 문서 Corpus로 답하지 않고 reject |
| `unavailable_external_information` | 오늘/최신/실시간처럼 Corpus 기준일 밖의 정보는 reject |
| `unsupported_recommendation_or_prediction` | 사용자 조건 없이 최고 수익 상품을 고르거나 예측하는 요청은 reject |
| supported | 문서 근거로 답할 수 있는 제도·세제·상품·절차 질문 |

P13의 H-017~H-020은 모두 이 taxonomy로 unsupported로 분류됐다. 이 분류는
`insufficient`과 다르다. `insufficient`은 질문은 지원 범위지만 현재 검색 근거가
부족한 경우이며, unsupported는 요청 자체가 제공 문서 기반 답변 범위를 벗어난 경우다.

## P14-B/C: Requirement-first route와 slot

`RequirementBuilder`는 검색 전에 명시 subject와 attribute를 다음 형태의 slot으로
구조화한다.

```text
product codes × requested fields
→ 각 상품코드마다 모든 요구 속성 생성
```

예를 들어 두 상품의 위험등급·총보수를 비교하면 네 slot을 만든다. 따라서 기존의
“첫 번째 상품코드만 slot 생성” 문제가 제거됐다.

비상품 compound도 DB/DC 급여·운용, 제도전환, 규약+동의, 중도인출 사유+절차,
연금·일시금 과세를 requirement plan으로 표현한다. Coupled eligibility처럼 하나의
표/규칙에서 완결되는 질문은 single-fact plan으로 남긴다.

각 slot에는 표시 문자열과 별도로 canonical key를 보존한다. P13 평가에서 gold의
`연금 수령 과세 시점`과 생성된 `연금 수령 과세 시점`처럼 의미는 같지만 표시 방식이
다른 슬롯을 exact string mismatch로 잘못 세지 않기 위한 측정 보정이다. 이 key 추가는
Router/Gate의 의사결정을 변경하지 않는다.

## 동일 P13 holdout 재평가

P13은 이제 개선에 사용됐으므로 이 결과는 development regression이지 새로운 일반화
수치가 아니다. 기존 baseline artifact는 유지하고 P14 결과를 별도 JSONL로 저장했다.
기존 P9 dev 15문항 회귀도 15/15를 유지했으며 false rejection과 unsafe pass는 모두
0건이었다. 기존 40문항 전체 수치는 더 이상 독립 검증 지표로 사용하지 않는다.

| Metric | P13 baseline | P14 regression |
|---|---:|---:|
| Routing accuracy | 12/20 (60.0%) | 19/20 (95.0%) |
| Compound recall | 5/8 (62.5%) | 7/8 (87.5%) |
| Unsupported recall | 0/4 | 4/4 |
| False rejection | 4/16 (25.0%) | 2/16 (12.5%) |
| Unsafe pass | 4/4 | 0/4 |
| Requirement-slot generation recall | 4/19 (21.1%) | 16/19 (84.2%) |
| Entity precision | 100.0% | 100.0% |
| Entity recall | 85.7% | 92.9% |

## 남은 실패

| Case | Stage | 원인 | Owner |
|---|---|---|---|
| H-009 | Support classification | `DB제도` 안의 `제`를 possessive marker로 잘못 해석해 supported compound를 unsupported로 분류 | support classifier |
| H-015 | Evidence gate | 연금 수령 연령은 매칭됐지만 최소 수령기간 slot의 후보 근거가 Top-10에서 selector 조건을 충족하지 못함 | slot matcher / retrieval |

H-009 때문에 supported→unsupported 1건이 남아 unsupported precision은 80%다. H-015와
H-009는 evidence sufficient로 라벨된 질문이 reject되어 false rejection 2건을 구성한다.

## 판단

**Needs refinement — HCX Shadow E2E 및 production 통합 보류.**

P14는 P13의 가장 위험한 경로였던 unsupported unsafe pass를 0으로 만들고, compound 및
slot generation을 크게 개선했다. 하지만 production candidate 기준인 false rejection
≤5%를 만족하지 못했고, H-009의 support classifier false positive는 안전 정책을 과도하게
만드는 명확한 결함이다.

다음 단계는 P13 결과를 다시 tuning하지 않고 다음과 같이 분리한다.

1. P14 failure inventory를 기반으로 support classifier의 possessive boundary와 H-015
   evidence-slot owner를 수정한다.
2. 수정 후 새 P15 mini-holdout에서 Router/Gate를 재검증한다.
3. P15에서도 unsupported safety와 false-rejection 기준을 충족할 때만 HCX Shadow E2E를
   검토한다.

## 재현

```bash
PYTHONPATH="$PWD/.venv/lib/python3.9/site-packages" \
  python3 scripts/evaluate_p13_holdout.py \
    --output evaluation/p14_requirement_first_results.jsonl
```

이 실행은 retrieval과 Router/Gate만 평가하며 HCX를 호출하지 않는다.
