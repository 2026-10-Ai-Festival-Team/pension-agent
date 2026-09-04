# P13: Router/Gate 독립 Holdout 평가

## 목적

P12까지의 기존 40문항은 Router와 Gate 설계에 반복 사용됐으므로 development/regression
set으로 취급한다. P13은 그 문항을 사용하지 않은 20문항 holdout에서 frozen P12
experimental Router와 route-specific Gate를 **HCX 없이** 평가한다.

이번 단계에서는 Router/Gate, retrieval, prompt, validator, production Agent를 수정하지
않았다. 실패는 P14 이후 별도 개선 입력으로만 사용한다.

## 기존 라벨 정합성

P11/P12의 R-030과 R-032는 질문 문자열이 완전히 같지만 gold route가 각각 `simple`과
`compound`다. 이는 모델 오류가 아닌 annotation conflict다. P13 holdout에는 두 문항을
포함하지 않았고, 기존 40문항의 39/40은 이 conflict를 해소한 일반화 성능으로 사용하지
않는다. P13의 독립 holdout에는 route conflict가 없다.

## Holdout 구성과 leakage 방지

| Route | Count | 범위 |
|---|---:|---|
| simple | 8 | 제도·절차·단일 상품 속성 |
| compound | 8 | 비교, 계좌+세제, 복수 상품 속성, 조건+절차 |
| unsupported | 4 | 개인 계좌, 최신 외부 정보, 조건 없는 추천 |
| **Total** | **20** | |

질문은 기존 R-xxx 실패 문장을 단순 치환하지 않고, 다른 요구축과 surface form으로 작성했다.
Gold route, required domain/entity/slot, evidence sufficiency, expected gate decision은 실행
전에 `evaluation/p13_holdout_labels.json`으로 고정했다. 이번 라벨은 1인 adjudicated
라벨이므로 최종 발표 수치에는 2인 독립 검토가 추가로 필요하다.

## Routing 결과

| Metric | Result |
|---|---:|
| Overall accuracy | 12/20 (60.0%) |
| Simple recall | 7/8 (87.5%) |
| Compound precision | 5/6 (83.3%) |
| Compound recall | 5/8 (62.5%) |
| Unsupported recall | 0/4 (0.0%) |

| Gold \ Predicted | simple | compound | unsupported |
|---|---:|---:|---:|
| simple | 7 | 1 | 0 |
| compound | 3 | 5 | 0 |
| unsupported | 4 | 0 | 0 |

주요 라우팅 오류는 다음과 같다.

- H-004: `어느 기간`의 의문사가 comparison signal로 오인돼 simple→compound.
- H-013/H-014/H-015: 복수 절차·조건 요구를 `single_fact`로 보아 compound→simple.
- H-017~H-020: 개인 계좌, 최신성, 조건 없는 복수 추천을 unsupported로 감지하지 못함.

## Gate 결과

| Gate state | Count |
|---|---:|
| Evidence sufficient + pass | 12 |
| Evidence sufficient + reject (false rejection) | 4 |
| Evidence insufficient + reject (correct rejection) | 0 |
| Evidence insufficient + pass (unsafe pass) | 4 |

- False Rejection Rate: **4/16 = 25.0%**
- Unsafe Pass Rate: **4/4 = 100.0%**

이 수치는 Gate 자체만의 문제로 읽으면 안 된다. H-017~H-020의 unsafe pass는 모두
unsupported→simple 라우팅 오류가 먼저 발생해 simple gate가 non-empty 검색 결과를
통과시킨 결과다. false rejection H-004/H-009/H-010/H-016은 compound route에 generic
requirement template이 없거나, H-004가 simple→compound로 오분류된 결과다.

## Requirement slot과 entity extraction

| Metric | Result |
|---|---:|
| Compound gold required slots | 19 |
| Generated slots matched | 4 |
| Required-slot recall | 4/19 (21.1%) |
| Missing slots | 15 |
| Spurious slots | 0 |
| Entity precision | 100.0% |
| Entity recall | 6/7 (85.7%) |

동적 product slot은 H-011의 두 속성을 모두, H-012의 첫 번째 상품 두 속성을 포착했다.
그러나 현재 design은 첫 번째 상품코드만 template으로 만들기 때문에 H-012의 두 번째
상품 두 slot을 놓쳤다. 비상품 compound H-009/H-010/H-013~H-016에는 일반 requirement
decomposition이 없어 slot coverage가 없다.

Entity recall 누락은 H-001의 `확정기여형`(DC 약어 없음), H-010의 `연금계좌`(IRP를
명시하지 않음)처럼 surface entity와 gold entity가 다를 때 발생했다. 이는 entity
extractor가 금융 개념을 추론하지 않고 명시 표현만 기록하는 현재 정책과 일치한다.

## Failure inventory

| Owner | Count | Cases |
|---|---:|---|
| router | 8 | H-004, H-013~H-015, H-017~H-020 |
| requirement template / gate | 4 | H-009, H-010, H-012, H-016 |
| none | 8 | 나머지 |

H-012는 gate가 pass했지만 두 번째 상품의 required slot이 생성되지 않아
requirement completeness 관점에서는 실패로 기록했다. 이는 `gate pass`와 `all required
evidence slots covered`가 같지 않다는 것을 보여준다.

## 결론 및 권고

**Production integration 보류 / P14 HCX Shadow E2E 미진행.**

P13 holdout은 P12의 39/40보다 훨씬 낮은 일반화 성능을 보여줬다. 특히 unsupported
recall 0%, compound recall 62.5%, unsafe pass 4건은 HCX를 호출하기 전에 해결해야 할
blocker다. 다음 개선은 P13 결과를 고정한 뒤 P14로 별도 분리한다.

우선순위는 다음과 같다.

1. unsupported intent의 개인 계좌·최신성·무조건 추천 감지
2. 복수 절차/조건 요청의 compound structural detection
3. 다중 상품코드를 모두 보존하는 product evidence slot 생성
4. generic requirement decomposition과 evidence completeness 평가

수정 후에는 이 holdout을 tuning set으로 바꾸지 말고, 별도의 P14 holdout으로 다시
일반화 평가해야 한다.

## 재현

```bash
PYTHONPATH="$PWD/.venv/lib/python3.9/site-packages" \
  python3 scripts/evaluate_p13_holdout.py
```

질문별 결과는 [p13_holdout_results.jsonl](../evaluation/p13_holdout_results.jsonl)에
저장된다. HCX 호출 수는 0이다.
