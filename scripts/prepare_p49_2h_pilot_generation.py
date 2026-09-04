"""Prepare, but never execute, the P49-2H-3B 84-record pilot.

The output is a generation-request queue.  It includes only curated original
evidence and a typed output contract; no HCX request, candidate JSONL, or
training record is created by this script.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POOL = ROOT / "evaluation/fine_tuning/p49_2h_curated_evidence_pool_v1.jsonl"
CONTRACT = ROOT / "evaluation/fine_tuning/p49_2h_candidate_generation_contract_v1.json"

PILOT_TARGETS = {"supported_answer": 55, "clarification_required": 15, "bounded_answer": 14}
SUPPORTED_DOMAINS = (
    "D01 D02 D03 D04 D07 D08 D09 D11 D12 D13 D14 D15 D17 D18 D19 D20 D21 D22 D24 D25 D26 D27 D28 "
    "D09 D09 D14 D14 D14 D14 D15 D15 D17 D17 D18 D19 D20 D20 D20 D21 D21 D21 D22 D22 D22 D28 D28 D28 "
    "D11 D11 D12 D12 D01 D03 D04 D07"
).split()
CLARIFICATION_DOMAINS = ("D09 D14 D20 D21 D24 " * 3).split()
BOUNDED_DOMAINS = ("D30 " * 14).split()

QUESTION_TYPE_CYCLES = {
    "supported_answer": ("Q01", "Q02", "Q03", "Q04", "Q05", "Q06", "Q07", "Q08", "Q11", "Q12", "Q13", "Q14", "Q15", "Q19", "Q20"),
    "clarification_required": ("Q09", "Q10", "Q13", "Q20"),
    "bounded_answer": ("Q17", "Q18", "Q12", "Q13"),
}

# The source seed is only provenance for augmentation lineage.  Exact evidence
# comes from the selected pool row, not from the seed's answer text.
SEED_BY_DOMAIN = defaultdict(lambda: "ROB_012", {
    "D01": "ROB_006", "D02": "ROB_006", "D03": "ROB_006", "D04": "ROB_003",
    "D07": "ROB_012", "D08": "ROB_012", "D09": "ROB_032", "D11": "ROB_012",
    "D12": "ROB_012", "D13": "ROB_012", "D14": "ROB_016", "D15": "ROB_016",
    "D17": "ROB_027", "D18": "ROB_027", "D19": "ROB_027", "D20": "ROB_035",
    "D21": "ROB_035", "D22": "ROB_027", "D24": "ROB_023", "D25": "ROB_016",
    "D26": "ROB_032", "D27": "ROB_015", "D28": "ROB_027", "D30": "ROB_030",
})


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def make_request(index: int, outcome: str, domain: str, pool_row: dict, type_index: int) -> dict:
    question_type = QUESTION_TYPE_CYCLES[outcome][type_index % len(QUESTION_TYPE_CYCLES[outcome])]
    supported = pool_row["evidence_role"] == "direct_requirement_evidence"
    requirement = {
        "canonical_requirement": pool_row["canonical_requirement"],
        "requirement_kind": "factual",
        "coverage_required": supported and outcome == "supported_answer",
        "support_status": "supported" if supported else "unsupported",
        "evidence_chunk_ids": [pool_row["chunk_id"]] if supported and outcome == "supported_answer" else [],
    }
    return {
        "pilot_request_id": f"P49-2H-PILOT-{index:03d}",
        "source_seed_id": SEED_BY_DOMAIN[domain],
        "question_type": question_type,
        "factual_domain": domain,
        "target_outcome": outcome,
        "pool_id": pool_row["pool_id"],
        "generation_status": "not_started",
        "host_provenance_locked": True,
        "requirement_template": [requirement],
        "direct_evidence": [{
            "chunk_id": pool_row["chunk_id"], "source_id": pool_row["source_id"],
            "evidence_type": pool_row["evidence_type"], "text": pool_row["evidence_text"],
        }],
        "generation_instructions": {
            "task": "Generate one natural Korean user question, independent gold facts, and a draft completion from this exact evidence only.",
            "output_must_not": ["invent evidence", "change host provenance", "promote human review", "promote acceptance", "use future facts outside evidence"],
            "field_constraints": pool_row["exclusion_constraints"],
            "table_fields": pool_row["table_fields"],
            "numeric_anchors": pool_row["numeric_anchors"],
            "optional_calculation_contract": pool_row["optional_calculation_contract"],
            "bounded_rule": "For bounded_answer, keep future/unsupported requirement unbound and use evidence only as optional current context.",
            "clarification_rule": "For clarification_required, ask only for missing conditions; do not resolve the condition from corpus context.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", type=Path, default=POOL)
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/fine_tuning/p49_2h_pilot_generation_requests_v1.jsonl")
    parser.add_argument("--manifest", type=Path, default=ROOT / "evaluation/fine_tuning/p49_2h_pilot_batch_manifest_v1.json")
    args = parser.parse_args()
    if len(SUPPORTED_DOMAINS) != PILOT_TARGETS["supported_answer"] or len(CLARIFICATION_DOMAINS) != PILOT_TARGETS["clarification_required"] or len(BOUNDED_DOMAINS) != PILOT_TARGETS["bounded_answer"]:
        raise RuntimeError("Pilot lane plan does not match its frozen quota.")
    pool = read_jsonl(args.pool)
    by_domain: dict[str, list[dict]] = defaultdict(list)
    for row in pool:
        by_domain[row["domain"]].append(row)
    requests, next_index = [], 1
    for outcome, domains in (("supported_answer", SUPPORTED_DOMAINS), ("clarification_required", CLARIFICATION_DOMAINS), ("bounded_answer", BOUNDED_DOMAINS)):
        for local_index, domain in enumerate(domains):
            compatible = [row for row in by_domain[domain] if outcome in row["allowed_outcomes"]]
            if not compatible:
                raise RuntimeError(f"No pool row permits {outcome} for {domain}")
            requests.append(make_request(next_index, outcome, domain, compatible[local_index % len(compatible)], local_index))
            next_index += 1
    counts = Counter(item["target_outcome"] for item in requests)
    manifest = {
        "stage": "P49-2H-3B Pilot Candidate Generation", "status": "prepared_not_executed",
        "pilot_target": 84, "lane_targets": PILOT_TARGETS, "lane_actual": dict(counts),
        "active_domain_coverage": sorted({item["factual_domain"] for item in requests}),
        "pool_input_sha256": hashlib.sha256(args.pool.read_bytes()).hexdigest(),
        "request_count": len(requests), "request_queue_sha256": None,
        "hcx_calls": 0, "raw_candidate_records": 0, "accepted_records": 0,
        "training_export_allowed": False, "tuning_allowed": False,
        "next_required_action": "Review prepared requests, then explicitly authorize a controlled HCX-007 pilot execution.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in requests), encoding="utf-8")
    manifest["request_queue_sha256"] = hashlib.sha256(args.output.read_bytes()).hexdigest()
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
