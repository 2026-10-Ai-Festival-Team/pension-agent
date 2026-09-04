"""Structured-output prompt for answers with an explicit evidence boundary."""

from __future__ import annotations

from collections.abc import Iterable

from src.generation.prompt_builder import NativeStructuredOutputPromptBuilder
from src.generation.versioned_generator_prompt import VersionedGeneratorPrompt, load_generator_prompt


class BoundedEvidencePromptBuilder(NativeStructuredOutputPromptBuilder):
    """Ask HCX to answer only verified units and disclose the rest.

    The caller supplies requirement labels only after a deterministic matcher
    bound every supported label to a primary-original chunk.  The model cannot
    turn a partial match into a full answer: unavailable labels are explicit in
    the prompt and the usual citation whitelist remains in force.
    """

    def __init__(
        self,
        *,
        supported_requirements: Iterable[str],
        unsupported_requirements: Iterable[str],
        prompt_contract: VersionedGeneratorPrompt | None = None,
    ) -> None:
        self.supported_requirements = tuple(supported_requirements)
        self.unsupported_requirements = tuple(unsupported_requirements)
        self.prompt_contract = prompt_contract or load_generator_prompt()

    def build(self, question, contexts):
        allowed = ", ".join(context.chunk_id for context in contexts)
        evidence = "\n\n".join(
            f"[EVIDENCE]\ncitation_id: {context.chunk_id}\ncontent: {context.text}"
            for context in contexts
        )
        supported = "\n".join(f"- {label}" for label in self.supported_requirements) or "- 없음"
        unsupported = "\n".join(f"- {label}" for label in self.unsupported_requirements) or "- 없음"
        return (
            f"{self.prompt_contract.runtime_instruction()}\n\n"
            "질문의 일부만 직접 근거가 확인됐습니다. "
            "[확인 불가 항목]의 값·조건·미래 결과를 추측하거나 일반 지식으로 보완하지 마세요. "
            "답변 첫 부분에서 해당 항목은 제공된 자료로 확인할 수 없다고 짧게 밝히고, "
            "[확인 가능한 항목]은 evidence에 있는 사실을 빠뜨리지 말고 답하세요. "
            "질문하지 않은 인접 field는 추가하지 마세요. JSON 객체만 반환하세요: "
            '{"answer": string, "cited_chunk_ids": [string]}. cited_chunk_ids에는 실제 사용한 '
            "아래 허용 citation_id를 하나 이상 원문 그대로 넣으세요.\n\n"
            f"[확인 가능한 항목]\n{supported}\n\n"
            f"[확인 불가 항목]\n{unsupported}\n\n"
            f"[질문]\n{question}\n\n{evidence}\n\n[허용 citation_id]\n{allowed}"
        )
