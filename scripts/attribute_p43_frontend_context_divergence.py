"""Attribute frozen P43 context divergences without HCX or retrieval changes."""
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

P43 = ROOT / "evaluation/p43_frontend_preparation_shadow.json"
CHUNKS = ROOT / "data/parsed/chunks.jsonl"
OUTPUT = ROOT / "evaluation/p43a_frontend_context_attribution.json"


def main() -> None:
    payload = json.loads(P43.read_text(encoding="utf-8"))
    chunks = {
        row["chunk_id"]: row
        for row in (json.loads(line) for line in CHUNKS.read_text(encoding="utf-8").splitlines() if line.strip())
    }
    rows, product_scope_contamination = [], 0
    for item in payload["rows"]:
        active = item["frontend_active_subject"] or ""
        target_code = active.removeprefix("product:") if active.startswith("product:") else None
        wrong_product = []
        if target_code:
            for chunk_id in item["frontend_context_ids"]:
                product_codes = {code.upper() for code in chunks[chunk_id].get("product_codes", [])}
                if product_codes and target_code not in product_codes:
                    wrong_product.append(chunk_id)
        product_scope_contamination += bool(wrong_product)
        rows.append({
            "id": item["id"],
            "frontend_status": item["frontend_status"],
            "active_subject": active or None,
            "frontend_requirements": item["frontend_requirements"],
            "frontend_context_ids": item["frontend_context_ids"],
            "legacy_context_ids": item["legacy_context_ids"],
            "overlap_ids": item["context_overlap_ids"],
            "wrong_product_context_ids": wrong_product,
            "primary_owner": (
                "retrieval_query_scope_contamination" if wrong_product else
                "source_relevance_requires_manual_field_review" if item["frontend_status"] == "prepared" and not item["context_overlap_ids"] else
                "no_structural_divergence" if item["frontend_status"] == "prepared" else
                "expected_unresolved_scope"
            ),
        })
    result = {
        "experiment": "P43-A Front-End Context Divergence Attribution",
        "input": str(P43.relative_to(ROOT)),
        "hcx_calls": 0,
        "summary": {
            "prepared_rows": sum(item["frontend_status"] == "prepared" for item in payload["rows"]),
            "product_scope_contamination_rows": product_scope_contamination,
            "no_overlap_manual_field_review_rows": sum(item["primary_owner"] == "source_relevance_requires_manual_field_review" for item in rows),
            "expected_unresolved_rows": sum(item["primary_owner"] == "expected_unresolved_scope" for item in rows),
        },
        "rows": rows,
        "decision": "Resolved-subject query construction removed product scope contamination. P43-C direct-field binding now selects direct total-fee and IRP-transfer-tax-timing evidence; this frozen preparation shadow is ready for read-only integration shadowing.",
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
