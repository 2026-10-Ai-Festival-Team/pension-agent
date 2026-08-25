import io
import json
import pytest
from src.config.generation import GenerationSettings
from src.generation.hcx import HyperClovaXGenerator
from src.generation.errors import GenerationError
from src.generation.prompt_builder import PromptBuilder
from src.models.chunk import ChunkLocator
from src.models.retrieval import SearchResult

class Transport:
    def __init__(self, responses): self.responses=list(responses); self.calls=0
    def post(self,*args):
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response
def context(): return [SearchResult(rank=1,chunk_id="c1",source_id="s",source_path="x.pdf",source_format="pdf",document_type="p",locator=ChunkLocator(page_start=1,page_end=1),element_ids=["e"],score=1,text="근거")]
def config(retries=0): return GenerationSettings(generator_backend="hcx",hcx_api_key="secret",hcx_model="HCX",hcx_base_url="https://example",max_retries=retries,hcx_min_interval_seconds=0)
def test_parses_json_and_code_fence():
    t=Transport([(200,json.dumps({"choices":[{"message":{"content":"```json\n{\"answer\":\"답변\",\"cited_chunk_ids\":[\"c1\"]}\n```"}}]}))])
    assert HyperClovaXGenerator(config=config(),transport=t).generate(question="q",contexts=context(),query_analysis=None).cited_chunk_ids==["c1"]

def test_parses_hcx_v3_result_envelope():
    body = {
        "status": {"code": "20000"},
        "result": {
            "message": {"content": '{"answer":"답변","cited_chunk_ids":["c1"]}'},
            "stopReason": "end_turn",
        },
    }
    result = HyperClovaXGenerator(config=config(), transport=Transport([(200, json.dumps(body))])).generate(question="q", contexts=context(), query_analysis=None)
    assert result.answer == "답변"
    assert result.finish_reason == "end_turn"
def test_auth_is_not_retried():
    t=Transport([(401,"bad")])
    with pytest.raises(GenerationError): HyperClovaXGenerator(config=config(2),transport=t).generate(question="q",contexts=context(),query_analysis=None)
    assert t.calls==1
def test_timeout_like_failure_retries():
    t=Transport([TimeoutError(),(200,json.dumps({"message":{"content":"{\"answer\":\"a\",\"cited_chunk_ids\":[\"c1\"]}"}}))])
    result = HyperClovaXGenerator(config=config(1),transport=t).generate(question="q",contexts=context(),query_analysis=None)
    assert result.answer=="a"
    assert t.calls==2
    assert len(result.diagnostic["attempt_history"]) == 2
    assert result.diagnostic["attempt_history"][0]["exception_type"] == "TimeoutError"


def test_truncated_json_records_sanitized_diagnostic_metadata():
    body = json.dumps({"result": {"message": {"content": '{"answer":"답변","cited_chunk_ids":["c1"'}}})
    with pytest.raises(GenerationError) as error:
        HyperClovaXGenerator(config=config(), transport=Transport([(200, body)])).generate(question="q", contexts=context(), query_analysis=None)

    diagnostic = error.value.diagnostic
    assert diagnostic["http_status"] == 200
    assert diagnostic["exception_type"] == "JSONDecodeError"
    assert diagnostic["content_length"] > 0
    assert "답변" not in diagnostic["content_tail_shape"]


def test_citation_field_type_is_recorded_without_accepting_response():
    body = json.dumps({"result": {"message": {"content": '{"answer":"답변","cited_chunk_ids":"c1"}'}}})
    with pytest.raises(GenerationError) as error:
        HyperClovaXGenerator(config=config(), transport=Transport([(200, body)])).generate(question="q", contexts=context(), query_analysis=None)

    assert error.value.diagnostic["cited_chunk_ids_type"] == "str"


def test_empty_answer_and_citation_are_recorded_as_contract_failures():
    body = json.dumps({"result": {"message": {"content": '{"answer":"","cited_chunk_ids":[]}'}}})

    with pytest.raises(GenerationError) as error:
        HyperClovaXGenerator(config=config(), transport=Transport([(200, body)])).generate(
            question="q", contexts=context(), query_analysis=None
        )

    assert error.value.diagnostic["response_contract_failures"] == [
        "empty_answer",
        "empty_cited_chunk_ids",
    ]


def test_prompt_builder_explicitly_forbids_empty_json_output():
    prompt = PromptBuilder().build("질문", context())

    assert "빈 문자열과 빈 배열은 반환하면 안 됩니다" in prompt


def test_generator_records_global_rate_limit_wait():
    class Limiter:
        def acquire(self): return 2.0

    body = json.dumps({"message": {"content": '{"answer":"답변","cited_chunk_ids":["c1"]}'}})
    result = HyperClovaXGenerator(config=config(), transport=Transport([(200, body)]), rate_limiter=Limiter()).generate(question="q", contexts=context(), query_analysis=None)

    assert result.diagnostic["rate_limit_wait_ms"] == 2000.0


def test_429_uses_bounded_retry_and_retry_after_header():
    class Headers(dict):
        pass

    class Http429Transport:
        def __init__(self): self.calls = 0
        def post(self, *_):
            self.calls += 1
            if self.calls == 1:
                error = __import__("urllib.error").error.HTTPError("https://example", 429, "too many", Headers({"Retry-After": "1"}), io.BytesIO(b""))
                raise error
            return 200, json.dumps({"message": {"content": '{"answer":"답변","cited_chunk_ids":["c1"]}'}})

    sleeps = []
    result = HyperClovaXGenerator(config=config(1), transport=Http429Transport(), sleeper=sleeps.append).generate(question="q", contexts=context(), query_analysis=None)

    assert result.answer == "답변"
    assert sleeps == [1.0]
    first_attempt = result.diagnostic["attempt_history"][0]
    assert first_attempt["http_status"] == 429
    assert first_attempt["retry_after_seconds"] == 1.0
    assert first_attempt["rate_limit_wait_ms"] == 0.0
    assert first_attempt["request_started_offset_ms"] is not None
    assert first_attempt["request_completed_offset_ms"] is not None
    assert first_attempt["request_started_monotonic_ms"] is not None
    assert first_attempt["request_completed_monotonic_ms"] is not None
