"""P28-A 평가 전용 Planner → Writer → Verifier workflow.

P28-A1에서는 Retrieval/Gate 직후 확정한 primary-original evidence bundle을
Writer, Verifier, Repair가 모두 공유한다. 어느 단계도 새 검색 결과나 bundle
밖의 식별자를 답변 근거로 사용할 수 없다.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from src.generation.hcx import HyperClovaXGenerator
from src.generation.prompt_builder import NativeStructuredOutputPromptBuilder


@dataclass(frozen=True)
class FrozenEvidenceBundle:
    """선택된 원본 1차 근거와 허용 citation ID를 함께 동결한다."""

    contexts: tuple
    allowed_primary_original_chunk_ids: tuple[str, ...]
    requirements: tuple[str, ...]

    @classmethod
    def from_contexts(cls, contexts, requirements, policy):
        allowed = tuple(item for item in contexts if policy.is_primary_original(item))
        return cls(allowed, tuple(item.chunk_id for item in allowed), tuple(requirements))

    def __post_init__(self) -> None:
        context_ids = tuple(item.chunk_id for item in self.contexts)
        if context_ids != self.allowed_primary_original_chunk_ids:
            raise ValueError("FrozenEvidenceBundle의 context와 허용 citation ID가 일치하지 않습니다.")
        if len(set(context_ids)) != len(context_ids):
            raise ValueError("FrozenEvidenceBundle에 중복 chunk_id를 넣을 수 없습니다.")

    def validates(self, cited_chunk_ids) -> bool:
        return (
            isinstance(cited_chunk_ids, list)
            and bool(cited_chunk_ids)
            and set(cited_chunk_ids).issubset(self.allowed_primary_original_chunk_ids)
        )


class WorkflowCitationBoundaryError(ValueError):
    """workflow 단계가 frozen evidence 밖의 citation을 반환했을 때 발생한다."""

    def __init__(self, stage: str) -> None:
        super().__init__(f"{stage} citation이 frozen primary-original bundle 밖에 있습니다.")
        self.stage = stage


class _BundleBoundPromptBuilder(NativeStructuredOutputPromptBuilder):
    """현재 bundle의 citation ID만 Native Structured Output에 허용한다."""

    def payload(self, question, contexts, model):
        if not contexts:
            raise ValueError("citation enum을 만들 primary-original evidence가 없습니다.")
        payload = super().payload(question, contexts, model)
        schema = deepcopy(self.response_schema)
        schema["properties"]["cited_chunk_ids"]["items"]["enum"] = [item.chunk_id for item in contexts]
        payload["responseFormat"]["schema"] = schema
        return payload


class WorkflowWriterPromptBuilder(_BundleBoundPromptBuilder):
    def __init__(self, requirements: tuple[str, ...], repair_feedback: str | None = None):
        self.requirements, self.repair_feedback = requirements, repair_feedback

    def build(self, question, contexts):
        requirements = "\n".join(f"- {item}" for item in self.requirements)
        evidence = "\n\n".join(f"[EVIDENCE]\ncitation_id: {c.chunk_id}\ncontent: {c.text}" for c in contexts)
        feedback = f"\n[Verifier 수정 요청]\n{self.repair_feedback}\n" if self.repair_feedback else ""
        return ("제공된 evidence만 사용해 질문에 답하세요. 각 요구 항목을 빠뜨리지 마세요. "
                "수치·세율·위험등급·보수는 evidence의 다른 필드와 바꾸지 마세요. "
                "Verifier의 수정 요청은 누락을 알려 주는 용도일 뿐 새로운 금융 사실 근거가 아닙니다. "
                "JSON answer와 cited_chunk_ids만 반환하고 citation_id 전체 문자열만 인용하세요.\n"
                f"[질문]\n{question}\n[요구 항목]\n{requirements}{feedback}\n{evidence}")


class WorkflowVerifierPromptBuilder(_BundleBoundPromptBuilder):
    def __init__(self, requirements: tuple[str, ...], writer_answer: str):
        self.requirements, self.writer_answer = requirements, writer_answer

    def build(self, question, contexts):
        requirements = "\n".join(f"- {item}" for item in self.requirements)
        evidence = "\n\n".join(f"[EVIDENCE]\ncitation_id: {c.chunk_id}\ncontent: {c.text}" for c in contexts)
        return ("새 검색은 하지 말고 아래 evidence만 검토하세요. Writer 답변이 모든 요구 항목을 답하고, "
                "각 claim이 evidence에 있으며, 수치·위험등급·보수·세율 혼동이나 질문 무관 답변이 없으면 "
                "answer에 PASS를 반환하세요. 하나라도 문제면 answer에 REVISE: 뒤에 짧고 구체적인 수정 요청을 반환하세요. "
                "수정 요청에 evidence에 없는 사실·수치·상품 특성을 쓰지 마세요. cited_chunk_ids에는 검토에 사용한 "
                "citation_id만 넣으세요. Repair는 이 진단으로 새 evidence를 추가할 수 없습니다.\n"
                f"[질문]\n{question}\n[요구 항목]\n{requirements}\n[Writer 답변]\n{self.writer_answer}\n{evidence}")


@dataclass
class WorkflowResult:
    generated: object
    writer_cited_chunk_ids: list[str]
    verifier_cited_chunk_ids: list[str]
    repair_cited_chunk_ids: list[str] | None
    verifier_verdict: str
    repaired: bool
    calls: int
    verifier_diagnostic: dict | None


class SelectiveWorkflow:
    """동일 contexts만 재사용하며 retrieval을 호출하지 않는다."""
    def __init__(self, generator: HyperClovaXGenerator): self.generator = generator

    def _call(self, builder, question, contexts, analysis):
        return HyperClovaXGenerator(config=self.generator.config, transport=self.generator.transport,
            prompt_builder=builder, rate_limiter=self.generator.rate_limiter, sleeper=self.generator.sleeper,
            response_capture=self.generator.response_capture).generate(question=question, contexts=contexts, query_analysis=analysis)

    def execute(self, *, question, bundle: FrozenEvidenceBundle, analysis) -> WorkflowResult:
        contexts, requirements = list(bundle.contexts), bundle.requirements
        if not contexts:
            raise ValueError("P28 workflow는 primary-original frozen evidence가 필요합니다.")
        written = self._call(WorkflowWriterPromptBuilder(requirements), question, contexts, analysis)
        if not bundle.validates(written.cited_chunk_ids):
            raise WorkflowCitationBoundaryError("Writer")
        verified = self._call(WorkflowVerifierPromptBuilder(requirements, written.answer), question, contexts, analysis)
        if not bundle.validates(verified.cited_chunk_ids):
            raise WorkflowCitationBoundaryError("Verifier")
        verdict = verified.answer.strip()
        if verdict.upper().startswith("PASS"):
            return WorkflowResult(
                written,
                written.cited_chunk_ids,
                verified.cited_chunk_ids,
                None,
                verdict,
                False,
                2,
                verified.diagnostic,
            )
        repaired = self._call(WorkflowWriterPromptBuilder(requirements, verdict), question, contexts, analysis)
        if not bundle.validates(repaired.cited_chunk_ids):
            raise WorkflowCitationBoundaryError("Repair")
        return WorkflowResult(
            repaired,
            written.cited_chunk_ids,
            verified.cited_chunk_ids,
            repaired.cited_chunk_ids,
            verdict,
            True,
            3,
            verified.diagnostic,
        )
