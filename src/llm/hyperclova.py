from __future__ import annotations

import json
import time
import uuid
from typing import Any

import requests


class HyperClovaError(RuntimeError):
    pass


class HyperClovaClient:
    def __init__(self, api_key: str, request_id: str, endpoint: str, model: str, timeout: float = 30, max_retries: int = 2):
        self.api_key = api_key
        self.request_id = request_id or uuid.uuid4().hex
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.endpoint and self.model)

    def _headers(self) -> dict[str, str]:
        key = self.api_key if self.api_key.lower().startswith("bearer ") else f"Bearer {self.api_key}"
        return {
            "Authorization": key,
            "X-NCP-CLOVASTUDIO-REQUEST-ID": self.request_id,
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "text/event-stream",
        }

    @staticmethod
    def _content(payload: dict[str, Any]) -> str:
        candidates = [
            payload.get("message", {}).get("content"),
            payload.get("result", {}).get("message", {}).get("content"),
            payload.get("delta"),
        ]
        for value in candidates:
            if isinstance(value, str):
                return value
            if isinstance(value, list):
                return "".join(item.get("text", "") for item in value if isinstance(item, dict))
        return ""

    @staticmethod
    def _merge_stream(previous: str, incoming: str) -> str:
        """Support both token deltas and cumulative/final SSE messages."""
        if not incoming:
            return previous
        if incoming.startswith(previous):
            return incoming
        if previous.endswith(incoming) or incoming in previous:
            return previous
        return previous + incoming

    def chat(self, system_prompt: str, user_prompt: str, max_tokens: int = 1024, temperature: float = 0.1) -> str:
        if not self.configured:
            raise HyperClovaError("HCX 환경변수가 설정되지 않았습니다.")
        payload = {
            "messages": [
                {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "text", "text": user_prompt}]},
            ],
            "topP": 0.8, "topK": 0, "maxTokens": max_tokens,
            "temperature": temperature, "repetitionPenalty": 1.1,
            "stop": [], "seed": 0, "includeAiFilters": True,
        }
        url = f"{self.endpoint}/v3/chat-completions/{self.model}"
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with requests.post(url, headers=self._headers(), json=payload, stream=True, timeout=self.timeout) as response:
                    response.raise_for_status()
                    answer = ""
                    final_answer = ""
                    for line in response.iter_lines(decode_unicode=True):
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            parsed = json.loads(data)
                            content = self._content(parsed)
                            result_content = parsed.get("result", {}).get("message", {}).get("content")
                            if result_content:
                                final_answer = self._content({"message": {"content": result_content}})
                            elif "aiFilter" in parsed:
                                final_answer = content
                            else:
                                answer += content
                        except json.JSONDecodeError:
                            continue
                    answer = (final_answer or answer).strip()
                    if not answer:
                        raise HyperClovaError("HCX가 빈 응답 또는 해석할 수 없는 응답을 반환했습니다.")
                    return answer
            except (requests.RequestException, HyperClovaError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(0.5 * (2**attempt))
        raise HyperClovaError(f"HCX 호출 실패: {last_error}")
