# P27-E: Full-40 Native Structured Outputs 재인증

P27-D에서 검증한 HCX-007 native Structured Outputs를 P24-B candidate retrieval/matcher, R-019 정책 수정, provenance/Financial Answer Policy, strict parser·citation validator, 6초 hard pacing과 함께 Full-40에 적용했다. 이 보고서는 semantic labeling 전 운영·출력 계약만 판정한다.

## 결과

| 항목 | 결과 |
|---|---:|
| API 200 | 40/40 |
| HCX attempt | 38 |
| HTTP 429 | 0 |
| HTTP 5xx | 0 |
| Retry exhaustion | 0 |
| JSON/schema failure | 0 |
| Empty answer | 0 |
| Empty citation | 0 |
| Citation validator failure | 0 |
| R-019 generator called | True |
| R-039 safe block | True |
| R-040 safe block | True |

새 answer hash 기반 semantic labeling은 별도 단계에서 수행한다. strict parser와 Fail-Closed validator는 재인증 중에도 완화하지 않았다.
