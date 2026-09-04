# P5: Multi-Evidence Orchestration 소규모 실험

## 목적과 범위

P4의 결과를 바탕으로, 전역 BM25 튜닝이나 모델 학습 없이 이미 검색된 BM25 Top-10 안에서 질문별 요구 근거를 선택·조합하면 generation/selection 계열 오류를 줄일 수 있는지 확인한다.

```text
A: 질문 → BM25 Top-10 → 상위 Context → HCX
B: 질문 → 요구 근거 슬롯 → Top-10 내 슬롯별 Context 선택 → HCX
```

이번 구현은 운영 `PensionAgent`를 변경하지 않는다. Corpus 23,421청크, Simple BM25, `pension-v1`, HCX citation 검증과 Fail-Closed 정책도 변경하지 않는다.

## 실험 계약

- 요구 슬롯은 질문이 요청한 비교·조건·항목만 구조화한다. 새 금융 사실이나 새로운 검색 질의를 만들지 않는다.
- 선택기는 기존 Top-10 밖을 검색하지 않는다.
- 슬롯마다 지정된 문자열 조건을 만족하는 기존 chunk 하나를 고르고, 중복 chunk는 제거한다.
- 모든 슬롯을 채우지 못하면 HCX를 호출하지 않고 `blocked_incomplete_requirement_evidence`로 기록한다.
- `cited_chunk_ids`가 선택 Context의 완전한 `chunk_id` 목록에 없으면 결과를 수용하지 않는다.
- test 문항 R-024·R-028·R-036·R-037은 튜닝에 쓰지 않고 retrieval 감사만 수행한다.

케이스와 슬롯 정의는 [p5_multi_evidence_cases.json](/Users/jun/Desktop/연금Agent대회/evaluation/p5_multi_evidence_cases.json)에 있다. 원문 응답이 포함된 실행 결과는 Git 제외 파일 `data/diagnostics/p5_multi_evidence_run.json`에만 저장한다.

## 구현

| 구성 | 역할 |
|---|---|
| `RequirementEvidenceSelector` | Top-10 안에서 슬롯별 lexical coverage가 가장 높은 chunk를 결정적으로 선택 |
| `RequirementAwarePromptBuilder` | 요구 슬롯과 선택된 완전한 `chunk_id`를 HCX에 명시 |
| `run_multi_evidence_experiment.py` | 기본 무호출 coverage 감사 또는 `--execute` HCX 파일럿 실행 |

PDF 표의 줄바꿈으로 `운용\n손익`처럼 분리된 표현은 선택 시에만 공백으로 정규화한다. 원본 chunk text는 바꾸지 않는다.

## 첫 실행 결과 (2026-08-10)

실행 조건은 HCX-DASH-002, global minimum interval 2초, `--execute`였다. 실제 HCX 호출 대상은 dev target 5개와 단일 근거 control 3개다. R-010은 슬롯 부족으로 호출 전에 차단했다.

| 구분 | 수 | 결과 |
|---|---:|---|
| 전체 케이스 | 13 | dev target/control 9개 + test 감사 4개 |
| 실제 HCX 시도 | 8 | HTTP 429 없음 |
| Fail-Closed 수용 | 4 | target 3, control 1 |
| 슬롯 부족 사전 차단 | 1 | R-010의 예외 사유 근거 없음 |
| 감사 전용 | 4 | HCX 미호출 |

이 실행의 4/8은 답변 정확도가 아니라 **구조화 출력과 인용 검증을 통과한 비율**이다. semantic quality 지표로 해석하지 않는다.

### 핵심 대상 before/after

| ID | A에서의 P4 문제 | B가 선택한 Context | B의 실행 결과 | 해석 |
|---|---|---|---|---|
| R-002 | DB→DC 전환용 MAX 식을 일반 DC 산정식으로 오독 | DB 산정 문단 + `460750...table-6f...`의 DC 부담금·운용손익 표 | HCX가 `source_id` 두 개만 반환해 차단 | selection은 올바른 비교 근거를 포함했으나 citation 계약 실패로 semantic 비교 보류 |
| R-011 | Top-10 7위 세금 표 대신 압류 문서 선택 | `7878...table-a362...` 세금 납부 시점·과세이연 표만 선택 | HCX가 `7878...` `source_id`만 반환해 차단 | 질문 관련 Context 선택은 개선됐으나 citation 형식 실패로 semantic 비교 보류 |
| R-010 | 16.5%·예외 근거가 불완전 | 해지 가산세·연금외수령 과세만 선택, 예외 슬롯 없음 | HCX 미호출 | retrieval/evidence incomplete를 generation 오류로 숨기지 않는 정책 확인 |

### 감사 결과

| ID | 슬롯 coverage | 결론 |
|---|---|---|
| R-024 | 투자대상·위험등급 모두 없음 | 실제 retrieval missing 유지 |
| R-028 | 투자대상·운용전략 모두 없음 | 실제 retrieval missing 유지 |
| R-036 | 같은 상품 요약 chunk에서 기준일·운용전략 모두 확인 | exact gold ID와 별개로 semantic equivalent evidence 유지 |
| R-037 | DB·DC 운용 주체 슬롯 모두 없음 | 압류 문서의 lexical overlap을 근거 충족으로 취급하지 않음 |

## 결정

**Production 미통합 / semantic 효과 판정 보류.**

P5의 작은 selection 가설은 R-002·R-011에서 필요한 Context를 실제로 분리해 전달할 수 있음을 보였다. 그러나 동일 실행에서 complete `chunk_id` 대신 `source_id`를 인용한 3건과 빈/비정상 citation 1건이 발생했다. Fail-Closed 정책은 올바르게 이 응답들을 차단했지만, 이 상태에서 accepted answer 수를 A/B semantic 성능으로 비교하면 citation 형식 변동이 selection 효과를 가리게 된다.

다음 판단은 prompt나 Agent를 전역 수정하는 것이 아니라, P1의 citation 표현 재발을 독립적으로 재현·분류한 뒤 동일한 selection 입력으로 제한된 재실행을 수행하는 것이다. 그때만 R-002·R-011의 semantic correctness, requirement coverage, grounding, latency 및 사용량을 A와 B로 비교한다.

## 재현

```bash
# 네트워크 호출 없이 Top-10 slot coverage만 확인
python3 scripts/run_multi_evidence_experiment.py

# .env의 HCX 설정으로 실제 파일럿 실행
python3 scripts/run_multi_evidence_experiment.py --execute
```

실제 실행 전에는 `.env`가 Git 제외 상태이고 `GENERATOR_BACKEND=hcx`인지 확인한다.
