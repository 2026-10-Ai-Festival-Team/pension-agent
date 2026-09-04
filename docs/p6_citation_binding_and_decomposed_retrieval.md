# P6: Citation Binding 및 Requirement별 Retrieval 실험

## 목적

P5에서 확인된 두 병목을 production 변경 없이 분리 검증했다.

```text
P6-A: 올바른 Context가 있어도 source_id 형태 인용으로 차단되는 문제
P6-B: Top-10에 필요한 근거 자체가 없는 retrieval missing 문제
```

Corpus, BM25 파라미터, tokenizer, 청킹, production retriever, citation validator는 변경하지 않았다. 자동 `source_id → chunk_id` 변환과 fuzzy citation 보정도 구현하지 않았다.

## HCX-007 요청 계약 정정

HCX-DASH-002에서 성공했던 `maxTokens`와 문자열 `messages[].content` 요청을 HCX-007에 그대로 보내면 HTTP 400이 발생했다. HCX-007은 추론 모델이라 v3 요청에 `maxCompletionTokens`와 typed text content 배열을 사용해야 한다. 따라서 generator는 모델이 `HCX-007`일 때만 다음 형식으로 payload를 만들도록 수정했다.

```json
{
  "messages": [{"role": "user", "content": [{"type": "text", "text": "..."}]}],
  "thinking": {"effort": "none"},
  "temperature": 0,
  "maxCompletionTokens": 800
}
```

이는 모델별 API 계약 호환 수정이며, citation validation 완화가 아니다. HCX-007 공식 v3 문서는 이 모델에 `maxCompletionTokens`와 typed text content를 사용하도록 명시한다. [CLOVA Studio HCX-007 문서](https://api.ncloud-docs.com/docs/en/clovastudio-chatcompletionsv3-thinking)

## P6-A: Citation Binding

### 방법

P5에서 selected evidence는 맞았지만 source ID를 반환했던 R-002·R-011만 실제 HCX-007로 재실행했다.

- Context 안에서는 `citation_id: <완전한 chunk_id>`만 citation 값으로 노출했다.
- `source_id` 값은 generation prompt에 넣지 않았다.
- 문서·위치·본문과 citation ID의 역할을 분리했다.
- `cited_chunk_ids`에는 `citation_id`를 byte-for-byte 복사하라고 명시했다.
- 기존 `chunk_id subset` Fail-Closed validator를 그대로 사용했다.

### 결과

| ID | 선택 Context | 반환 citation | Fail-Closed | 초기 수동 검토 |
|---|---|---|---|---|
| R-002 | DB 산정 문단 + DC 부담금·운용손익 표 | 두 complete `chunk_id` | 통과 | DB 평균임금×근속기간, DC 부담금 누계액±운용손익을 올바르게 비교 |
| R-011 | 세금 납부 시점·과세이연 표 | complete `chunk_id` | 통과 | 연금 수령 시 과세라는 질문 핵심에 답함 |

두 호출 모두 HTTP 200, 재시도 0회였다. generation latency는 R-002 2,079ms, R-011 1,391ms였다. 첫 P5의 source ID 문제는 이 두 사례에서 prompt representation만으로 재현되지 않았다.

### 결론

**Targeted pass, production 미통합.**

P6-A는 “citation validator를 완화하지 않고도 모델이 올바른 식별자를 출력할 수 있는가”라는 가설을 R-002·R-011에서 지지한다. 단 두 사례뿐이므로 전체 Agent prompt 교체의 근거는 아직 충분하지 않다. 다음 후보는 동일 binding 형식을 P5의 다른 compound dev 사례에 제한적으로 재현해 citation·semantic quality·latency를 함께 비교하는 것이다.

## P6-B: Requirement별 Decomposed Retrieval

### 방법

R-024·R-028·R-037만 대상으로 HCX 호출 없이 다음을 비교했다.

```text
A: 원 질문 1회 → BM25 Top-10
B: requirement별 query 2회 → 각 Top-10 → chunk_id 중복 제거 → merge
```

각 query는 고정된 P6 계획 파일에 기록했고, BM25 index와 production retriever는 바꾸지 않았다. B의 candidate rank는 서로 다른 query의 BM25 점수를 비교하는 순위가 아니라 merge 순서다.

### 결과

| ID | A candidate | B candidate | A slot coverage | B slot coverage | Exact gold | Semantic evidence 판정 |
|---|---:|---:|---|---|---|---|
| R-024 | 10 | 14 | 없음 | 없음 | 없음 | 개선 없음 |
| R-028 | 10 | 18 | 없음 | 전체 | 없음 | `table-fdab...`에 국내 주식·장기성장주·운용전략이 있어 동등 근거 회수 |
| R-037 | 10 | 13 | 없음 | 전체 | B에서 hit | DB/DC 적립금 운용 주체 표 회수 |

R-024는 query를 분해해도 목차·변경 위험등급 등 주변 chunk만 늘어났고, 질문이 요구한 투자대상·위험등급을 만족하는 evidence는 나오지 않았다. 반대로 R-037은 `DB 적립금 운용 주체`와 `DC 적립금 운용 주체` query가 기존 direct gold 표를 모두 회수했다. R-028은 exact gold ID는 아니지만 같은 상품 설명의 동등한 투자전략 표를 찾았다.

### 결론

**Targeted retrieval gain, production 미통합.**

Requirement별 retrieval은 3건 중 R-037의 direct evidence와 R-028의 semantic equivalent evidence를 회수했다. 하지만 R-024에는 효과가 없고 candidate 수는 3~8개 증가했다. 따라서 모든 질의에 적용하지 않는다. 다음 HCX 파일럿은 R-037과 R-028에만 제한해, merged Context가 실제 answer correctness와 requirement coverage를 높이는지 확인해야 한다.

## 재현

```bash
# HCX-007, R-002·R-011만 실제 호출
python3 scripts/run_p6_citation_binding.py

# HCX를 호출하지 않는 retrieval-only 비교
python3 scripts/run_p6_decomposed_retrieval.py --per-query-top-k 10
```

원문 answer와 provider diagnostic이 포함된 결과는 각각 `data/diagnostics/p6_citation_binding_run.json`, `data/diagnostics/p6_decomposed_retrieval_run.json`에 저장하며 Git에서 제외한다.
