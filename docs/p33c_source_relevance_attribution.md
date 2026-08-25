# P33-C: Source-Relevance Attribution

## Scope

- 대상: P33-B에서 manifest의 허용 청크가 selected context에 없던 7개 개발 회귀 사례
- HCX 호출 없음, prompt·정책·retriever·matcher·gate 변경 없음
- 판정 축: `subject + account/product/system scope + field/requirement + factual value/condition`

## Result

| 판정 | 건수 | 사례 |
|---|---:|---|
| exact gold chunk | 11 | 기존 P33-B 교집합 통과 사례 |
| equivalent evidence | 3 | P33-003, P33-011, P33-012 |
| partial evidence | 2 | P33-013, P33-023 |
| irrelevant or wrong scope | 2 | P33-024, P33-025 |

`exact + equivalent`는 14/18입니다. 하지만 partial 2건과 wrong-scope 2건이 남아 있으므로 P33-B는 source relevance 기준으로 **No-Go**입니다.

## Key findings

- P33-003은 동일 IRP 원본의 표가 단기·단시간 근로자의 IRP 가입대상을 직접 설명하므로 semantic equivalent입니다.
- P33-012는 다른 청크를 사용했지만 동일 상품의 5등급, 채권 운용전략, 실적배당·원금손실·예금자보호 비대상 근거가 모두 존재합니다.
- P33-013·023은 일부 사실은 맞지만, 투자전략 또는 6등급 의미라는 필수 축이 빠졌거나 선택된 청크가 해당 축을 지지하지 않습니다.
- P33-024는 목표전환 상품의 비보장 근거에 다른 상품의 원금손실 표를 사용했습니다.
- P33-025는 과거 성과의 장래 비보장 및 적합성 판단과 무관한 압류·ESG 전략 청크를 선택했습니다.

## Decision

P34 Fresh Holdout은 아직 만들거나 실행하지 않습니다. 다음 개선은 P33 개별 ID 패치가 아니라, 동일 subject의 필수 field를 묶어 선택하는 source-relevance matcher와 generic safety-premise retrieval을 일반화하는 작업이어야 합니다.
