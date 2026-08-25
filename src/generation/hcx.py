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
    def __init__(self, *, config, transport=None, prompt_builder=None, rate_limiter=None, sleeper=time.sleep, response_capture=None):
        self.config = config
        self.transport = transport or UrllibTransport()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.rate_limiter = rate_limiter or GlobalMinIntervalLimiter(
            config.hcx_min_interval_seconds,
            guard_seconds=config.hcx_pacing_guard_seconds,
        )
        self.sleeper = sleeper
        # 기본 로그에는 원문 응답을 남기지 않는다. 제한된 진단 실험에서만 콜백으로 보관한다.
        self.response_capture = response_capture

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

    @staticmethod
    def _attempt_record(diagnostic, **extra):
        """Keep per-attempt timing; the final diagnostic alone is insufficient."""
        record = {
            "attempt_count": diagnostic.get("attempt_count"),
            "retry_used": diagnostic.get("retry_used", False),
            "attempt_started_offset_ms": diagnostic.get("attempt_started_offset_ms"),
            "request_started_offset_ms": diagnostic.get("request_started_offset_ms"),
            "request_completed_offset_ms": diagnostic.get("request_completed_offset_ms"),
            "request_started_monotonic_ms": diagnostic.get("request_started_monotonic_ms"),
            "request_completed_monotonic_ms": diagnostic.get("request_completed_monotonic_ms"),
            "rate_limit_wait_ms": diagnostic.get("rate_limit_wait_ms"),
            "http_status": diagnostic.get("http_status"),
            "retry_after_seconds": diagnostic.get("retry_after_seconds"),
            "attempt_latency_ms": diagnostic.get("attempt_latency_ms"),
            "request_payload_bytes": diagnostic.get("request_payload_bytes"),
            "message_content_length": diagnostic.get("content_length"),
            "usage": diagnostic.get("usage"),
        }
        record.update(extra)
        return record

    def generate(self, *, question, contexts, query_analysis):
        started = time.perf_counter()
        payload = self.prompt_builder.payload(question, contexts, self.config.hcx_model)
        payload_bytes = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        headers = {"Authorization": f"Bearer {self.config.hcx_api_key}", "Content-Type": "application/json"}
        attempt_history = []
        for attempt in range(self.config.max_retries + 1):
            attempt_started = time.perf_counter()
            diagnostic = {
                "attempt_count": attempt + 1,
                "retry_used": attempt > 0,
                "attempt_started_offset_ms": round((attempt_started - started) * 1000, 3),
                "request_payload_bytes": payload_bytes,
            }
            try:
                diagnostic["rate_limit_wait_ms"] = round(self.rate_limiter.acquire() * 1000, 3)
                diagnostic["request_started_offset_ms"] = round((time.perf_counter() - started) * 1000, 3)
                diagnostic["request_started_monotonic_ms"] = round(time.perf_counter() * 1000, 3)
                response_headers = {}
                try:
                    status, body = self.transport.post(
                        self.config.hcx_base_url, headers, payload, self.config.timeout_seconds
                    )
                except urllib.error.HTTPError as error:
                    status = error.code
                    body = error.read().decode(errors="replace")
                    response_headers = error.headers or {}
                if self.response_capture is not None:
                    self.response_capture(status, body)
                diagnostic["request_completed_offset_ms"] = round((time.perf_counter() - started) * 1000, 3)
                diagnostic["request_completed_monotonic_ms"] = round(time.perf_counter() * 1000, 3)
                diagnostic["http_status"] = status
                diagnostic["retry_after_seconds"] = self._retry_after_seconds(response_headers)
                if status in {401, 403}:
                    raise GenerationError("HCX authentication failed", diagnostic=diagnostic)
                if status == 429 or status >= 500:
                    if attempt < self.config.max_retries:
                        retry_delay = max(0.1 * (attempt + 1), diagnostic["retry_after_seconds"] or 0)
                        diagnostic["retry_delay_ms"] = round(retry_delay * 1000, 3)
                        diagnostic["attempt_latency_ms"] = round((time.perf_counter() - attempt_started) * 1000, 3)
                        attempt_history.append(
                            self._attempt_record(
                                diagnostic,
                                retry_delay_ms=diagnostic["retry_delay_ms"],
                                outcome="retry",
                            )
                        )
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
                contract_failures = []
                if not answer:
                    contract_failures.append("empty_answer")
                if not isinstance(cited, list):
                    contract_failures.append("cited_chunk_ids_not_list")
                elif not cited:
                    contract_failures.append("empty_cited_chunk_ids")
                if contract_failures:
                    diagnostic["response_contract_failures"] = contract_failures
                    if "cited_chunk_ids_not_list" in contract_failures:
                        diagnostic["citation_validation_reason"] = "citation_field_schema_violation"
                    elif "empty_cited_chunk_ids" in contract_failures:
                        # 기존 CitationValidationError 경로와 같은 외부 계약을
                        # 유지한다. 다만 세부 원인은 response_contract_failures에
                        # 별도로 남긴다.
                        diagnostic["citation_validation_reason"] = "missing_citation"
                        diagnostic["returned_cited_chunk_ids"] = []
                    raise GenerationResponseError("Invalid HCX response", diagnostic=diagnostic)
                usage = result.get("usage") if isinstance(result.get("usage"), dict) else None
                diagnostic["usage"] = usage
                diagnostic["attempt_latency_ms"] = round((time.perf_counter() - attempt_started) * 1000, 3)
                attempt_history.append(self._attempt_record(diagnostic, outcome="success"))
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
                attempt_history.append(
                    self._attempt_record(
                        diagnostic,
                        exception_type=type(error).__name__,
                        outcome="failed",
                    )
                )
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
                diagnostic.setdefault(
                    "request_completed_offset_ms",
                    round((time.perf_counter() - started) * 1000, 3),
                )
                diagnostic.setdefault("request_completed_monotonic_ms", round(time.perf_counter() * 1000, 3))
                diagnostic["attempt_latency_ms"] = round((time.perf_counter() - attempt_started) * 1000, 3)
                attempt_history.append(
                    self._attempt_record(
                        diagnostic,
                        exception_type=type(exc).__name__,
                        outcome="failed",
                    )
                )
                diagnostic["attempt_history"] = attempt_history
                if attempt < self.config.max_retries:
                    self.sleeper(0.1 * (attempt + 1))
                    continue
                raise GenerationError("HCX generation failed", diagnostic=diagnostic)
