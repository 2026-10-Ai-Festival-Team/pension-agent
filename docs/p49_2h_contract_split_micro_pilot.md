# P49-2H-3C Contract-Split Micro-Pilot

P49-2H-3B의 84건 universal contract는 3/84 PASS로 No-Go였다. 특히 literal
anchor, clarification의 무응답 계약, bounded의 미래 target 제한이 한 schema에
섞여 실패했다. 3C는 기존 raw/validated/report 파일을 변경하지 않는 별도 35건
micro-pilot이다. 3C-A에서는 최종 completion도 host가 책임진다: clarification은
모델의 `clarification_questions`로 host가 재질문 completion을 조립하고,
bounded는 host가 `unsupported_target` 한계 고지를 고정 삽입한다. supported의
`completion_required_terms`는 모델이 만들지 않으며 검증 기준이 아니다.

| Lane | Count | Host-owned input | Model task |
| --- | ---: | --- | --- |
| `supported_answer` | 15 | requirement, direct evidence, literal quotes | 자연스러운 질문·근거 충실 답변 |
| `clarification_required` | 10 | user scenario, missing conditions | 사실 답변 없이 최소 재질문 |
| `bounded_answer` | 10 | supported/unsupported requirements, optional context | 지원 부분 답변·미지원 미래값 한계 고지 |

Prepare only — it makes zero external calls:

```bash
.venv/bin/python scripts/prepare_p49_2h_contract_split_micro_pilot.py
```

The resulting manifest must say `prepared_not_executed`, 35 records, and
15/10/10 lane counts. Actual HCX-007 execution is separately gated. The v2
runner writes a new raw file and preserves the failed v1 raw file:

```bash
.venv/bin/python scripts/run_p49_2h_contract_split_micro_pilot.py --execute
```

Validate only after that explicit run:

```bash
.venv/bin/python scripts/validate_p49_2h_contract_split_micro_pilot.py \
  --input evaluation/fine_tuning/p49_2h_contract_split_micro_raw_v4.jsonl \
  --output evaluation/fine_tuning/p49_2h_contract_split_micro_validated_v4.jsonl \
  --manifest evaluation/fine_tuning/p49_2h_contract_split_micro_validation_manifest_v4.json
```

No command here can approve a record, export training data, or start tuning.
The micro-pilot must pass its lane-specific automatic checks and evidence-first
human review before a second 84-record pilot can be authorized.

For a deliberately balanced partial run, pass exact IDs with `--request-ids`;
the runner rejects unknown/completed IDs rather than silently substituting a
different lane. This matters because the prepared queue is grouped by outcome.
