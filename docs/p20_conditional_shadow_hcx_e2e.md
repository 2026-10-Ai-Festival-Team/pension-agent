# P20: Conditional Shadow HCX E2E

## 목적

P19에서 안정화한 shared Shadow preparation이 실제 HCX-DASH-002 호출까지
동일하게 유지되는지, 그리고 conditional path가 P16 baseline의 Strict
End-to-End Useful Answer Rate를 개선하는지를 확인했다. 이 작업은
evaluation-only이며 production `PensionAgent`는 변경하지 않았다.

## 고정 조건

- 같은 40개 질문과 38개 answerable denominator
- 같은 Corpus(23,421 chunks), Simple BM25, `pension-v1`
- HCX-DASH-002, 같은 generation parameter와 `maxTokens`
- global minimum interval 2초, 동일 retry/parser/citation validator/Fail-Closed
- P19 shared preparation과 실제 P20 preparation의 중간 상태를 항목별 비교

P20 실행 중 router, requirement, matcher, retrieval, prompt, validator 규칙은
수정하지 않았다.

## Preparation parity와 gate 안전성

P19 offline artifact와 P20 HCX 직전 상태의 다음 필드는 **40/40 일치**했다.

```text
route, extracted entities, requirement plan, base/candidate retrieval IDs,
evidence sufficiency, gate decision, selected/merged evidence IDs,
HCX invocation decision
```

따라서 P16에서 발견된 offline/e2e composition mismatch는 P20에서 재발하지
않았다. P16의 known false rejection이었던 R-002, R-005, R-006, R-027은 모두
HCX 호출 대상이 되었고, known unsafe pass였던 R-019와 R-028은 실제로
pre-generation reject됐다. R-010, R-024, R-037도 incomplete evidence로
안전하게 차단됐다.

| Gate metric | P16 shadow | P20 conditional shadow |
|---|---:|---:|
| Preparation parity with P19 | 해당 없음 | **40 / 40** |
| Known false rejection | 4 | **0** |
| Known unsafe pass | 2 | **0** |
| Answerable pre-generation rejection | 6 | 5 |
| Unsupported safe handling | 2 / 2 | 2 / 2 |

여기서 pre-generation rejection 5건은 모두 incomplete evidence를 확인한
정책 차단이며, transport 또는 HCX semantic failure와 구분한다.

## 시스템 결과

| Metric | P16 baseline reference | P20 conditional shadow |
|---|---:|---:|
| HCX attempted | 38 | 33 |
| HTTP 429 (attempt history) | 18 | 42 |
| Retry count / GenerationError exhaustion | 13 / 6 | 29 / 14 |
| JSON/schema failure | 1 | 1 |
| Citation rejection | 1 | 1 |
| Accepted answers | 31 | 18 |
| HCX Accepted Answer Rate | 81.6% | 54.5% |
| Mean / p50 / p95 total latency | 3248 / 2382 / 7144 ms | 3549 / 3176 / 6210 ms |
| Input / output tokens | 138,354 / 3,926 | 68,980 / 2,172 |

P21 재분류 결과 P20의 `GenerationError exhaustion` 14건은 provider 429
retry exhaustion 13건과 HTTP 200 뒤 JSON/schema 실패 1건으로 구성된다. 높은 429와
provider retry exhaustion은 route quality가 아니라 provider 운영
상태의 실패다. 이들은 accepted-answer semantic denominator에서는 제외했지만,
answerable 38개로 고정한 Strict E2E 지표에는 그대로 반영했다. 그러므로 이번
run은 conditional routing의 semantic 개선을 인과적으로 증명하지 못하며,
운영 안정성도 Go 기준을 충족하지 못한다.

## Answer-hash 기반 semantic review

P20에서 실제로 수용된 18개 answer만 새 `answer_sha256` 기준으로 다시
assistant-assisted 1차 검토했다. P16 label을 재사용하지 않았으며 raw answer와
context는 Git 제외 `data/diagnostics/`에만 보관한다. 세제·제도 답변을 발표용
최종 성능으로 사용하기 전에는 팀원의 독립 2차 검토가 필요하다.

