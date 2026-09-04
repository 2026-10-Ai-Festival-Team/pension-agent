"""Contract tests for the frozen P34 Closed factual holdout builder."""
from __future__ import annotations

import json

from scripts import build_p34_closed_holdout as p34
from scripts import evaluate_p34_closed_pre_hcx as pre_hcx
from src.experiments.multi_evidence import RequirementCase, RequirementSlot


def test_p34_is_balanced_closed_factual_scope() -> None:
    manifest = p34._manifest_without_hash()
    assert manifest["denominators"] == {"total": 18, "answerable": 18, "unsupported": 0}
    assert {record["category"] for record in manifest["questions"]} == {
        "institution_closed", "tax_closed", "procedure_closed", "compound_closed", "product_fact", "product_fact_comparison",
    }
    assert all(record["answerability"] == "answerable" for record in manifest["questions"])
    assert all(record["expected_policy_behavior"] == "answer_with_source" for record in manifest["questions"])


def test_p34_gold_evidence_is_declared_by_requirement_group() -> None:
    for record in p34.SPECS:
        assert record["required_requirements"]
        assert record["expected_slot_keys"]
        assert record["evidence_groups"]
        assert all(group for group in record["evidence_groups"])


def test_p34_builder_writes_a_hash_valid_manifest(tmp_path, monkeypatch) -> None:
    output = tmp_path / "p34.json"
    monkeypatch.setattr(p34, "MANIFEST_PATH", output)
    p34.main()
    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert manifest["manifest_sha256"]
    assert manifest["validation"]["missing_declared_gold_chunk_ids"] == 0


def test_p34_evaluator_accepts_declared_db_dc_schema_equivalent_plan() -> None:
    case = RequirementCase(
        question_id="dynamic:db_dc_benefit_calculation",
        role="test",
        slots=tuple(
            RequirementSlot(name=key, terms=(key,), key=key)
            for key in ("db_benefit", "dc_benefit", "db_operation", "dc_operation")
        ),
    )

    covered, status = pre_hcx._plan_coverage(
        "db_dc_general_comparison",
        ["db_dc_operation_party", "db_dc_benefit_determination", "db_dc_contribution_structure"],
        case,
    )

    assert covered
    assert status == "schema_equivalent"
