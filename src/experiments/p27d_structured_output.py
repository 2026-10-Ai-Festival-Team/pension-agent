"""P27-D native Structured Outputs A/B 전용 shadow composition."""

from __future__ import annotations

from src.experiments.citation_diagnosis import NativeStructuredCitationPromptBuilder
from src.experiments.p26_candidate_agent import P26CandidateAgent
from src.generation.hcx import HyperClovaXGenerator


class P27DStructuredOutputAgent(P26CandidateAgent):
    """Compound 경로도 minimal citation + native JSON schema를 함께 사용한다."""

    def _compound_generator(self, selection):
        if not isinstance(self.generator, HyperClovaXGenerator):
            return self.generator
        return HyperClovaXGenerator(
            config=self.generator.config,
            transport=self.generator.transport,
            prompt_builder=NativeStructuredCitationPromptBuilder(
                "B_minimal_no_other_identifier", selection
            ),
            rate_limiter=self.generator.rate_limiter,
            sleeper=self.generator.sleeper,
            response_capture=self.generator.response_capture,
        )
