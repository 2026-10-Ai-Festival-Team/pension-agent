# P49-2H-3B Pilot Candidate Generation

The pilot is an 84-record request queue, not an accepted dataset:

| Outcome | Requests |
| --- | ---: |
| `supported_answer` | 55 |
| `clarification_required` | 15 |
| `bounded_answer` | 14 |

The queue is derived only from the curated pool. Each request locks a pool row,
host-owned provenance, outcome, question-type lane, field constraints, and the
typed candidate contract before any model output exists.

Prepare the queue without external calls:

```bash
.venv/bin/python scripts/prepare_p49_2h_pilot_generation.py
```

This command creates no raw candidate, makes zero HCX calls, and cannot export
training data. A later live runner must require a separate explicit
authorization and write its raw output to a new file.

## Controlled live execution (not yet authorized)

Only run this after reviewing the frozen 84-request queue. The explicit
`--execute` flag is required because this makes paid external HCX-007 calls;
the runner never changes the browser/candidate runtime and cannot promote a
record to human-approved or accepted.

```bash
.venv/bin/python scripts/run_p49_2h_pilot_generation.py --execute
```

It writes raw, host-hydrated candidates to
`evaluation/fine_tuning/p49_2h_pilot_raw_v1.jsonl`. The host, not HCX, fixes
the requirement template, actual corpus chunk ID, source-seed lineage, and all
review/acceptance statuses. To resume an interrupted batch without overwriting
completed request IDs, use `--resume`. For a controlled first smoke batch,
provide `--max-requests N` (where `N` is 1 through 84) and a distinct output
path.

Validate raw candidates before writing a QA report:

```bash
.venv/bin/python scripts/validate_p49_2h_augmentation_candidates.py \
  --input evaluation/fine_tuning/p49_2h_pilot_raw_v1.jsonl \
  --output evaluation/fine_tuning/p49_2h_pilot_validated_v1.jsonl \
  --manifest evaluation/fine_tuning/p49_2h_pilot_validation_manifest_v1.json
```

After a raw pilot has passed the existing candidate validator, summarize it
without modifying statuses:

```bash
.venv/bin/python scripts/report_p49_2h_pilot_qa.py \
  --validated evaluation/fine_tuning/PILOT_VALIDATED.jsonl \
  --output evaluation/fine_tuning/PILOT_QA_REPORT.json
```

The report tracks validator failures, outcome-lane failures, potential
numeric/field/policy/duplicate families, and a deterministic human spot-review
list. It leaves `human_review_status` and `acceptance_status` untouched.
