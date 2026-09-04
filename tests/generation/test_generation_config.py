import pytest
from src.config.generation import GenerationSettings
from src.generation.factory import build_answer_generator
from src.generation.hcx import HyperClovaXGenerator
from src.generation.prompt_builder import NativeStructuredOutputPromptBuilder
def test_evaluation_rejects_fake(monkeypatch):
    monkeypatch.setenv("APP_ENV","evaluation"); monkeypatch.setenv("GENERATOR_BACKEND","fake")
    with pytest.raises(RuntimeError): GenerationSettings.from_env()
def test_hcx_requires_complete_config():
    with pytest.raises(ValueError): build_answer_generator(GenerationSettings(generator_backend="hcx"))


def test_hcx_007_uses_native_structured_output_builder():
    generator = build_answer_generator(GenerationSettings(
        generator_backend="hcx",
        hcx_api_key="test-key",
        hcx_model="HCX-007",
        hcx_base_url="https://example.invalid/hcx",
    ))

    assert isinstance(generator, HyperClovaXGenerator)
    assert isinstance(generator.prompt_builder, NativeStructuredOutputPromptBuilder)
