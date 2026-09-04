# P8: DASH-002 Citation Identifier 재발 진단

## 목적

P7 R-028에서 requirement evidence selection은 성공했지만 HCX-DASH-002가 full `chunk_id` 대신 그 prefix인 `source_id`를 반환한 조건을 격리했다.

Production Agent, retrieval, validator는 변경하지 않았다. `source_id → chunk_id` 자동 변환, fuzzy match, top-1 citation 삽입, validator 완화도 사용하지 않았다.

## 고정 조건

- 대상: R-028
- Evidence: P6-B에서 회수한 동일한 `table-fdab...` semantic equivalent 투자전략 표
- Model: HCX-DASH-002
- 동일 question, evidence text, temperature, maxTokens, rate limiter, retry, Fail-Closed
- 변경 변수: generation prompt 안의 citation identifier representation만 변경

## Identifier exposure 검사

첫 확인 결과, full chunk ID는 source ID prefix를 포함하므로 단순 substring 검사로는 source ID 노출 여부를 판단할 수 없다.

```text
chunk_id = <source_id>-table-<suffix>
```

따라서 source ID가 full chunk ID 밖에 **독립 값으로** 노출되는지만 검사했다. 네 variant 모두 actual source ID의 별도 노출은 없었다. P7 current variant에는 “source_id를 사용하지 말 것”이라는 **literal label**만 있었고, 이는 실제 source ID 값을 노출한 것은 아니다.

## Variant 결과

| Variant | Citation 표현 변경 | Actual source ID 별도 노출 | 반환 | 결과 |
|---|---|---:|---|---|
| A P7 current | 기존 binding prompt | 없음 | source ID prefix | 차단 |
| B minimal | `citation_id`와 짧은 exact-copy 계약만 유지 | 없음 | full chunk ID | 통과 |
| C delimited | `<CITATION_ID>` 태그 사용 | 없음 | source ID prefix | 차단 |
| D whitelist | exact JSON 예시와 허용 full ID 반복 | 없음 | full chunk ID | 통과 |

각 실행은 HTTP 200, 재시도 0회였다. 원문 답변과 provider diagnostic은 Git 제외 진단 파일에만 보관한다.

## B 반복성과 회귀 확인

가장 짧은 성공 representation인 B를 추가로 두 번 반복했다.

| Case | Representation | 반복 | Citation | Semantic 초기 검토 |
|---|---|---:|---|---|
| R-028 | B minimal | 3/3 | full chunk ID 3/3 | 국내 주식·장기성장주·2S 운용전략을 근거에 맞게 설명 |
| R-037 | B minimal | 1/1 | full chunk ID | DB 회사 운용, DC 근로자 운용을 정확히 설명 |

R-028 B의 평균 generation latency는 약 2.18초, 평균 total token은 793이었다. R-037 regression run은 1.13초, 469 token이었다.

## Root cause 판정

**확정된 원인:** actual source ID가 별도 metadata로 prompt에 노출되어 선택된 것은 아니다.

**가장 강한 설명:** DASH-002가 긴 composite `chunk_id`의 source prefix를 인용값으로 축약하는 출력 취약성이다. 기존 contract와 태그 방식은 이 축약을 막지 못했지만, 최소형 또는 exact whitelist representation은 같은 evidence에서 이를 막았다.

literal `source_id` 문구가 유일한 원인이라고 단정할 수는 없다. C는 그 문구를 제거했어도 실패했기 때문이다. 따라서 최소 수정 후보는 “금지할 identifier 목록을 늘리는 것”이 아니라, **citation_id 하나와 exact-copy 계약만 남기는 generation-facing representation**이다.

## P8-B: Conditional Routing 설계안 (구현 보류)

P8-A 결과만으로 production integration을 수행하지 않는다. 이후 후보 설계는 다음과 같다.

```text
Query Analyzer
├─ single-evidence
│  └─ frozen BM25 → 기존 generation context
└─ comparison / multi-topic / conditional
   └─ requirement decomposition
      → requirement별 retrieval
      → merge + completeness assessment
      ├─ incomplete → Fail-Closed / 한계 고지
      └─ complete → minimal citation representation → HCX
```

초기 routing 조건은 질문이 둘 이상의 비교 대상 또는 둘 이상의 독립 요구 항목을 포함하는 경우로 한정한다. 단순 질문에는 기존 경로를 유지한다. R-024처럼 retrieval completeness가 false인 경우에는 merged context라도 HCX를 호출하지 않는다.

## 결정

**P8-A pass, P8-B 설계만 제시, production 구현 보류.**

P8-A는 R-028의 citation contract 문제를 Fail-Closed를 유지한 채 재현·완화할 수 있음을 보였다. 하지만 P7의 orchestration을 전체 Agent에 넣기 전에, 이 minimal representation을 compound dev subset에서 별도로 평가해 citation 안정성·semantic quality·latency의 회귀가 없는지 검증해야 한다.

## 재현

```bash
# R-028의 A/B/C/D 최소 진단
python3 scripts/run_p8_dash002_citation_diagnosis.py

# B representation 반복
python3 scripts/run_p8_dash002_citation_diagnosis.py \
  --variants B_minimal_no_other_identifier B_minimal_no_other_identifier

# R-037 회귀 확인
python3 scripts/run_p8_dash002_citation_diagnosis.py \
  --question-id R-037 --variants B_minimal_no_other_identifier
```
