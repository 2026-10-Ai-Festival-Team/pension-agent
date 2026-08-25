from scripts import build_p37_closed_holdout as p37


def test_p37_builder_writes_a_hash_valid_manifest_without_prior_question_overlap(tmp_path, monkeypatch) -> None:
    output = tmp_path / "p37.json"
    monkeypatch.setattr(p37, "MANIFEST_PATH", output)

    p37.main()

    manifest = __import__("json").loads(output.read_text(encoding="utf-8"))
    assert manifest["validation"]["exact_normalised_overlap_with_prior_evaluation_files"] == 0
    assert manifest["validation"]["missing_declared_gold_chunk_ids"] == 0
    assert len(manifest["questions"]) == 18
