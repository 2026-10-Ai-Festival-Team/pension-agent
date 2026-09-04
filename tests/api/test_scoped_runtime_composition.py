from src.api import main
from src.config.generation import GenerationSettings
from src.experiments.direct_requirement_e2e import DirectRequirementE2EAgent
from src.generation.fake import FakeGenerator


def _settings(**overrides):
    defaults = {
        "generator_backend": "hcx",
        "hcx_api_key": "test",
        "hcx_model": "HCX-007",
        "hcx_base_url": "https://example.invalid",
        "hcx_min_interval_seconds": 0,
    }
    return GenerationSettings(**(defaults | overrides))


def test_browser_runtime_builds_the_frozen_scoped_path_not_legacy_p27(monkeypatch):
    retriever = object()
    monkeypatch.setattr(main, "build_frozen_retriever", lambda *_: retriever)
    monkeypatch.setattr(main, "build_answer_generator", lambda *_args, **_kwargs: FakeGenerator())

    app = main.create_browser_configured_app("chunks.jsonl", "index", _settings())

    assert isinstance(app.state.agent, DirectRequirementE2EAgent)
    assert app.state.agent.preparation.retriever is retriever
    assert app.state.agent.scoped_selector.__class__.__name__ == "ResolverFirstScopedSelector"


def test_browser_runtime_refuses_to_silently_fall_back_to_legacy_p27():
    settings = _settings(generator_backend="fake", hcx_model="")

    try:
        main.create_browser_configured_app("chunks.jsonl", "index", settings)
    except RuntimeError as error:
        assert "HCX-007" in str(error)
    else:
        raise AssertionError("scoped browser runtime must not fall back to P27")
