import json

import scripts.build_p38_2_semantic_atom_holdout as holdout


def test_p38_2_manifest_is_frozen_and_has_no_normalized_prior_overlap(tmp_path, monkeypatch) -> None:
    output = tmp_path / "p38_2.jsonl"
    metadata = tmp_path / "p38_2_metadata.json"
    monkeypatch.setattr(holdout, "OUTPUT", output)
    monkeypatch.setattr(holdout, "METADATA", metadata)

    holdout.main()

    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    manifest = json.loads(metadata.read_text(encoding="utf-8"))
    assert len(rows) == 18
    assert len({row["source_question_id"] for row in rows}) == 18
    assert {row["split"] for row in rows} == {"fresh_holdout_frozen"}
    assert manifest["normalised_overlap_with_prior_material"] == 0
    assert manifest["status"] == "frozen_before_isolated_parser_execution"
