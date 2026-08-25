import json

import scripts.attribute_p38_2_semantic_atom_failures as attribution


def test_p38_2_attribution_covers_each_non_exact_requirement_once(tmp_path, monkeypatch) -> None:
    output = tmp_path / "p38_2a.json"
    monkeypatch.setattr(attribution, "OUTPUT", output)
    attribution.main()
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["failure_count"] == 14
    assert len(report["failures"]) == 14
    assert len({failure["source_question_id"] for failure in report["failures"]}) == 14
    assert sum(report["primary_owner_summary"].values()) == 14
    assert sum(report["failure_family_summary"].values()) == 14
    assert report["hcx_calls"] == 0
    assert report["candidate_agent_changed"] is False
    assert report["parser_changed"] is False
