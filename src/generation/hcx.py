import json, time, urllib.request
from dataclasses import dataclass
from src.generation.base import GenerationResult
from src.generation.errors import GenerationError, GenerationResponseError
from src.generation.prompt_builder import PromptBuilder

class UrllibTransport:
    def post(self,url,headers,payload,timeout):
        request=urllib.request.Request(url,data=json.dumps(payload).encode(),headers=headers,method="POST")
        with urllib.request.urlopen(request,timeout=timeout) as response: return response.status, response.read().decode()

class HyperClovaXGenerator:
    def __init__(self, *, config, transport=None, prompt_builder=None): self.config=config; self.transport=transport or UrllibTransport(); self.prompt_builder=prompt_builder or PromptBuilder()
    def generate(self, *, question, contexts, query_analysis):
        started=time.perf_counter(); payload=self.prompt_builder.payload(question,contexts,self.config.hcx_model); headers={"Authorization":f"Bearer {self.config.hcx_api_key}","Content-Type":"application/json"}
        for attempt in range(self.config.max_retries+1):
            try:
                status, body=self.transport.post(self.config.hcx_base_url,headers,payload,self.config.timeout_seconds)
                if status in {401,403}: raise GenerationError("HCX authentication failed")
                if status==429 or status>=500:
                    if attempt < self.config.max_retries: time.sleep(.1*(attempt+1)); continue
                    raise GenerationError("HCX service unavailable")
                if status>=400: raise GenerationError("HCX request failed")
                data=json.loads(body)
                # HCX v3 responses wrap the assistant message in ``result``.
                # Keep the OpenAI-compatible fallbacks to support mocked and
                # future-compatible response envelopes.
                result = data.get("result", {}) if isinstance(data, dict) else {}
                result_message = result.get("message", {}) if isinstance(result, dict) else {}
                content = (
                    result_message.get("content")
                    or data.get("message", {}).get("content")
                    or data.get("choices", [{}])[0].get("message", {}).get("content")
                )
                if content and content.strip().startswith("```"): content=content.strip().split("\n",1)[1].rsplit("```",1)[0]
                parsed=json.loads(content); answer=parsed.get("answer","").strip(); cited=parsed.get("cited_chunk_ids",[])
                if not answer or not isinstance(cited,list): raise GenerationResponseError("Invalid HCX response")
                finish_reason = (
                    result.get("stopReason")
                    or result.get("finishReason")
                    or data.get("finish_reason")
                    or data.get("finishReason")
                )
                return GenerationResult(answer,cited,self.config.hcx_model,(time.perf_counter()-started)*1000,finish_reason)
            except GenerationError: raise
            except Exception:
                if attempt < self.config.max_retries: time.sleep(.1*(attempt+1)); continue
                raise GenerationError("HCX generation failed")
