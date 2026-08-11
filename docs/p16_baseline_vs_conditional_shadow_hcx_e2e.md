# P16: Baseline vs Conditional-Routing Shadow HCX E2E

## 목적과 고정 조건

P15 Router/Gate offline 통과 뒤, 기존 baseline Agent와 experimental
conditional-routing Shadow Agent를 실제 HCX로 비교했다. 목적은 HCX 호출률이 아니라
**같은 38개 answerable 질문에서 Strict End-to-End Useful Answer Rate가 개선되는지**를
확인하는 것이다.

두 run은 다음을 고정했다.

- 40개 고정 평가 질문, 원본 Corpus 23,421 chunks, Simple BM25 + `pension-v1`
- HCX-DASH-002, `maxTokens=800`, temperature 0
- global minimum interval 2초, bounded retry, 같은 response parser
- 기존 citation subset validator 및 Fail-Closed 정책
- baseline 실행 → 10초 cooldown → shadow 실행 순서

Shadow에서 바뀐 것은 conditional route뿐이다.

```text
simple    → 기존 retrieval / 기존 generation prompt
compound  → requirement plan / requirement candidate expansion /
            completeness gate / merged evidence / minimal citation representation
unsupported·insufficient → HCX 미호출
```

Production `PensionAgent`는 변경하지 않았다. answer·context·raw provider diagnostic은
사측 문서 내용을 포함하므로 `data/diagnostics/`에만 저장했다.

## 시스템·계약 지표

| Metric | Baseline | Conditional shadow |
|---|---:|---:|
| Total / answerable / unsupported | 40 / 38 / 2 | 40 / 38 / 2 |
| HCX attempted | 38 | 32 |
| Pre-generation rejection | 2 | 8 |
| HTTP 429 (attempt history) | 18 | 9 |
| Retry count | 13 | 6 |
| Retry exhaustion | 6 | 4 |
| JSON/schema failure | 1 | 1 |
| Citation rejection | 1 | 0 |
| Accepted answers | 31 | 28 |
| HCX Accepted Answer Rate | 81.6% | 87.5% |
| Mean / p50 / p95 total latency | 3248 / 2382 / 7144 ms | 2384 / 2034 / 4668 ms |
| Total input / output tokens | 138,354 / 3,926 | 105,305 / 3,043 |
| Total run duration | 129.9 s | 95.4 s |

Shadow의 Accepted Answer Rate·지연·토큰 총량이 좋아 보이는 주된 이유는 6건을 더
HCX 호출 전 차단했기 때문이다. 따라서 이 값은 답변 품질 개선 증거가 아니며, semantic
품질 및 false rejection과 함께 해석해야 한다.

두 run은 같은 설정으로 순차 실행했지만 외부 provider의 순간적인 rate-limit 상태까지
동일하게 통제할 수는 없다. 실제 429 빈도 차이도 route 효과로 해석하지 않았으며, 아래
semantic 평가는 각 run에서 검증을 통과해 수용된 실제 answer를 별도로 검토한 결과다.

## Answer-hash 기반 semantic review

각 run에서 수용된 answer는 별도 `run_sha256`·`answer_sha256` packet으로 생성했다.
P3 라벨을 재사용하지 않고 이번 answer와 cited context를 assistant-assisted 1차로 다시
검토했다. 세제·제도 판단은 최종 발표 지표로 쓰기 전 팀원의 독립 2차 검토가 필요하다.

| Metric | Baseline | Conditional shadow |
|---|---:|---:|
| Semantic correctness | 23 / 31 | 22 / 28 |
| Full requirement coverage | 23 / 31 | 19 / 28 |
| Fully grounded | 26 / 31 | 24 / 28 |
| Strict useful accepted answers | 20 | 19 |
| **Strict E2E Useful Answer Rate** | **20 / 38 (52.6%)** | **19 / 38 (50.0%)** |

Strict은 `factual correctness=pass` + `requirement coverage=pass` +
`evidence grounding=pass`를 모두 만족한 수용 answer로 정의했다. 429·transport·schema·citation
거부는 semantic 분모에 넣지 않으며, strict E2E의 분모는 두 variant 모두 answerable 38개로
고정했다.

## Subset 비교

