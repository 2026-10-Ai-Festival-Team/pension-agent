# P44 — Read-only Shadow Integration

## Boundary

P44 attaches an optional observer *after* the existing P27-D candidate has
created its response.  The observer receives the question only and records
the resolver-first scoped requirement preparation trace.  It cannot modify the
candidate's route, retrieval, evidence gate, generation call, citation
validation, policy, or API response schema.

For this integration check, the already frozen P42 selector outputs are
replayed.  The resolver, binder, resolved-scope retrieval query, direct-field
evidence binding, and candidate API paths run locally.  No HCX request is made
and the browser composition root does not enable the observer by default.

## Result

| Check | Result |
| --- | ---: |
| Candidate API responses unchanged | **18 / 18** |
| Shadow front-end contract errors | **0** |
| Shadow exceptions | **0** |
| Ambiguous scope retrieval | **0** |
| Shadow-worse divergence | **0** |
| Shadow-better divergence | 1 |
| Equivalent divergence | 17 |
| Added HCX answer calls | **0** |
| Candidate decision/browser response changes | **0 / 0** |
| Shadow latency (min / median / max) | 0.031 / 50.889 / 152.116 ms |

`shadow_better` denotes the one row where the legacy candidate evidence gate
was insufficient while the shadow prepared scoped evidence.  `equivalent`
does not require identical chunk IDs; P43-C already established direct-field
source relevance for the changed contexts.  There are no shadow-worse rows.

The measured latency is only the local observer/retrieval path under frozen
selector replay.  It intentionally excludes an HCX selector call and must not
be interpreted as live-HCX production latency.

## Decision

**P44: read-only integration Go.**  The observer is opt-in, failure-isolated,
and does not alter the existing candidate or browser path.  P42 remains a
development regression set.  The next evaluation is a newly frozen Closed
E2E holdout using the full new path, not another P42 optimization.

Result: `evaluation/p44_read_only_shadow_integration.json`.
