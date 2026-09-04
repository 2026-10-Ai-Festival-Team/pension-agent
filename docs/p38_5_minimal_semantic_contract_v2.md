# P38-5 — Minimal Semantic Contract v2

## Purpose and boundary

P38-5 redesigns only the isolated semantic-planning representation. It does not modify the candidate Agent, retrieval, matcher, gate, HCX prompt, citation contract, or answer-generation path.

P38-4 showed that 37 of 50 missing v1 action/modifier atoms duplicated meaning already carried by subjects or fields, while 11 missing atoms lost real factual scope. V2 therefore preserves only evidence-changing distinctions.

## Contract

```text
subject[]
field[]
essential qualifier[]
relation[]
```

`action` is not an LLM-required atom. The deterministic composer derives an operation only where a field makes it unambiguous, such as `withdrawal_reason -> withdrawal` or `tax_timing + tax_timing_on_transfer -> transfer tax timing`.

### Essential qualifiers

- `before_retirement`
- `combined_limit`
- `isa_maturity`
- `additional_credit`
- `in_kind`
- `tax_timing_on_transfer`
- `not_tax_exempt`
- `current`, `historical`, `change_possibility`

Nonessential v1 modifiers such as `comparison`, `account_specific`, `annual_rate`, and `holding_period` are not strict qualifier atoms. Their evidence semantics are already represented by a comparison relation, multiple explicit subjects, or a canonical field (`total_fee`, `cost_example`).

### Field granularity changes

V2 adds separate fields for partial withdrawal and account closure. These cannot safely be represented as one generic withdrawal field plus a fragile modifier:

- `partial_withdrawal_condition`
- `account_closure_condition`
- `partial_withdrawal_tax`
- `account_closure_tax`

### Relations

Relations retain only factual relationships that cannot be recovered from a single subject-field pair:

- `comparison`
- `transfer` with source and destination

## Validation

`src/experiments/semantic_contract_v2.py` is an isolated v2 ontology, strict validator, and deterministic composer. It accepts no unknown ontology values and has no production imports.

## Annotation protocol

P38-1/P38-2 v1 gold was manually reannotated into the frozen 48-row v2 manifest at `question_bank/development/semantic_contract_v2_manual_gold.jsonl`. The builder copies only original question text and checks coverage; it does not read or transform v1 atom labels. Every row records:

```json
{
  "annotation_status": "confirmed",
  "annotation_source": "manual",
  "legacy_v1_used_as_reference": true,
  "auto_converted": false,
  "ambiguity": null
}
```

The frozen manifest metadata is `question_bank/development/semantic_contract_v2_manual_gold_metadata.json` with SHA-256 `2249f41fcc4938935ebeba93051f39147ee9b96f7a698efcb8427cae816a2c2f`. Any future uncertain relation must be marked `needs_annotation` rather than inferred from v1.

P38-5 closes the representation and manual-gold gate, not parser performance or generalization.

## Next gate

Only after the manual v2 annotation manifest is frozen may P38-6 compare a v2 HCX Structured Output parser against a v2 deterministic baseline. Metrics are subject F1, field F1, essential-qualifier F1, relation accuracy, semantic requirement coverage, requirement exact, and unsupported extra atoms.