| Metric | P16 baseline | P20 conditional shadow |
|---|---:|---:|
| Semantic correctness | 23 / 31 | 16 / 18 |
| Full requirement coverage | 23 / 31 | 15 / 18 |
| Fully grounded | 26 / 31 | 16 / 18 |
| Strict useful accepted answers | 20 | 15 |
| **Strict E2E Useful Answer Rate** | **20 / 38 (52.6%)** | **15 / 38 (39.5%)** |

Strict useful는 `factual_correctness=pass`, `requirement_coverage=pass`,
`evidence_grounding=pass`를 동시에 만족한 수용 answer다. HCX Accepted
Answer Rate와 semantic correctness를 같은 지표로 해석하지 않는다.

P20 수용 answer의 semantic error는 세 건이다.

- R-011: 압류보호 근거를 인용했지만, 질문의 과세 시점에 답하지 않았다.
- R-033: 상품명은 맞지만 요청한 위험등급을 빠뜨렸다.
- R-034: 시간별 비용 예시를 요청한 총보수 값으로 해석했다.

## Compound subset

P16 이전부터 등록한 11개 compound reference cohort로 비교했다. P20은 그 중
4개를 수용했고 R-027, R-036 두 개만 strict useful였다.

| Metric | P16 baseline | P20 conditional shadow |
|---|---:|---:|
| Accepted | 8 | 4 |
| Semantic correct | 2 | 3 |
| Full coverage | 5 | 2 |
| Fully grounded | 4 | 3 |
| Strict useful | 2 | 2 |

R-027이 P16 false rejection에서 strict useful로 회복된 것은 positive case다.
하지만 R-033/R-034의 product-field coverage 오류와 provider 실패 때문에
compound strict useful 총수는 baseline보다 늘지 않았다.

## Known-case delta

| ID | P16 | P20 preparation / HCX outcome | 판정 |
|---|---|---|---|
| R-002 | false rejection | gate pass, HCX transport failure | gate 회복; 생성 품질 미평가 |
| R-005 | false rejection | gate pass, accepted strict useful | 개선 |
| R-006 | false rejection | gate pass, HCX transport failure | gate 회복; 생성 품질 미평가 |
| R-019 | unsafe pass | pre-generation reject | 안전성 개선 |
| R-027 | false rejection | accepted strict useful | 개선 |
| R-028 | unsafe pass | pre-generation reject | 안전성 개선 |

## 결정

**No-Go — production conditional-routing 통합을 보류한다.**

P20은 preparation parity와 known gate safety를 실제 실행에서 재현했다는 점에서
성공이다. 다만 primary metric은 baseline 52.6%보다 낮은 39.5%였고, compound
strict useful도 증가하지 않았으며, 429/retry exhaustion이 커 실제 E2E 품질
개선을 신뢰성 있게 입증할 수 없었다.

다음 단계는 rule/prompt tuning이 아니라, provider가 안정된 시간대에 동일한 P20
fixed artifact로 **단일 재실행**할 수 있는 운영 프로토콜을 정하는 것이다. 그 run에서도
preparation parity 40/40, false rejection 0, unsafe pass 0을 재확인한 뒤에만
Strict E2E 개선 여부를 다시 판단한다.

## 산출물과 재현

- Git 포함(원문 미포함):
  - `evaluation/p20_shadow_results.jsonl`
  - `evaluation/p20_semantic_labels.json`
  - `evaluation/p20_case_deltas.json`
- Git 제외: raw HCX response, answer/context review packet,
  `data/diagnostics/p20_*`

실제 비용이 발생하는 재실행은 명시적 실행 옵션이 있어야 한다.

```bash
PYTHONPATH="$PWD/.venv/lib/python3.9/site-packages" \
  python3 scripts/evaluate_p20_shadow_hcx.py --execute
```

그 뒤 raw diagnostics에서 review packet을 만들고
`apply_p20_manual_review.py`, `build_p20_e2e_artifacts.py` 순서로
answer-hash-bound semantic label과 Git-safe summary를 생성한다.
