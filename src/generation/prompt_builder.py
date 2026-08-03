import json
class PromptBuilder:
    def build(self, question, contexts):
        evidence="\n\n".join(f"[근거]\nchunk_id: {c.chunk_id}\n문서: {c.source_path}\n위치: {c.locator.page_start or c.locator.sheet}\n내용: {c.text}" for c in contexts)
        return f"제공된 문서 근거만 사용해 답하세요. 근거 밖 사실·수치·상품코드를 추가하지 마세요. JSON만 반환하세요: {{\"answer\": string, \"cited_chunk_ids\": [string]}}\n\n[질문]\n{question}\n\n{evidence}"

    def payload(self, question, contexts, model):
        return {"model": model, "messages": [{"role":"user","content":self.build(question,contexts)}], "temperature":0, "max_tokens":800}
