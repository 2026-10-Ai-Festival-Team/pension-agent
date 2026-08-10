# P7: Merged-Context HCX 파일럿

## 목적

P6-B에서 retrieval이 개선된 R-037과 R-028에 대해, requirement별 retrieval과 merged context가 실제 답변 품질까지 개선하는지 확인했다.

이번 주 실험은 orchestration 효과와 모델 효과를 분리하기 위해 **HCX-DASH-002**로 고정했다. HCX-007의 P6-A 결과와 합산하거나 orchestration 효과로 해석하지 않는다.

## 고정 조건

- Model: HCX-DASH-002
- Corpus: 23,421 chunks, Simple BM25, `pension-v1`
- A: 원 질문 BM25 Top-10 중 기존 Agent와 같은 앞 5개 Context
- B: requirement별 Top-10 검색 후 중복 제거, requirement slot을 만족하는 merged Context
- Citation binding prompt, full `chunk_id` subset validator, Fail-Closed, 2초 global interval, retry 정책 유지
- 각 A/B를 두 번 반복
- R-024는 negative control이며 HCX에 호출하지 않음

## 결과 요약

| Case | Variant | Requirement evidence | Citation contract | Semantic 결과 | 판정 |
|---|---|---|---|---|---|
| R-037 | A 기존 Context | 불완전 | 2/2 통과 | 압류 근거만 인용하면서 운용 책임·수익·위험을 근거 밖으로 추가 | 실패 |
| R-037 | B merged Context | 전체 | 2/2 통과 | DB는 회사, DC는 근로자가 적립금을 운용한다고 직접 답변 | 성공 |
| R-028 | A 기존 Context | 불완전 | 2/2 통과 | “투자대상 정보가 제공되지 않는다”로 질문을 충족하지 못함 | 실패 |
| R-028 | B merged Context | 전체 | 0/2 통과 | 동등한 투자전략 표를 선택했지만 `source_id`만 인용해 차단 | 보류 |
| R-024 | negative | 불완전 | HCX 미호출 | 투자대상·위험등급 근거 없음 | 정상 차단 |

모든 실제 호출은 HTTP 200과 재시도 0회였다. 수용 여부와 semantic quality는 별도 지표로 유지했다.

## R-037 before/after

### A: 기존 Context

기존 Top-5는 모두 퇴직연금 압류 문서였다. citation ID 자체는 유효했지만, 답변은 문서에 없는 DB/DC 책임·수익·위험 설명까지 추가했다. 즉 **valid citation은 relevance나 grounding을 보장하지 않는다**는 P3/P4 결론이 재현됐다.

### B: merged Context

`DB 적립금 운용 주체`, `DC 적립금 운용 주체` 검색을 분리한 뒤 동일한 DB/DC 비교 표 하나를 selected Context로 전달했다. 두 반복 모두 다음 요구를 충족했다.

- DB: 회사가 적립금을 운용
- DC: 근로자가 직접 적립금을 운용
- complete `chunk_id` 인용
- 질문과 무관한 압류·수익·위험 설명 없음

| 지표 | A 평균 | B 평균 |
|---|---:|---:|
| Generation latency | 4,357ms | 1,245ms |
| Total tokens | 2,055 | 540 |
| Context chunks | 5 | 1 |

R-037에서는 merged context가 품질뿐 아니라 Context 길이와 latency도 줄였다.

## R-028 before/after

P6-B의 `투자대상`·`운용전략` retrieval은 같은 상품의 `table-fdab...` 동등 근거를 회수했다. 이 표에는 국내 주식·장기성장주 중심 투자 및 운용전략이 있어 질문의 핵심을 지지한다.

그러나 HCX-DASH-002는 두 반복 모두 full `chunk_id`가 아닌 `ac97d050d2b39ec2` source ID를 `cited_chunk_ids`에 반환했다. validator는 이를 자동 보정하지 않고 차단했다. 따라서 B의 answer semantic correctness는 평가 대상이 아니며, “retrieval 성공”을 “E2E 성공”으로 과장하지 않는다.

## R-024 negative control

Requirement별 query를 실행해도 투자대상과 위험등급 evidence가 완결되지 않았다. P7은 HCX를 호출하지 않았고 `blocked_incomplete_requirement_evidence`로 기록했다. 이는 information-limit handling의 정상 결과다.

## 결정

**Needs refinement — production 미통합.**

P7은 R-037에서 다음 가설을 반복적으로 지지했다.

```text
requirement별 retrieval
→ relevant merged context
→ citation-bound generation
→ 정확하고 짧은 근거 기반 답변
```

하지만 R-028은 동일한 merged-context 방식에서도 DASH-002의 source ID 인용 재발 때문에 Fail-Closed 통과에 실패했다. 따라서 다음 작업은 전체 routing 통합이 아니라, DASH-002에서 citation binding이 어떤 Context 구성에서 source ID로 흔들리는지 독립적으로 재현·분류하는 것이다.

R-024는 별도 retrieval backlog로 유지한다. Corpus·BM25·generation 정책 변경을 한 실험으로 섞지 않는다.

## 재현

```bash
# .env가 HCX-DASH-002를 가리킬 때만 실행된다.
python3 scripts/run_p7_merged_context_hcx_pilot.py --runs 2
```

실제 answer와 provider diagnostic은 Git 제외 파일 `data/diagnostics/p7_merged_context_hcx_pilot.json`에만 저장한다.
