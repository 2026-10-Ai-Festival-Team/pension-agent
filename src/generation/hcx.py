import json
import time
import urllib.request

from src.generation.base import GenerationResult
from src.generation.errors import GenerationError, GenerationResponseError
from src.generation.prompt_builder import PromptBuilder


class UrllibTransport:
    def post(self, url, headers, payload, timeout):
        request = urllib.request.Request(
            url, data=json.dumps(payload).encode(), headers=headers, method="POST"
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode()


class HyperClovaXGenerator:
    def __init__(self, *, config, transport=None, prompt_builder=None):
        self.config = config
        self.transport = transport or UrllibTransport()
        self.prompt_builder = prompt_builder or PromptBuilder()

    @staticmethod
    def _content_metadata(content):
        if not isinstance(content, str):
            return {"message_content_present": False, "content_length": None}
        safe_characters = set('{}[],:.\\"`- \n\r\t')
        shape = "".join(char if char in safe_characters else "x" for char in content)
        return {
            "message_content_present": True,
            "content_length": len(content),
            "content_has_markdown_fence": content.strip().startswith("```"),
            "content_tail_shape": shape[-160:],
        }

    @staticmethod
    def _finish_reason(data, result):
        return (
            result.get("stopReason")
            or result.get("finishReason")
            or data.get("finish_reason")
            or data.get("finishReason")
        )

    def generate(self, *, question, contexts, query_analysis):
        started = time.perf_counter()
        payload = self.prompt_builder.payload(question, contexts, self.config.hcx_model)
        headers = {"Authorization": f"Bearer {self.config.hcx_api_key}", "Content-Type": "application/json"}
        for attempt in range(self.config.max_retries + 1):
            diagnostic = {"attempt_count": attempt + 1, "retry_used": attempt > 0}
            try:
                status, body = self.transport.post(
                    self.config.hcx_base_url, headers, payload, self.config.timeout_seconds
                )
                diagnostic["http_status"] = status
                if status in {401, 403}:
                    raise GenerationError("HCX authentication failed", diagnostic=diagnostic)
                if status == 429 or status >= 500:
                    if attempt < self.config.max_retries:
                        time.sleep(0.1 * (attempt + 1))
                        continue
                    raise GenerationError("HCX service unavailable", diagnostic=diagnostic)
                if status >= 400:
                    raise GenerationError("HCX request failed", diagnostic=diagnostic)

                data = json.loads(body)
                diagnostic.update(
                    {
                        "response_envelope_present": isinstance(data, dict),
                        "response_has_result": isinstance(data, dict) and isinstance(data.get("result"), dict),
                    }
                )
                result = data.get("result", {}) if isinstance(data, dict) else {}
                result_message = result.get("message", {}) if isinstance(result, dict) else {}
                content = (
                    result_message.get("content")
                    or data.get("message", {}).get("content")
                    or data.get("choices", [{}])[0].get("message", {}).get("content")
                )
                diagnostic.update(self._content_metadata(content))
                finish_reason = self._finish_reason(data, result)
                diagnostic["finish_reason"] = finish_reason
                if content and content.strip().startswith("```"):
                    content = content.strip().split("\n", 1)[1].rsplit("```", 1)[0]
                    diagnostic["markdown_fence_removed"] = True
                else:
                    diagnostic["markdown_fence_removed"] = False
                parsed = json.loads(content)
                answer = parsed.get("answer", "").strip()
                cited = parsed.get("cited_chunk_ids", [])
                diagnostic.update(
                    {
                        "json_parse_success": True,
                        "answer_present": "answer" in parsed,
                        "answer_type": type(parsed.get("answer")).__name__,
                        "cited_chunk_ids_present": "cited_chunk_ids" in parsed,
                        "cited_chunk_ids_type": type(cited).__name__,
                    }
                )
                if not answer or not isinstance(cited, list):
                    raise GenerationResponseError("Invalid HCX response", diagnostic=diagnostic)
                usage = result.get("usage") if isinstance(result.get("usage"), dict) else None
                return GenerationResult(
                    answer,
                    cited,
                    self.config.hcx_model,
                    (time.perf_counter() - started) * 1000,
                    finish_reason,
                    usage,
                    diagnostic,
                )
            except GenerationError:
                raise
            except Exception as exc:
                diagnostic.update(
                    {
                        "exception_type": type(exc).__name__,
                        "exception_message": str(exc)[:160],
                        "http_status": getattr(exc, "code", diagnostic.get("http_status")),
                    }
                )
                if isinstance(exc, json.JSONDecodeError):
                    diagnostic.update(
                        {
                            "json_parse_success": False,
                            "json_error_position": exc.pos,
                            "json_error_message": exc.msg,
                        }
                    )
                if attempt < self.config.max_retries:
                    time.sleep(0.1 * (attempt + 1))
                    continue
                raise GenerationError("HCX generation failed", diagnostic=diagnostic)
