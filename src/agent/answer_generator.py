from __future__ import annotations

from src.agent.prompts import ANSWER_SYSTEM_PROMPT
from src.llm.hyperclova import HyperClovaClient, HyperClovaError
from src.schemas.models import AnswerMode, QuestionAnalysis


class AnswerGenerator:
    def __init__(self, client: HyperClovaClient | None):
        self.client = client

    def generate(self, question: str, context: str, mode: AnswerMode, analysis: QuestionAnalysis) -> str:
        if mode == AnswerMode.CLARIFY:
            missing = ", ".join(analysis.missing_information) or "계좌 유형, 투자 기간, 위험 감내 수준"
            return f"적절한 안내를 위해 다음 정보를 먼저 알려주세요: {missing}."
        if mode == AnswerMode.ABSTAIN:
            return "제공된 대회 자료에서 이 질문에 답할 충분한 근거를 찾지 못했습니다. 확인 가능한 자료나 조건을 추가해 주세요."
        if not self.client or not self.client.configured:
            return "근거 문서는 찾았지만 HyperCLOVA X가 설정되지 않아 답변을 생성할 수 없습니다."
        prompt = f"QUESTION:\n{question}\n\nCONTEXT:\n{context}"
        try:
            return self.client.chat(ANSWER_SYSTEM_PROMPT, prompt, max_tokens=1024, temperature=0.1)
        except HyperClovaError:
            return "근거 문서는 찾았지만 HyperCLOVA X 호출에 실패했습니다. 잠시 후 다시 시도해 주세요."
