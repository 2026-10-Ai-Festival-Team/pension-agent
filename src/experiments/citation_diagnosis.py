"""P8-A에서 generation prompt의 citation identifier 표현만 바꾼다."""
from __future__ import annotations

import hashlib
import re

from src.generation.prompt_builder import PromptBuilder


class CitationDiagnosisPromptBuilder(PromptBuilder):
    """동일 evidence text로 identifier representation을 분리 비교한다."""

    def __init__(self, variant: str, selection) -> None:
        self.variant = variant
        self.selection = selection

    def build(self, question, contexts):
        requirements = "\n".join(f"- {match.slot.name}" for match in self.selection.matches)
        blocks = "\n\n".join(
            f"[EVIDENCE E{index}]\ncitation_id: {context.chunk_id}\ncontent: {context.text}"
            for index, context in enumerate(contexts, start=1)
        )
        allowed = ", ".join(context.chunk_id for context in contexts)
        if self.variant == "A_p7_current":
            return super().build(question, contexts)
        if self.variant == "B_minimal_no_other_identifier":
            contract = (
                "cited_chunk_ids에는 evidence의 citation_id 전체 문자열만 그대로 복사하세요. "
                "다른 식별자나 일부 문자열은 사용할 수 없습니다."
            )
        elif self.variant == "C_delimited_citation_id":
            blocks = "\n\n".join(
                f"[EVIDENCE E{index}]\n<CITATION_ID>{context.chunk_id}</CITATION_ID>\ncontent: {context.text}"
                for index, context in enumerate(contexts, start=1)
            )
            contract = (
                "cited_chunk_ids에는 <CITATION_ID> 태그 안의 전체 값만 그대로 복사하세요. "
                "태그 밖 문자열, 일부 문자열 또는 다른 식별자는 사용할 수 없습니다."
            )
        elif self.variant == "D_explicit_json_whitelist":
            contract = (
                "반드시 아래 JSON 형식으로 반환하세요. cited_chunk_ids 값은 허용 목록에서 한 글자도 바꾸지 않은 "
                f"전체 문자열을 사용해야 합니다. 예: {{\"answer\":\"...\",\"cited_chunk_ids\":[\"{allowed}\"]}}"
            )
        else:
            raise ValueError(f"unknown citation diagnosis variant: {self.variant}")
        return (
            "제공된 evidence만 사용해 질문에 직접 답하세요. JSON만 반환하세요: "
            '{"answer": string, "cited_chunk_ids": [string]}.\n\n'
            f"[Citation contract]\n{contract}\n\n[질문 요구 항목]\n{requirements}\n\n"
            f"[질문]\n{question}\n\n{blocks}\n\n[허용 citation_id]\n{allowed}"
        )


def prompt_identifier_exposure(prompt: str, contexts) -> dict:
    """원문을 기록하지 않고 source ID가 단독 값으로 노출되는지 점검한다."""
    source_ids = [context.source_id for context in contexts]
    chunk_ids = [context.chunk_id for context in contexts]
    return {
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        # A source ID is necessarily a prefix of this project's chunk IDs, so
        # substring presence alone is not evidence of a separately exposed ID.
        "source_id_exposed_separately": any(
            re.search(rf"(?<![A-Za-z0-9]){re.escape(value)}(?!-)", prompt) is not None
            for value in source_ids
        ),
        "literal_source_id_label_present": "source_id" in prompt,
        "all_chunk_ids_present": all(value in prompt for value in chunk_ids),
        "context_count": len(contexts),
    }
