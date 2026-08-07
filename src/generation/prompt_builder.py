import json
class PromptBuilder:
    def build(self, question, contexts):
        evidence="\n\n".join(f"[근거]\nchunk_id: {c.chunk_id}\n문서: {c.source_path}\n위치: {c.locator.page_start or c.locator.sheet}\n내용: {c.text}" for c in contexts)
        allowed_chunk_ids = ", ".join(c.chunk_id for c in contexts)
        return f"제공된 문서 근거만 사용해 답하세요. 근거 밖 사실·수치·상품코드를 추가하지 마세요. JSON만 반환하세요: {{\"answer\": string, \"cited_chunk_ids\": [string]}}. cited_chunk_ids에는 반드시 아래 허용 chunk_id 중 답변에 사용한 하나 이상을 한 글자도 바꾸지 않고 복사하세요. 허용 목록 밖의 ID, 문서명, 페이지 번호를 인용으로 쓰면 안 됩니다.\n\n[허용 chunk_id]\n{allowed_chunk_ids}\n\n[질문]\n{question}\n\n{evidence}"

    def payload(self, question, contexts, model):
        # HCX v3 uses camelCase. ``max_tokens`` is ignored and can truncate
        # the JSON response before its cited_chunk_ids array is complete.
        return {"model": model, "messages": [{"role":"user","content":self.build(question,contexts)}], "temperature":0, "maxTokens":800}
