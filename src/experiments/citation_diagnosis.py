"""P8-A에서 generation prompt의 citation identifier 표현만 바꾼다."""
from __future__ import annotations

import hashlib
import re

from src.generation.prompt_builder import NativeStructuredOutputPromptBuilder, PromptBuilder


class CitationDiagnosisPromptBuilder(PromptBuilder):
    """동일 evidence text로 identifier representation을 분리 비교한다."""

    def __init__(self, variant: str, selection) -> None:
        self.variant = variant
        self.selection = selection

    @staticmethod
    def _slot_instruction(slot) -> str:
        """필드별 값의 의미 경계를 Writer에게 명시한다.

        이는 추출 규칙이 아니라 prompt 내 답변 계약이다. 비용 예시를 연간 보수로
        바꾸거나 판매수수료를 총보수로 읽는 식의 column confusion을 막되, evidence
        밖의 값을 새로 만들지는 않는다.
        """
        key = slot.key or ""
        if key.endswith(":total_fee"):
            return "연간 총보수·비용의 백분율만 답하고, 판매수수료나 기간별 비용 예시와 바꾸지 마세요."
        if key.endswith(":example_cost"):
            return "질문에서 요청한 투자기간 열의 비용 예시만 답하고, 연간 총보수나 다른 기간 열과 바꾸지 마세요."
        if key.endswith(":other_expenses"):
            return "기타비용은 총보수·비용 및 기간별 비용 예시와 별도 항목으로 설명하세요."
        if key.endswith(":risk_grade"):
            return "위험등급 숫자와 등급명을 함께 확인하고, 원금보장 여부와 같은 의미로 취급하지 마세요."
        if key.endswith(":principal_loss_possible") or key.endswith(":principal_guarantee_status"):
            return "원금손실 가능성과 원금보장 여부를 위험등급과 분리해 evidence 문구대로 설명하세요."
        if key.endswith(":investment_strategy") or key.endswith(":investment_target"):
            return "투자전략·비중은 evidence에 있는 자산과 비율을 그대로 설명하세요."
        if key in {"db_benefit", "dc_benefit"}:
            return "DB와 DC의 급여 산정 기준을 서로 바꾸지 말고 각각 설명하세요."
        if key == "irp_eligibility":
            return "가입 가능한 사람을 문서에 나온 범주별로 구분해 설명하고, 한두 사례만 들어 답을 축소하지 마세요."
        if key == "dc_withdrawal_conditions":
            return "DC 중도인출은 법정 사유가 있을 때만 가능하다는 점과, evidence에 있는 대표 사유를 구분해 설명하세요."
        if key == "withdrawal_procedure":
            return (
                "증빙서류는 사유별로 달라질 수 있음을 먼저 밝히되, '서류가 필요하다'고만 답하지 마세요. "
                "반드시 중도인출신청서를 적고, evidence가 주택구입 사유를 설명하면 주민등록등본·건물등기사항증명서·"
                "지방세 세목별 과세증명서 및 매매·분양계약서처럼 evidence에 직접 나온 대표 서류를 함께 제시하세요."
            )
        if key == "isa_transfer_tax_timing":
            return "ISA 전환금의 추가 세액공제와 인출·과세 처리를 서로 섞지 말고, evidence가 말하는 원금·과세 시점을 구분해 설명하세요."
        return "이 항목을 evidence에 있는 표현과 수치 범위 안에서 빠짐없이 답하세요."

    def build(self, question, contexts):
        requirements = "\n".join(
            f"- {match.slot.name}: {self._slot_instruction(match.slot)}"
            for match in self.selection.matches
        )
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
        multi_requirement_contract = ""
        if len(self.selection.matches) >= 2:
            multi_requirement_contract = (
                "\n[Coverage contract]\n"
                "질문 요구 항목이 둘 이상이면 각 항목의 값·조건을 각각 답하세요. "
                "비교·동일 여부 질문에 예/아니오만 쓰고 끝내지 말고, 비교되는 값과 차이를 evidence에 있는 "
                "표현·수치로 함께 설명하세요. evidence가 항목을 명시하면 '명시되어 있지 않다'고 바꾸지 마세요.\n"
            )
        return (
            "제공된 evidence만 사용해 질문에 직접 답하세요. 질문이 여러 사실·조건을 물으면 각 항목을 빠뜨리지 말고 "
            "첫 문장에 결론을 제시한 뒤 항목별로 설명하세요. evidence에 없는 세부사항은 만들지 말고, 사유별로 달라지는 "
            "사항은 그 범위를 분명히 밝히세요. JSON만 반환하세요: "
            '{"answer": string, "cited_chunk_ids": [string]}.\n\n'
            f"[Citation contract]\n{contract}{multi_requirement_contract}\n[질문 요구 항목]\n{requirements}\n\n"
            f"[질문]\n{question}\n\n{blocks}\n\n[허용 citation_id]\n{allowed}"
        )


class NativeStructuredCitationPromptBuilder(CitationDiagnosisPromptBuilder):
    """Minimal citation prompt에 HCX-007 native JSON schema만 추가한다."""

    response_schema = NativeStructuredOutputPromptBuilder.response_schema

    def payload(self, question, contexts, model):
        return NativeStructuredOutputPromptBuilder.payload(self, question, contexts, model)


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
