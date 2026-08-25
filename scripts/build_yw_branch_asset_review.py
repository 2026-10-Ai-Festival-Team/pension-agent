"""Materialize P38-0A reference artifacts from a reviewed teammate snapshot.

The script creates evaluation metadata only.  It never imports teammate code,
never calls HCX, and never changes a candidate-Agent module.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import unicodedata


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "evaluation/retrieval_questions.jsonl"
INTEGRATIONS = ROOT / "evaluation/integrations"
BASELINES = ROOT / "evaluation/baselines"
REMOTE_BRANCH = "origin/feature/yw-pension-agent"
REMOTE_COMMIT = "ee2e42cc8ca5895190f6a064630df9d671af3289"


# This is review metadata, not a parser rule table.  The IDs classify whether
# a teammate retrieval term can be *discussed* with the existing P38 ontology.
# It must never be read by P38 parser or candidate-Agent code.
ALIGNMENTS = {
    "R-001": ("compatible", ["account:DB", "account:DC"], ["manage", "compare"], ["operation_party"], ["comparison"]),
    "R-002": ("compatible", ["account:DB", "account:DC"], ["compare"], ["benefit_determination"], ["comparison"]),
    "R-004": ("compatible", ["account:DC"], ["contribute"], ["contribution_structure"], []),
    "R-008": ("compatible", ["account:IRP"], ["contribute"], ["tax_credit_limit"], ["account_specific"]),
    "R-011": ("compatible", ["account:IRP"], ["transfer"], ["tax_timing"], []),
    "R-018": ("compatible", ["account:IRP"], ["withdraw"], ["withdrawal_reason"], []),
    "R-019": ("compatible", ["account:DC"], ["withdraw"], ["withdrawal_reason"], []),
    "R-029": ("partially_compatible", [], ["invest"], ["risk_grade", "risk_grade_changeability"], ["change_possibility"]),
    "R-033": ("partially_compatible", ["product:KR510902511M"], ["invest"], ["risk_grade"], []),
    "R-034": ("partially_compatible", ["product:KR5110501016"], ["invest"], ["total_fee"], []),
    "R-039": ("not_applicable", [], [], [], []),
    "R-040": ("not_applicable", [], [], [], []),
}


PHRASE_NORMALIZER_RULES = (
    ("개인부담금", ("본인 부담금",), "R-007"),
    ("세액공제", ("세액 공제 혜택",), "R-008"),
    ("세금상 불이익", ("연금외수령", "기타소득세"), "R-010"),
    ("세액공제 대상", ("종합소득", "세액공제 납입한도"), "R-012"),
    ("다른 금융회사로 이전", ("사업자이전", "계약이전"), "R-014"),
    ("퇴직연금 제도 변경", ("퇴직급여 제도 변경", "퇴직연금규약"), "R-017"),
    ("연금으로 수령", ("수급요건", "연금 지급기간"), "R-022"),
)


def _normalise_question(question: str) -> str:
    normalized = unicodedata.normalize("NFKC", question).lower()
    return re.sub(r"[^0-9a-z가-힣]", "", normalized)


def _read_json_or_jsonl(path: Path) -> list[dict]:
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return raw.get("questions", raw.get("rows", []))
    return []


def _project_questions() -> list[tuple[str, str, str]]:
    paths = [
        ROOT / "evaluation/question_bank_v1.jsonl",
        ROOT / "evaluation/question_bank_behavior_contract_v1.jsonl",
        ROOT / "evaluation/closed_core_benchmark_v1.jsonl",
        ROOT / "question_bank/development/semantic_atoms_v1.jsonl",
        ROOT / "evaluation/p32_holdout_manifest.json",
        ROOT / "evaluation/p33_holdout_manifest.json",
        *(ROOT / f"evaluation/p{phase}_closed_holdout_manifest.json" for phase in range(34, 38)),
    ]
    questions = []
    for path in paths:
        for row in _read_json_or_jsonl(path):
            question = row.get("question")
            if not isinstance(question, str):
                continue
            question_id = str(row.get("question_id", row.get("source_question_id", row.get("id", "unknown"))))
            questions.append((str(path.relative_to(ROOT)), question_id, question))
    return questions


def _alignment(question_id: str) -> dict:
    status, subjects, actions, fields, modifiers = ALIGNMENTS.get(
        question_id, ("needs_human_annotation", [], [], [], [])
    )
    return {
        "status": status,
        "subjects": subjects,
        "actions": actions,
        "fields": fields,
        "modifiers": modifiers,
        "automatic_gold_use": False,
    }


def build() -> dict:
    if not FIXTURE.exists():
        raise SystemExit(f"missing reviewed fixture: {FIXTURE}")
    fixture_bytes = FIXTURE.read_bytes()
    source_rows = _read_json_or_jsonl(FIXTURE)
    if len(source_rows) != 40:
        raise SystemExit(f"expected 40 teammate retrieval questions, got {len(source_rows)}")

    prior_by_normalized: dict[str, list[dict]] = {}
    for path, question_id, question in _project_questions():
        prior_by_normalized.setdefault(_normalise_question(question), []).append({
            "path": path,
            "question_id": question_id,
            "question": question,
        })

    crosswalk_rows = []
    for row in source_rows:
        question = row["question"]
        duplicates = prior_by_normalized.get(_normalise_question(question), [])
        crosswalk_rows.append({
            "source_question_id": row["question_id"],
            "source_split": row["split"],
            "question": question,
            "category": row["category"],
            "answerable": row["answerable"],
            "product_codes": row["product_codes"],
            "relevant_chunks": row["relevant_chunks"],
            "relevant_source_ids": row["relevant_source_ids"],
            "required_terms": row["required_terms"],
            "evidence_requirement": row["evidence_requirement"],
            "normalized_duplicate": bool(duplicates),
            "duplicate_of": duplicates,
            "semantic_atom_alignment": _alignment(row["question_id"]),
            "use_as": "dev_reference",
            "fresh_holdout": False,
        })

    taxonomy = {
        "source": {
            "branch": REMOTE_BRANCH,
            "commit": REMOTE_COMMIT,
            "document": "docs/retrieval_failure_analysis_normalized.md",
            "scope": "teammate dev retrieval analysis only",
        },
        "crosswalk": {
            "query_document_vocabulary_gap": {
                "current_possible_owners": ["semantic_normalization", "retrieval_query_formulation"],
                "automatic_equivalence": False,
            },
            "chunk_too_broad": {
                "current_possible_owners": ["chunking_granularity", "evidence_selection"],
                "automatic_equivalence": False,
            },
            "evidence_spans_multiple_chunks": {
                "current_possible_owners": ["requirement_composition", "multi_evidence_composition"],
                "automatic_equivalence": False,
            },
            "repetitive_document_noise": {
                "current_possible_owners": ["retrieval_ranking", "evidence_selection"],
                "automatic_equivalence": False,
            },
            "table_rendering": {
                "current_possible_owners": ["table_parsing", "table_field_retrieval"],
                "automatic_equivalence": False,
            },
        },
    }
    phrase_baseline = {
        "source": {
            "branch": REMOTE_BRANCH,
            "commit": REMOTE_COMMIT,
            "path": "src/retrieval/query_normalizer.py",
        },
        "role": "lexical_baseline_only",
        "production_import_prohibited": True,
        "rules": [
            {"phrase": phrase, "aliases": list(aliases), "observed_dev_case": case}
            for phrase, aliases, case in PHRASE_NORMALIZER_RULES
        ],
        "comparison_hypothesis": "Use only in a future P38 comparison against compositional parsing; do not copy these phrase rules into a candidate normalizer.",
    }
    inventory = {
        "branch": REMOTE_BRANCH,
        "commit": REMOTE_COMMIT,
        "reviewed_files": [
            "evaluation/retrieval_questions.jsonl",
            "docs/retrieval_failure_analysis_normalized.md",
            "docs/retrieval_final_evaluation.md",
            "src/retrieval/query_normalizer.py",
            "src/orchestration/query_analyzer.py",
            "src/retrieval/fielded_bm25_retriever.py",
            "src/orchestration/evidence_assessor.py",
            "src/orchestration/context_builder.py",
        ],
        "assets": [
            {"path": "evaluation/retrieval_questions.jsonl", "role": "dev_fixture", "recommended_action": "integrate", "reason": "40-question evidence fixture with relevant chunks, source IDs, terms, and any/all contract."},
            {"path": "docs/retrieval_failure_analysis_normalized.md", "role": "reference_only", "recommended_action": "copy_as_reference", "reason": "Provides retrieval failure taxonomy without changing current ownership labels."},
            {"path": "docs/retrieval_final_evaluation.md", "role": "reference_only", "recommended_action": "copy_as_reference", "reason": "Records dev/test retrieval generalization gap for future comparison design."},
            {"path": "src/retrieval/query_normalizer.py", "role": "lexical_baseline", "recommended_action": "copy_as_reference", "reason": "Observed-dev phrase expansion baseline only; prohibited from candidate import."},
            {"path": "src/orchestration/query_analyzer.py", "role": "reference_only", "recommended_action": "do_not_merge", "reason": "Coarse one-intent keyword analyzer; baseline, not a compositional parser."},
            {"path": "src/retrieval/fielded_bm25_retriever.py", "role": "retrieval_experiment", "recommended_action": "defer", "reason": "Potential table-row-key retrieval A/B after P38 parsing is evaluated."},
            {"path": "src/orchestration/evidence_assessor.py", "role": "reference_only", "recommended_action": "do_not_merge", "reason": "Its context-presence checks are weaker than current subject-field-value-scope contract."},
            {"path": "src/orchestration/context_builder.py", "role": "reference_only", "recommended_action": "do_not_merge", "reason": "Top-k deduplication alone is not a factual evidence sufficiency contract."},
        ],
        "fixture_snapshot": {
            "path": "evaluation/retrieval_questions.jsonl",
            "question_count": len(source_rows),
            "sha256": hashlib.sha256(fixture_bytes).hexdigest(),
            "source_commit": REMOTE_COMMIT,
            "matches_reviewed_branch": True,
            "fresh_holdout": False,
        },
        "production_merge": False,
        "hcx_calls": 0,
    }
    return {"inventory": inventory, "crosswalk_rows": crosswalk_rows, "taxonomy": taxonomy, "phrase_baseline": phrase_baseline}


def main() -> None:
    artifacts = build()
    INTEGRATIONS.mkdir(parents=True, exist_ok=True)
    BASELINES.mkdir(parents=True, exist_ok=True)
    (INTEGRATIONS / "yw_branch_asset_inventory.json").write_text(
        json.dumps(artifacts["inventory"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (INTEGRATIONS / "yw_retrieval_fixture_crosswalk.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in artifacts["crosswalk_rows"]) + "\n",
        encoding="utf-8",
    )
    (INTEGRATIONS / "yw_failure_taxonomy_crosswalk.json").write_text(
        json.dumps(artifacts["taxonomy"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (BASELINES / "yw_phrase_normalizer_reference.json").write_text(
        json.dumps(artifacts["phrase_baseline"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = {
        "questions": len(artifacts["crosswalk_rows"]),
        "duplicates": sum(row["normalized_duplicate"] for row in artifacts["crosswalk_rows"]),
        "alignment": {
            status: sum(row["semantic_atom_alignment"]["status"] == status for row in artifacts["crosswalk_rows"])
            for status in ("compatible", "partially_compatible", "needs_human_annotation", "not_applicable")
        },
        "hcx_calls": 0,
        "production_merge": False,
    }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
