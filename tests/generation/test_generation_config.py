import pytest
from src.config.generation import GenerationSettings
from src.generation.factory import build_answer_generator
def test_evaluation_rejects_fake(monkeypatch):
    monkeypatch.setenv("APP_ENV","evaluation"); monkeypatch.setenv("GENERATOR_BACKEND","fake")
    with pytest.raises(RuntimeError): GenerationSettings.from_env()
def test_hcx_requires_complete_config():
    with pytest.raises(ValueError): build_answer_generator(GenerationSettings(generator_backend="hcx"))
