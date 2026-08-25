# P49-R — Frozen Scoped Retrieval Runtime Integration

## Purpose

The browser/API runtime now uses the already evaluated P42--P48
single-subject Closed factual path.  It does not repair or extend P27.

```text
question
→ resolver
→ scoped direct requirement selector
→ deterministic binder
→ resolved-scope retrieval
→ direct-field evidence binding
→ answer generator
→ citation validation
```

The legacy P27 raw-BM25 path is not a fallback for this browser composition.
If HCX-007 structured selection is not configured, startup fails explicitly.

## Runtime contract

`create_browser_configured_app()` requires:

```text
GENERATOR_BACKEND=hcx
HCX_MODEL=HCX-007
```

The selector and answer generator share one global request limiter.  API
request field `top_k` remains accepted for schema compatibility but cannot
re-open an unscoped raw BM25 query; the scoped path retains its frozen context
budget.

The existing response schema is unchanged:

```text
question_id, question, retrieved_context, think_trace, answer
```

`retrieved_context` is the scoped evidence supplied to answer generation.  The
browser labels it **답변에 사용한 근거**, not a raw search-result list.

## Staging trace

For an `/answer` response, record:

```text
question
route / frontend_reason
active_subject
selected_requirements
retrieval_queries
requirement_candidate_ids
selected_evidence_chunk_ids
cited_chunk_ids
displayed_evidence_chunk_ids
```

For `DB는 내가 직접 굴리는 거지?`, a passing trace must contain
`active_subject=DB`, `selected_requirements=["DB.operation_party"]`, and a
direct DB-operation-party evidence chunk in selected, cited, and displayed
evidence.  An unrelated raw BM25 context must not appear in the final context.

## Boundary

This integration preserves the frozen single-active-subject capability boundary.
Genuine multi-subject comparisons remain unresolved/fail-closed; P49-R does
not add comparison orchestration or change fine-tuning behavior.
