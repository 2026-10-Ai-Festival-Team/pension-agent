# P40 — Fresh Scope / Reference Holdout

## Scope and freeze

P40 is an 18-question fresh Closed factual holdout for the isolated
`resolver -> frozen P39 selector -> binder` path.  It was created and manually
annotated before execution.  The P39 selector enum, prompt, candidate Agent,
browser, retrieval, matcher, citation validator, and financial policy were not
changed or connected for this run.

The live selector results were checkpointed per request.  HCX-007 was called
18 times with the existing structured-output configuration.

## Runtime contract

| Check | Result |
| --- | --- |
| Schema valid | 18 / 18 |
| Ontology valid | 18 / 18 |
| Unknown enum output | 0 |
| Provider errors | 0 |
| Candidate/browser integration | none |

## Requirement selection

| Metric | Result |
| --- | ---: |
| Precision | 81.48% |
| Recall | 100.00% |
| Exact requirement set | 15 / 18 (83.33%) |
| Multi-requirement recall | 14 / 14 (100.00%) |
| False missing requirement | 0 |
| Unsupported extra requirement | 5 |

The selector fully covered every requested multi-requirement set.  The three
non-exact cases are intentionally ambiguous-reference cases with no factual
requirement gold; the model nevertheless selected a related requirement.

## Scope / reference findings

| Metric | Result |
| --- | ---: |
| Resolved-reference accuracy | 14 / 15 (93.33%) |
| Ambiguous-reference safe unresolved | 2 / 3 (66.67%) |
| Subject-requirement binding errors | 0 |
| Ambiguous unsafe resolution | 1 |

### Unsafe case: P40-005

`KR5114420022` and `KR5114450222` are both introduced, then the question asks
for `그 상품` without an ordinal or other narrowing expression.  This reference
is ambiguous and should remain unresolved.  The current resolver does not
register this occurrence as an unresolved anaphora and the binder emits a
`bound_comparison` result covering both products.  That is an unsafe scope
expansion, even though the selected factual field (`product.risk_grade.current`)
is otherwise relevant.

### Resolver-only mismatch: P40-009

The raw resolver leaves `그 계좌` unresolved because no explicit account is
named.  The binder safely anchors it to `DC` only because the already selected
requirements are both DC-scoped; the final bindings are correct.  This is not a
binding error, but it shows that the resolver itself did not establish the
subject independently.

### Correct safe failures

P40-006 (`DB` and `DC` followed by `그 제도`) and P40-018 (`연금저축` and
`IRP` followed by `그 계좌`) stayed unresolved.  No answer scope was guessed
for either case.

## Decision

**P40: No-Go for shadow integration.**  Runtime and schema safety passed, and
the direct selector preserved all required requirements.  However, the strict
scope/reference gate requires zero ambiguous unsafe resolution and zero
binding-driven scope widening.  P40-005 violates that contract.

P40 is now a development/regression set.  Do not rerun it as a fresh
generalization claim.  The next work is failure attribution for the resolver's
anaphora detection and for the resolver/binder boundary; candidate integration
remains prohibited until a new fresh scope/reference holdout passes.

Raw result: `evaluation/p40_scope_reference_holdout.json`.
