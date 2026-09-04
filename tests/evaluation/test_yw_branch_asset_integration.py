import json
from pathlib import Path

import scripts.build_yw_branch_asset_review as review


def test_yw_branch_assets_are_dev_reference_only_and_crosswalk_is_complete(tmp_path, monkeypatch) -> None:
    integrations = tmp_path / "integrations"
    baselines = tmp_path / "baselines"
    monkeypatch.setattr(review, "INTEGRATIONS", integrations)
    monkeypatch.setattr(review, "BASELINES", baselines)

    review.main()

    rows = [
        json.loads(line)
        for line in (integrations / "yw_retrieval_fixture_crosswalk.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 40
    assert len({row["source_question_id"] for row in rows}) == 40
    assert {row["use_as"] for row in rows} == {"dev_reference"}
    assert not any(row["fresh_holdout"] for row in rows)
    assert all(row["semantic_atom_alignment"]["automatic_gold_use"] is False for row in rows)
    assert {
        row["semantic_atom_alignment"]["status"] for row in rows
    } <= {"compatible", "partially_compatible", "needs_human_annotation", "not_applicable"}

    baseline = json.loads((baselines / "yw_phrase_normalizer_reference.json").read_text(encoding="utf-8"))
    assert baseline["role"] == "lexical_baseline_only"
    assert baseline["production_import_prohibited"] is True


def test_yw_phrase_baseline_is_not_imported_by_production_modules() -> None:
    root = Path(__file__).resolve().parents[2]
    production_directories = (root / "src/orchestration", root / "src/retrieval", root / "src/api", root / "src/generation")

    assert not any(
        "yw_phrase_normalizer_reference" in path.read_text(encoding="utf-8")
        for directory in production_directories
        for path in directory.glob("*.py")
    )
