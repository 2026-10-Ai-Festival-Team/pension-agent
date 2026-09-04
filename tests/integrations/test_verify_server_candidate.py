from scripts.verify_server_candidate import _citation_valid, _raw_identifier_exposed


def test_server_smoke_citation_checks_document_identity_without_raw_chunk_ids():
    trace = {"generator_called": True, "cited_documents": [{"source_filename": "doc36.docx"}], "cited_chunk_ids": ["internal-123"]}
    assert _citation_valid("[근거]\n- [doc36.docx]", trace)
    assert not _raw_identifier_exposed("[근거]\n- [doc36.docx]", trace)
    assert _raw_identifier_exposed("[근거]\n- internal-123", trace)
