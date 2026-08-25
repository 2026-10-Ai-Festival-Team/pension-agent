# P38-0A — Teammate Branch Asset Review

## Scope and snapshot

- Reviewed branch: `origin/feature/yw-pension-agent`
- Reviewed commit: `ee2e42cc8ca5895190f6a064630df9d671af3289`
- HCX calls: **0**
- Production merge: **none**
- Candidate-Agent, P38 parser, retrieval, matcher, policy, prompt, and API
  behaviour: **unchanged**

The local `evaluation/retrieval_questions.jsonl` exactly matches the reviewed
branch snapshot (`40` questions, SHA-256
`8f9cea03985a12d3511f60b3596d431494158cc7d32d35a18b008d3c8406d8a6`).  It is
registered as a development/reference fixture, never as a fresh holdout.

## Reviewed files and disposition

| Teammate file | Role | Action |
| --- | --- | --- |
| `evaluation/retrieval_questions.jsonl` | evidence-aware dev fixture | integrate as reference |
| `docs/retrieval_failure_analysis_normalized.md` | retrieval failure taxonomy | crosswalk only |
| `docs/retrieval_final_evaluation.md` | baseline/generalization evidence | reference only |
| `src/retrieval/query_normalizer.py` | phrase-expansion baseline | copy rules as data only |
| `src/orchestration/query_analyzer.py` | coarse keyword baseline | do not merge |
| `src/retrieval/fielded_bm25_retriever.py` | future retrieval A/B candidate | defer |
| `src/orchestration/evidence_assessor.py` | weak context sufficiency reference | do not merge |
| `src/orchestration/context_builder.py` | top-k context reference | do not merge |

`EvidenceAssessor` and `ContextBuilder` were not adopted because their checks
do not preserve the current `subject + field + value/condition + scope`
evidence contract.

## Crosswalk results

The generated retrieval crosswalk contains all 40 source IDs, each unique and
marked `dev_reference`; normalized exact overlap with the designated current
question-bank/P32--P37 sources is `0`.  Lack of exact wording overlap does not
make the fixture fresh: it was inspected and comes from a reviewed branch.

`required_terms` are not semantic gold.  They are marked compatible, partially
compatible, needs-human-annotation, or not-applicable without extending
`semantic_atoms_v1` or feeding an automatic parser label.

## Taxonomy crosswalk

- `query_document_vocabulary_gap` -> semantic normalization or retrieval query formulation
- `chunk_too_broad` -> chunking granularity or evidence selection
- `evidence_spans_multiple_chunks` -> requirement/multi-evidence composition
- `repetitive_document_noise` -> retrieval ranking or evidence selection
- `table_rendering` -> table parsing or table-field retrieval

These are related-owner hypotheses, not automatic equivalences with current
failure labels.

## Deferred comparison work

The teammate normalizer is explicitly a phrase expansion table tied to observed
development failures.  Its rules are retained only in
`evaluation/baselines/yw_phrase_normalizer_reference.json` for a future
phrase-baseline versus compositional-parser A/B.  Fielded BM25 remains a future
retrieval experiment after P38 parsing evaluation, not part of P38.

## Conclusion

P38-1/P38-2 have a clean reference fixture and failure taxonomy without a
production merge.  Compositional parser readiness is **Ready for isolated
evaluation only**; this review does not authorise candidate integration.
