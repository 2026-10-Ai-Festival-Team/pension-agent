from scripts import build_p36_closed_holdout as p36


def test_p36_builder_writes_a_hash_valid_manifest_without_prior_question_overlap(tmp_path, monkeypatch) -> None:
    output = tmp_path / "p36.json"
    monkeypatch.setattr(p36, "MANIFEST_PATH", output)

    p36.main()

    manifest = p36.json.loads(output.read_text(encoding="utf-8"))
    assert manifest["status"] == "frozen_before_pre_hcx_execution"
    assert manifest["denominators"] == {"total": 18, "answerable": 18, "unsupported": 0}
    assert manifest["validation"]["exact_normalised_overlap_with_prior_evaluation_files"] == 0
    assert p36.hashlib.sha256(
        p36.json.dumps(
            {key: value for key, value in manifest.items() if key not in {"manifest_sha256", "validation"}},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest() == manifest["manifest_sha256"]
