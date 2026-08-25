import json

from src.config.generation import GenerationSettings
from src.experiments.hcx_semantic_planner_v21 import HCXSemanticPlannerV21, SemanticPlannerV21PromptBuilder


class Transport:
    def __init__(self, body):
        self.body = body

    def post(self, *_args):
        return 200, self.body


def _config():
    return GenerationSettings(generator_backend="hcx", hcx_api_key="test", hcx_model="HCX-007", hcx_base_url="https://example", max_retries=0, hcx_min_interval_seconds=0)


def test_v21_native_schema_excludes_generic_comparison_and_requires_directional_transfer_shape() -> None:
    schema = SemanticPlannerV21PromptBuilder().payload("DC 질문", "HCX-007")["responseFormat"]["schema"]

    assert "relations" not in schema["properties"]
    assert "directional_transfers" in schema["properties"]
    assert schema["properties"]["directional_transfers"]["items"]["required"] == ["source", "destination"]


def test_v21_parser_accepts_canonical_directional_transfer_only() -> None:
    content = {"subjects": ["account:ISA", "account:pension"], "fields": ["transfer_deadline"], "essential_qualifiers": ["isa_maturity"], "directional_transfers": [{"source": "account:ISA", "destination": "account:pension"}]}
    body = json.dumps({"result": {"message": {"content": json.dumps(content)}}})

    result = HCXSemanticPlannerV21(config=_config(), transport=Transport(body)).plan("ISA 질문")

    assert result.schema_valid is True
    assert result.ontology_valid is True
    assert result.plan.transfers[0].destination == "account:pension"
