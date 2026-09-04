# P39-2 Execution Incident — Invalid Fresh Holdout

## What happened

The frozen P39-2 manifest was validated before execution. All 18 isolated
HCX-007 selector calls completed with the intended pacing, but the runner
failed before saving results because its evaluator expected `source_question_id`
while the fresh manifest correctly used its own `id` field.

No output hashes, selections, or final metrics were persisted. The run cannot
be reconstructed without re-calling HCX.

## Decision

P39-2 is **invalid for generalization evaluation**. Do not rerun the same
questions: they have already been sent to the selector. It is retained only as
an execution-incident record, not a scored holdout.

## Corrective action

- The evaluator now accepts either `source_question_id` or manifest `id`.
- The runner persists each completed response to a checkpoint before final
  scoring. A future scoring failure therefore preserves raw selections and
  hashes without requiring a second HCX call.
- A new, non-overlapping P39-3 fresh holdout is required for the next valid
  generalization test.
