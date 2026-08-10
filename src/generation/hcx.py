import json
import time
import urllib.error
import urllib.request

from src.generation.base import GenerationResult
from src.generation.errors import GenerationError, GenerationResponseError
from src.generation.prompt_builder import PromptBuilder
from src.generation.rate_limit import GlobalMinIntervalLimiter


class UrllibTransport:
    def post(self, url, headers, payload, timeout):
        request = urllib.request.Request(
            url, data=json.dumps(payload).encode(), headers=headers, method="POST"
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode()


class HyperClovaXGenerator:
    def __init__(self, *, config, transport=None, prompt_builder=None, rate_limiter=None, sleeper=time.sleep):
        self.config = config
        self.transport = transport or UrllibTransport()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.rate_limiter = rate_limiter or GlobalMinIntervalLimiter(config.hcx_min_interval_seconds)
        self.sleeper = sleeper

    @staticmethod
    def _retry_after_seconds(headers):
        value = headers.get("Retry-After") if headers else None
        try:
            return float(value) if value is not None else None
        except ValueError:
            return None

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
        attempt_history = []
        for attempt in range(self.config.max_retries + 1):
            attempt_started = time.perf_counter()
            diagnostic = {"attempt_count": attempt + 1, "retry_used": attempt > 0}
            try:
                diagnostic["rate_limit_wait_ms"] = round(self.rate_limiter.acquire() * 1000, 3)
                response_headers = {}
                try:
                    status, body = self.transport.post(
                        self.config.hcx_base_url, headers, payload, self.config.timeout_seconds
                    )
                except urllib.error.HTTPError as error:
                    status = error.code
                    body = error.read().decode(errors="replace")
                    response_headers = error.headers or {}
                diagnostic["http_status"] = status
                diagnostic["retry_after_seconds"] = self._retry_after_seconds(response_headers)
                if status in {401, 403}:
                    raise GenerationError("HCX authentication failed", diagnostic=diagnostic)
                if status == 429 or status >= 500:
                    if attempt < self.config.max_retries:
                        retry_delay = max(0.1 * (attempt + 1), diagnostic["retry_after_seconds"] or 0)
                        diagnostic["retry_delay_ms"] = round(retry_delay * 1000, 3)
                        diagnostic["attempt_latency_ms"] = round((time.perf_counter() - attempt_started) * 1000, 3)
                        attempt_history.append({"http_status": status, "attempt_latency_ms": diagnostic["attempt_latency_ms"], "retry_delay_ms": diagnostic["retry_delay_ms"], "outcome": "retry"})
                        self.sleeper(retry_delay)
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
                diagnostic["attempt_latency_ms"] = round((time.perf_counter() - attempt_started) * 1000, 3)
                attempt_history.append({"http_status": status, "attempt_latency_ms": diagnostic["attempt_latency_ms"], "outcome": "success"})
                diagnostic["attempt_history"] = attempt_history
                return GenerationResult(
                    answer,
                    cited,
                    self.config.hcx_model,
                    (time.perf_counter() - started) * 1000,
                    finish_reason,
                    usage,
                    diagnostic,
                )
            except GenerationError as error:
                diagnostic = error.diagnostic or diagnostic
                diagnostic["attempt_latency_ms"] = round((time.perf_counter() - attempt_started) * 1000, 3)
                attempt_history.append({"http_status": diagnostic.get("http_status"), "attempt_latency_ms": diagnostic["attempt_latency_ms"], "exception_type": type(error).__name__, "outcome": "failed"})
                diagnostic["attempt_history"] = attempt_history
                error.diagnostic = diagnostic
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
                diagnostic["attempt_latency_ms"] = round((time.perf_counter() - attempt_started) * 1000, 3)
                attempt_history.append({"http_status": diagnostic.get("http_status"), "attempt_latency_ms": diagnostic["attempt_latency_ms"], "exception_type": type(exc).__name__, "outcome": "failed"})
                diagnostic["attempt_history"] = attempt_history
                if attempt < self.config.max_retries:
                    self.sleeper(0.1 * (attempt + 1))
                    continue
                raise GenerationError("HCX generation failed", diagnostic=diagnostic)
