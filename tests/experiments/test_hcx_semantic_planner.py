import json

from src.config.generation import GenerationSettings
from src.experiments.hcx_semantic_planner import (
    HCXSemanticPlanner,
    ONTOLOGY,
    SemanticPlannerPromptBuilder,
    lexically_normalize,
)


class Transport:
    def __init__(self, body):
        self.body = body
        self.calls = 0

    def post(self, *_args):
        self.calls += 1
        return 200, self.body


def _config():
    return GenerationSettings(generator_backend="hcx", hcx_api_key="test", hcx_model="HCX-007", hcx_base_url="https://example", max_retries=0, hcx_min_interval_seconds=0)


def test_native_semantic_schema_uses_only_current_ontology_enums() -> None:
    payload = SemanticPlannerPromptBuilder().payload("DC 질문", "HCX-007")

    schema = payload["responseFormat"]["schema"]
    assert payload["thinking"] == {"effort": "none"}
    assert schema["required"] == ["subjects", "actions", "fields", "modifiers"]
    assert schema["properties"]["subjects"]["items"]["enum"] == list(ONTOLOGY["subjects"])
    assert "historical" not in schema["properties"]["modifiers"]["items"]["enum"]


def test_hcx_semantic_planner_validates_a_structured_atom_response() -> None:
    content = {"subjects": ["account:DC"], "actions": ["withdraw"], "fields": ["withdrawal_reason", "required_document"], "modifiers": ["before_retirement"]}
    body = json.dumps({"result": {"message": {"content": json.dumps(content)}}})

    result = HCXSemanticPlanner(config=_config(), transport=Transport(body)).plan("질문")

    assert result.schema_valid is True
    assert result.ontology_valid is True
    assert set(result.atoms.fields) == {"withdrawal_reason", "required_document"}


def test_lexical_normalization_is_limited_to_explicit_identity_aliases() -> None:
    normalized = lexically_normalize(" 연저에서 확정기여형 적립금을 중간에 빼도 돼? kr510902773m ")

    assert normalized == "연금저축에서 DC 적립금을 중간에 빼도 돼? KR510902773M"
    # It must not turn a semantic phrase such as '중간에 빼다' into an action.
    assert "withdraw" not in normalized
