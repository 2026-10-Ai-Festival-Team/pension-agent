# P12: Router 일반화와 Requirement/Gate 범위 검증

## 목적과 고정 조건

P11에서 발견된 두 blocker를 분리해 검증했다.

1. **P12-A Router 일반화**: non-P9의 compound→simple 사례를 question-ID 또는 단일 문구로
   하드코딩하지 않고, 질문 구조에서 복수 요구 속성을 감지한다.
2. **P12-B Requirement/Gate 범위**: R-006 false rejection과 R-019 unsafe pass를
   requirement slot 관점에서 재현·판정한다.

Production `PensionAgent`, BM25/Corpus/normalizer, HCX, generation prompt, validator,
Fail-Closed 정책은 변경하지 않았다. 이번 결과는 offline shadow Agent의 결과이며 HCX를
호출하지 않았다.

## P12-A: non-P9 compound detection

### 원인 분석

| Case | 질문 구조 | P11 원인 | P12 처리 |
|---|---|---|---|
| R-032 | 판매수수료·총보수의 **공통 표시 위치** | R-030과 질문 문장이 동일하지만 gold route가 다름 | 라벨 정합성 이슈로 분리; shared-location 구조는 simple 유지 |
| R-033 | 상품코드 + 상품명 + 위험등급 | 복수 상품 속성 signal 부재 | `product_code + 2 requested_fields`로 compound |
| R-034 | 상품코드 + 총보수 + 투자대상 | 복수 상품 속성 signal 부재 | 같은 구조 규칙으로 compound |
| R-036 | 상품코드 + 기준일 + 운용전략 | 복수 상품 속성 signal 부재 | 같은 구조 규칙으로 compound |

R-030과 R-032는 정확히 같은 질문이다. 따라서 R-032만 compound가 되도록 수정하는 것은
route rule이 아니라 라벨 과적합이다. 두 질문은 “두 값 자체”가 아니라 그 값들의 **공통
확인 위치**를 묻는 하나의 evidence request로 판단해 `simple`을 유지했다. P12는 R-032를
남은 gold-label reconciliation 항목으로 기록한다.

일반화 규칙은 상품코드가 있는 질문에서 `상품명`, `위험등급`, `보수`, `투자대상`,
`운용전략`, `기준일` 같은 서로 다른 정보 필드가 둘 이상이면 compound로 보낸다. 다만
“어디에 표시/어디에서 확인”처럼 하나의 공통 위치를 묻는 질문은 simple로 유지한다.

## P12-B: Requirement/Gate

### R-006 — false rejection 해소

P11에서는 gold route를 compound로 맞혔지만 P5에 template이 없어서
`compound_requirements_not_defined`로 차단됐다. P12 전용 template은 문서 ID가 아니라
다음 semantic slot을 요구한다.

- DB→DC 제도전환 가능 여부
- 제도전환 절차의 퇴직연금규약·동의 조건

기존 Top-10에서 두 slot이 각각 선택되어 `compound_requirements_complete`가 됐다.

### R-019 — unsafe pass 제거

P11의 simple gate는 non-empty Top-10만으로 통과시켰다. P12에서는 DC 중도인출의
**계정별 법정사유·요건**을 하나의 semantic slot으로 정의하고, account label과 법정사유
용어가 같은 좁은 evidence span에 있어야 한다고 요구했다. 이는 IRP 설명과 DC 표현이
넓은 chunk에 섞여 있는 경우를 DC 요건 근거로 잘못 채택하지 않기 위한 구조적 제약이다.

현재 Top-10에는 이 slot을 충족하는 국소 DC 근거가 없어 `simple_requirements_incomplete`로
사전 차단됐다. 이는 HCX 호출을 막는 안전한 결과이며 retrieval/decomposed retrieval의
후속 과제로 남긴다.

### 복수 상품 속성의 일반 slot

R-033/R-034처럼 template 파일에 없는 product-code compound 질문에는 질문 ID별 rule을
추가하지 않았다. 상품코드와 각 요청 속성을 묶은 동적 slot을 만들어, product metadata가
있는 검색 결과에서만 통과시켰다. `상품명` slot은 제목이 있는 동일 상품 근거도 요구한다.

## Full-40 Offline Shadow 결과

`false/unsafe`는 P3에서 semantic sufficiency가 `full`/`partial`/`none`으로 이미 검토된
질문에 대해서만 집계했다. 기존 HCX format/transport 실패로 semantic 검토가 없던 7문항은
`unknown`으로 분리했다.

| Subset | P11 routing | P12 routing | P11 false rejection | P12 false rejection | P11 unsafe pass | P12 unsafe pass |
|---|---:|---:|---:|---:|---:|---:|
| P9 dev (15) | 15/15 | 15/15 | 0 | 0 | 0 | 0 |
| Non-P9 (25) | 21/25 | 24/25 | 1 | 0 | 1 | 0 |
| Full 40 | 36/40 | 39/40 | 1 | 0 | 1 | 0 |

P12의 non-P9 1건은 R-032이며, Router rule regression이 아니라 R-030과 충돌하는 gold route
라벨이다. 이 라벨을 독립 검토로 정정하거나, 별도 holdout에서 shared-location 질문을
검증하기 전에는 25/25라고 보고하지 않는다.

## 결정

**Offline 개선 확인 / HCX Shadow E2E 보류.**

P12는 P11에서 관측된 known false rejection과 unsafe pass를 모두 제거하고, non-P9
compound→simple 구조적 miss를 4건에서 1건의 라벨 충돌로 줄였다. 그러나 P11/P12의 40문항은
이제 Router와 Gate 설계에 사용됐으므로 더 이상 독립 holdout이 아니다. 또한 7문항은 prior
semantic sufficiency가 `unknown`이다.

다음 단계(P13)는 rule을 추가하지 않고 새 holdout 15~30문항을 독립 라벨링해
simple/compound/unsupported와 gate safety를 먼저 평가해야 한다. P13 holdout에서 다음을
확인한 뒤에만 동일 조건의 HCX Shadow E2E를 실행한다.

- shared-location 질문의 route 일관성
- product-code 복수 속성 질문의 compound recall
- known false rejection = 0 유지
- known unsafe pass = 0 유지
- P9/P11 simple control 과탐 없음

## 재현

```bash
PYTHONPATH="$PWD/.venv/lib/python3.9/site-packages" \
  python3 scripts/evaluate_p12_shadow_offline.py
```

Git 제외 artifact `data/diagnostics/p12_shadow_offline.json`에 질문별 route, entity,
requested fields, slot, gate decision, 선택 chunk와 HCX 미실행 상태가 저장된다.
