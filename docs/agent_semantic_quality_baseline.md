# Agent 의미 품질 평가 기준선 (P2)

## 목적과 원칙

P2는 Agent를 개선하거나 HCX 프롬프트·검색·파서·정책을 튜닝하지 않고, 현재 Evidence-Validated RAG Agent의 품질을 다음 세 층으로 분리해 측정한다.

```text
검색 근거 도달 여부
→ 인용·정책 계약 통과 여부
→ 답변 의미 품질 (사람 검토)
```

따라서 HCX Accepted Answer Rate는 사실성, 근거 완전성, 답변 정확성과 동일한 지표가 아니다. HTTP 429·transport·JSON format 실패도 의미 품질의 분모에 넣지 않는다.

## 고정 구성과 실행

- Corpus: 23,421 chunks
- Retriever: Simple BM25 + `pension-v1`
- Generator: HCX-DASH-002, `maxTokens=800`
- Rate limit: 단일 프로세스 global minimum interval 2초
- 질문: 고정된 40문항 (answerable 38, unsupported 2)
- Run SHA-256: `0af114e2e07ae041f9749fc455c7a0d3396ed2ac859690542886997a56f5ec7f`

이 실행의 answer 원문과 retrieved context는 사측 문서 내용을 포함하므로 Git 제외 파일 `data/diagnostics/agent_hcx_quality_run.json`과 `data/diagnostics/answer_quality_review_packet.jsonl`에만 저장한다.

## 운영·계약 지표

| 항목 | 결과 | 의미 |
|---|---:|---|
| API success | 40/40 | 평가 API가 정상 응답 |
| HCX attempted | 38/40 | unsupported 2건은 정책에 따라 HCX 미호출 |
| Structured JSON parse | 32/38 | provider/format 안정성 지표 |
| Citation contract pass | 31/32 | parse 성공 응답 중 valid citation 통과 |
| HCX Accepted Answer Rate | 31/38 (81.6%) | semantic correctness가 아닌 구조·인용 계약 통과율 |
| HCX transport/format rejection | 6 | 429 5건, malformed JSON 1건 |
| Citation rejection | 1 | 빈 `cited_chunk_ids` |

이번 run의 2초 interval에서도 429가 5건 발생했다. 이는 P0의 2초 설정이 단일 실험에서 확인한 최소 안정점이지 provider quota의 영구 보장이 아니라는 기존 한계와 일치한다.

## Retrieval 및 evidence completeness

| 항목 | 결과 | 해석 |
|---|---:|---|
| Direct evidence hit@10 | 27/38 | gold direct chunk가 Top-10에 하나 이상 존재 |
| Generated answer 중 direct evidence hit@10 | 25/31 | 의미 검토에 우선 투입할 근거 도달 답변 |
| Generated answer 중 direct evidence miss | 6/31 | 검색 실패와 생성 품질을 혼동하지 않기 위해 별도 분류 |
| All evidence hit@10 | 0/3 | 복합 근거가 필요한 R-002, R-024, R-036 모두 미충족 |
| Unsupported policy handling | 2/2 | HCX를 호출하지 않고 안전 응답 |

`unlabeled_retrieved_chunk_count`는 gold relevant set 밖 Top-10 개수다. 평가 gold가 모든 비관련 청크를 라벨링한 것은 아니므로 이를 irrelevant-context 비율로 단정하지 않는다.

## 의미 품질 검토 packet

`scripts/build_answer_quality_review_packet.py`는 각 질문에 다음을 같은 행으로 고정한다.

- question 및 category
- gold direct/relevant chunk IDs와 required terms
- retrieved context 및 selected citation IDs
- 실제 answer와 `answer_sha256`
- retrieval·citation·policy 시스템 결과
- 수동 review fields

수동 검토 필드는 다음과 같다.

| 축 | 평가 내용 |
|---|---|
| factual correctness | 근거와 사실이 일치하는가 |
| numeric fidelity | 세율·금액·기간·연령 등 수치를 보존했는가 |
| requirement coverage | 질문의 조건·절차·설명 요구를 빠뜨리지 않았는가 |
| evidence grounding | citation ID가 유효한 것을 넘어 claim을 실제 지지하는가 |
| hallucination | 문서 밖 사실·수치·상품코드가 없는가 |
| premise correction | 잘못된 전제를 필요한 경우 교정했는가 |
| comparison coverage | 복합/비교 질문의 대상별 근거를 모두 다뤘는가 |
| information-limit handling | 한계 고지·역질문·정책 거절이 적절한가 |

현재 packet은 수동 라벨을 아직 채우지 않았으므로 **semantic accuracy 점수는 보고하지 않는다.** `not_reviewed`를 `pass`로 간주하거나 Accepted Answer Rate를 답변 정확도로 대체하지 않는다.

## 다음 판정 순서

1. 31개 generated answer를 우선 검토하되, gold direct hit 25개와 miss 6개를 분리한다.
2. R-002·R-024·R-036은 all-evidence miss로 표시해 비교·복합 요구 충족 여부를 엄격히 판정한다.
3. unsupported 2개와 evidence/generation rejection은 information-limit handling으로 별도 검토한다.
4. 완료된 review packet은 run SHA-256과 answer SHA-256을 검증한 뒤에만 집계한다.
5. 그 결과에서 가장 큰 실패 축 하나만 다음 개선 후보로 선택한다.

이 순서로 retrieval failure, provider failure, citation contract failure, semantic answer failure를 한 지표에 섞지 않는다.
