import json

from src.config.generation import GenerationSettings
from src.experiments.hcx_semantic_planner_v2 import HCXSemanticPlannerV2, SemanticPlannerV2PromptBuilder


class Transport:
    def __init__(self, body):
        self.body = body

    def post(self, *_args):
        return 200, self.body


def _config():
    return GenerationSettings(generator_backend="hcx", hcx_api_key="test", hcx_model="HCX-007", hcx_base_url="https://example", max_retries=0, hcx_min_interval_seconds=0)


def test_v2_native_schema_has_no_action_component_and_requires_relation_shape() -> None:
    schema = SemanticPlannerV2PromptBuilder().payload("DC 질문", "HCX-007")["responseFormat"]["schema"]

    assert "actions" not in schema["properties"]
    assert schema["required"] == ["subjects", "fields", "essential_qualifiers", "relations"]
    assert schema["properties"]["relations"]["items"]["required"] == ["type", "source", "destination", "left", "right"]


def test_v2_parser_accepts_only_complete_ontology_constrained_relation() -> None:
    content = {"subjects": ["account:ISA", "account:pension"], "fields": ["transfer_deadline", "tax_credit_limit"], "essential_qualifiers": ["isa_maturity", "additional_credit"], "relations": [{"type": "transfer", "source": "account:ISA", "destination": "account:pension", "left": "", "right": ""}]}
    body = json.dumps({"result": {"message": {"content": json.dumps(content)}}})

    result = HCXSemanticPlannerV2(config=_config(), transport=Transport(body)).plan("ISA 질문")

    assert result.schema_valid is True
    assert result.ontology_valid is True
    assert result.plan.relations[0].destination == "account:pension"
