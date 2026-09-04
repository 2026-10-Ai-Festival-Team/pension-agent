import json

from scripts import build_semantic_atoms_v1 as atoms


def test_semantic_atoms_v1_is_a_complete_development_only_compositional_spec(tmp_path, monkeypatch) -> None:
    output = tmp_path / "semantic_atoms.jsonl"
    metadata = tmp_path / "semantic_atoms_metadata.json"
    monkeypatch.setattr(atoms, "OUTPUT", output)
    monkeypatch.setattr(atoms, "METADATA", metadata)

    atoms.main()

    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 30
    assert all(row["split"] == "development_regression" for row in rows)
    assert all(row["subjects"] and row["actions"] and row["fields"] for row in rows)
    assert all(len(row["composed_requirements"]) == len(row["fields"]) for row in rows)
