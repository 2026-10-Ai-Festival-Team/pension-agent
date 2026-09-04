import json
from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_runtime_registry_has_complete_inventory_without_inventing_doc_ids():
    registry = json.loads((ROOT / "data/provenance/runtime_citation_provenance_v2.json").read_text(encoding="utf-8"))
    audit = json.loads((ROOT / "data/provenance/runtime_citation_provenance_audit_v2.json").read_text(encoding="utf-8"))

    assert registry["summary"] == {
        "runtime_source_count": 155,
        "source_identity_count": 155,
        "mapped_source_count": 3,
        "unmapped_source_count": 152,
        "locator_available_source_count": 137,
        "document_scope_fallback_source_count": 18,
        "citation_renderable_source_count": 155,
    }
    assert len(registry["records"]) == 155
    assert all(
        record["document_id"] is None
        for record in registry["records"]
        if record["mapping_status"] != "verified"
    )
    assert audit["inventory"]["manifest_source_count"] == 158
    assert audit["inventory"]["excluded_from_runtime_count"] == 3
    assert audit["mapping"]["duplicate_document_id"] == []
    assert audit["mapping"]["duplicate_source_path"] == []
    assert audit["mapping"]["path_mismatch"] == []
    assert audit["mapping"]["unknown_source"] == []
    assert audit["mapping"]["invalid_document_id"] == []
    assert audit["mapping"]["source_identity_count"] == 155
    assert audit["mapping"]["citation_renderable_source_count"] == 155
    assert audit["gate"]["decision"] == "PASS"
