# P27-D: HCX-007 Native Structured Outputs A/B

P27-C에서 JSON 앞 설명문·Markdown fence 때문에 strict parser가 차단한 여섯 문항과 semantic control 네 문항을 같은 P26 candidate preparation 경로에서 2회씩 비교했다. parser와 Fail-Closed citation validator는 완화하지 않았다.

## 고정 조건

- 모델: `HCX-007`
- pacing: 6초 hard global interval
- A: 기존 JSON prompt + `thinking.effort=none`
- B: `responseFormat.type=json` + JSON Schema, `thinking.effort=none` (실제 추론 비활성)
- 대상: P27-C 형식 실패 6건 + semantic control 4건, 각 2회

## 요약

| Variant | JSON/schema | Citation validator | Prefix prose | Markdown fence | Empty answer | Empty citation |
|---|---:|---:|---:|---:|---:|---:|
| A: current prompt | 11/20 | 11/20 | 9 | 6 | 0 | 0 |
| B: native Structured Outputs | 20/20 | 20/20 | 0 | 0 | 0 | 0 |

## B variant 문항별 결과

| Question | JSON/schema | Prefix prose | Fence | Citation |
|---|---:|---:|---:|---:|
| R-001 | 2/2 | 0 | 0 | 2/2 |
| R-002 | 2/2 | 0 | 0 | 2/2 |
| R-004 | 2/2 | 0 | 0 | 2/2 |
| R-007 | 2/2 | 0 | 0 | 2/2 |
| R-011 | 2/2 | 0 | 0 | 2/2 |
| R-019 | 2/2 | 0 | 0 | 2/2 |
| R-022 | 2/2 | 0 | 0 | 2/2 |
| R-024 | 2/2 | 0 | 0 | 2/2 |
| R-025 | 2/2 | 0 | 0 | 2/2 |
| R-037 | 2/2 | 0 | 0 | 2/2 |

semantic correctness와 requirement coverage는 생성 답변 hash를 기준으로 별도 수동 검토한다. API schema는 형식을 보장할 뿐, citation ID의 허용 목록 적합성이나 금융 사실의 정확성을 보장하지 않으므로 기존 validator를 계속 적용했다.

## Semantic control 수동 검토

R-002, R-019, R-024, R-037은 두 variant 모두 citation 검증을 통과했다. R-002·R-024·R-037은 `correct/full/fully_supported`, R-019는 두 variant 모두 법정사유라는 핵심을 답했지만 구체 사유를 열거하지 않아 `correct/partial/fully_supported`로 판정했다. 따라서 이번 표본에서 B의 semantic regression은 없었다. 세부 라벨은 `evaluation/p27d_semantic_control_labels.json`에 기록했다.

P27-C 형식 실패 대상 중 R-004처럼 형식이 정상화되어도 의미 품질을 별도 검토해야 하는 문항은 이 실험의 semantic 성공으로 계산하지 않았다.

## 결론

**Native Structured Outputs: Go (형식 안정성 한정).**

- P27-C 형식 실패 여섯 문항을 포함한 B 20/20에서 JSON/schema와 citation validator가 모두 통과했다.
- B에서 설명문 prefix·Markdown fence·빈 answer·빈 citation array·HTTP 429는 모두 0건이었다.
- strict parser와 Fail-Closed validator를 완화하거나 ID를 자동 보정하지 않았다.
- HCX-007 endpoint는 `responseFormat`과 함께 `thinking: {"effort":"none"}`을 요구했다. 이는 실제 추론을 켜는 것이 아니라 공식 Structured Outputs 예시와 같은 비활성 설정이다.

다음 단계는 이 native Structured Outputs 요청 계약을 고정한 P27-E Full-40 재인증이다. P27-D는 format contract 실험이므로, R-004 등 semantic generation backlog는 별도 P28 대상으로 유지한다.
