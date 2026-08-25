import json


class PromptBuilder:
    def build(self, question, contexts):
        evidence="\n\n".join(f"[근거]\nchunk_id: {c.chunk_id}\n문서: {c.source_path}\n위치: {c.locator.page_start or c.locator.sheet}\n내용: {c.text}" for c in contexts)
        allowed_chunk_ids = ", ".join(c.chunk_id for c in contexts)
        return f"제공된 문서 근거만 사용해 답하세요. 근거 밖 사실·수치·상품코드를 추가하지 마세요. 단순 사실 질문은 결론과 핵심 근거를 1~2문장으로 답하되, 비교·절차·세제·조건처럼 둘 이상의 항목을 묻는 질문은 각 항목을 빠뜨리지 말고 항목별로 설명하세요. 사유별·조건별로 달라지는 내용은 그 구분을 밝혀야 하며, 근거에 없는 세부사항은 만들지 마세요. JSON만 반환하세요: {{\"answer\": string, \"cited_chunk_ids\": [string]}}. answer는 반드시 비어 있지 않은 한국어 문장이어야 하고 cited_chunk_ids에는 반드시 아래 허용 chunk_id 중 답변에 사용한 하나 이상을 한 글자도 바꾸지 않고 복사하세요. 빈 문자열과 빈 배열은 반환하면 안 됩니다. 빈 배열은 허용되지 않습니다. 제공된 근거만으로 직접 답하기 어렵다고 판단해도 빈 JSON을 반환하지 말고, 그 한계를 짧게 설명하고 그 판단에 실제로 사용한 가장 관련 있는 chunk_id를 인용하세요. source_id, 문서명, 파일 경로, 페이지 번호, chunk_id 일부는 인용 ID가 아니며 사용하면 안 됩니다. 새 ID를 만들거나 허용 ID를 줄이거나 수정하지 마세요.\n\n[허용 chunk_id]\n{allowed_chunk_ids}\n\n[질문]\n{question}\n\n{evidence}"

    def payload(self, question, contexts, model):
        prompt = self.build(question, contexts)
        # HCX-007 is an inference model. Its v3 API requires a typed text
        # content array and ``maxCompletionTokens``; ``maxTokens`` is for the
        # standard/DASH generation contract and causes a 400 for HCX-007.
        if model.upper() == "HCX-007":
            return {
                "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
                "thinking": {"effort": "none"},
                "temperature": 0,
                "maxCompletionTokens": 800,
            }
        # HCX v3 uses camelCase. ``max_tokens`` is ignored and can truncate
        # the JSON response before its cited_chunk_ids array is complete.
        return {"model": model, "messages": [{"role":"user","content":prompt}], "temperature":0, "maxTokens":800}


class NativeStructuredOutputPromptBuilder(PromptBuilder):
    """HCX-007 Structured Outputs 전용 prompt/payload builder.

    P27-D 실험에서만 사용한다. 응답의 의미·인용 적합성은 API schema로 보장되지
    않으므로, 기존의 엄격 parser와 citation validator를 그대로 뒤에 둔다.
    """

    response_schema = {
        "type": "object",
        "properties": {
            "answer": {"type": "string"},
            "cited_chunk_ids": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
        },
        "required": ["answer", "cited_chunk_ids"],
    }

    def payload(self, question, contexts, model):
        if model.upper() != "HCX-007":
            raise ValueError("Native Structured Outputs는 HCX-007에서만 사용할 수 있습니다.")
        prompt = self.build(question, contexts)
        # 공식 Structured Outputs 예시는 ``thinking.effort=none``을 함께 보낸다.
        # 이는 추론을 활성화하는 값이 아니라 비활성화 값이며, 생략하면 현재 HCX-007
        # endpoint가 responseFormat을 400으로 거절한다. Native SO와 actual thinking은
        # 결합하지 않는다.
        return {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "maxCompletionTokens": 800,
            "thinking": {"effort": "none"},
            "responseFormat": {"type": "json", "schema": self.response_schema},
        }