| Subset | Baseline strict | Shadow strict | 해석 |
|---|---:|---:|---|
| Simple route 성격 질문 | 18 / 23 accepted | 18 / 23 accepted | semantic aggregate regression 없음 |
| Compound 성격 질문 | 2 / 8 accepted | 1 / 5 accepted | requirement coverage·grounding 모두 하락 |
| 전체 answerable | 20 / 38 | 19 / 38 | primary metric 미개선 |

Simple aggregate가 유지된 것은 긍정적이지만 production Go 기준에는 충분하지 않다. Shadow가
가장 겨냥한 compound subset에서 수용 answer와 strict useful answer가 모두 감소했다.

## Route/Gate 안전성 재확인

P3의 frozen retrieval sufficiency는 새 answer의 semantic 라벨로 재사용하지 않고, gate 정책의
사후 안전성 reference로만 사용했다.

- **false rejection 4건**: R-002, R-005, R-006, R-027은 prior `full` 근거가 있었지만
  dynamic requirement plan 부재로 `compound_requirements_not_defined`에서 차단됐다.
- **known unsafe pass 2건**: R-019, R-028은 prior `partial` 근거 상태인데 Shadow가 HCX를
  호출했다. R-028은 실제 answer review에서도 semantic error였다.
- **추가 semantic unsafe pass**: R-024는 compound gate가 complete라고 판단했지만, 실제
  answer는 상품의 투자대상·위험등급을 답하지 못했다.
- **안전한 차단**: R-010(partial)과 R-037(none)은 HCX 호출 전 차단됐다.

따라서 P15의 independent mini-holdout에서 보인 false rejection 0 / unsafe pass 0 성질은
이 full-40 Shadow 실행에 일반화되지 않았다.

## Known-case delta

| ID | Baseline | Shadow | 판정 |
|---|---|---|---|
| R-002 | 잘못된 DC 산정식으로 semantic error | requirement plan 없음으로 차단 | 안전 차단처럼 보이나 full 근거가 있어 false rejection |
| R-010 | 세금 조건 일부 누락 | pre-generation rejection | partial 근거에 대한 적절한 Fail-Closed |
| R-011 | 압류 금지 답변으로 질문 무관 | 같은 simple 경로·같은 semantic error | orchestration 대상 감지 실패 |
| R-024 | baseline generation/citation 미수용 | gate complete 후 “정보 없음” 답변 | citation valid만으로 evidence relevance 보장 불가 |
| R-028 | 투자대상·전략 대신 가격변동 설명 | 목차 근거로 semantic error | candidate selection / slot 검증 실패 |
| R-037 | 압류보호 설명으로 semantic error | plan 없음으로 pre-generation rejection | retrieval none에 대한 안전 차단 |

Case delta 전체는 Git 제외 `data/diagnostics/p16_case_deltas.jsonl`에, answer-hash review는
`p16_*_reviewed.jsonl`에 보관했다.

## 결정

**No-Go — conditional-routing Shadow를 production에 통합하지 않는다.**

Go 기준 가운데 다음을 충족하지 못했다.

1. Strict E2E Useful Answer Rate가 baseline 52.6%보다 개선되지 않았다(50.0%).
2. compound semantic quality가 개선되지 않았다.
3. full-40에서 false rejection과 unsafe pass가 재발했다.
4. citation rejection 감소는 있었지만, R-024/R-028처럼 relevance·coverage 실패를 막지 못했다.

P16 결과를 보면서 Router, prompt, retrieval, validator를 수정하지 않았다. 다음 작업은 P16
결과를 기준으로 **requirement-plan coverage와 gate precision을 별도 진단**하는 것이며, 실제
HCX 재실행은 그 offline blocker가 해소된 뒤에만 검토한다.

## 재현

```bash
PYTHONPATH="$PWD/.venv/lib/python3.9/site-packages" \
  python3 scripts/evaluate_p16_shadow_hcx.py --execute --cooldown-seconds 10

PYTHONPATH="$PWD/.venv/lib/python3.9/site-packages" \
  python3 scripts/build_answer_quality_review_packet.py \
  --run data/diagnostics/p16_baseline_hcx.json \
  --output data/diagnostics/p16_baseline_review_packet.jsonl \
  --summary data/diagnostics/p16_baseline_review_summary.json
```

동일하게 shadow packet을 만들고 answer-hash를 확인한 review 뒤
`apply_p16_manual_review.py`, `summarize_p16_semantic_review.py`,
`build_p16_case_deltas.py` 순서로 집계한다.
