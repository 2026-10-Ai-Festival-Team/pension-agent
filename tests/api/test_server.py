import pytest
from fastapi.testclient import TestClient
from src.api.main import create_app
from src.api import server


def test_server_rejects_missing_runtime_artifacts(monkeypatch, tmp_path):
    monkeypatch.setenv("CORPUS_PATH", str(tmp_path / "missing.jsonl"))
    monkeypatch.setenv("BM25_INDEX_PATH", str(tmp_path / "missing-index"))
    with pytest.raises(RuntimeError, match="Required corpus"):
        server.build_application()


def test_server_passes_validated_paths_to_app(monkeypatch, tmp_path):
    corpus = tmp_path / "chunks.jsonl"; corpus.write_text("", encoding="utf-8")
    index = tmp_path / "index"; index.mkdir(); (index / "index_meta.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("CORPUS_PATH", str(corpus)); monkeypatch.setenv("BM25_INDEX_PATH", str(index))
    monkeypatch.setattr(server, "create_local_app", lambda c, i: (c, i))
    assert server.build_application() == (corpus, index)


def test_health_endpoint_is_available_without_runtime_artifacts():
    assert TestClient(create_app()).get("/health").json() == {"status": "ok"}
