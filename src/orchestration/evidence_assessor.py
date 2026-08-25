from dataclasses import dataclass, field
from src.models.document import AuthorityLevel, SourceType
from src.models.retrieval import SearchResult
from src.orchestration.query_analyzer import QueryAnalysis


@dataclass(frozen=True)
class EvidenceAssessment:
    sufficient: bool
    reason: str
    missing_requirements: list[str] = field(default_factory=list)
    selected_chunk_ids: list[str] = field(default_factory=list)


class EvidenceAssessor:
    def assess(self, analysis: QueryAnalysis, contexts: list[SearchResult]) -> EvidenceAssessment:
        return self._assess(analysis, contexts, require_primary_original=True)

    def assess_without_provenance(
        self,
        analysis: QueryAnalysis,
        contexts: list[SearchResult],
    ) -> EvidenceAssessment:
        """P25 회귀 검증 전용: provenance 제약만 제외한 기존 gate 결과를 계산한다."""
        return self._assess(analysis, contexts, require_primary_original=False)

    def _assess(
        self,
        analysis: QueryAnalysis,
        contexts: list[SearchResult],
        *,
        require_primary_original: bool,
    ) -> EvidenceAssessment:
        if analysis.intent == "unsupported_or_personal":
            return EvidenceAssessment(False, "unsupported_or_personal_information")
        if analysis.requires_user_conditions:
            return EvidenceAssessment(False, "conditional_recommendation_requires_user_conditions", ["투자 기간", "위험 성향", "운용 목적"])
        if not contexts:
            return EvidenceAssessment(False, "no_retrieval_evidence")
        if require_primary_original and not any(
            result.source_type == SourceType.ORIGINAL
            and result.authority_level == AuthorityLevel.PRIMARY
            for result in contexts
        ):
            return EvidenceAssessment(False, "primary_original_evidence_missing")
        if analysis.product_codes and not all(any(code in result.product_codes or code in result.text.upper() for result in contexts) for code in analysis.product_codes):
            return EvidenceAssessment(False, "product_code_evidence_missing", analysis.product_codes)
        joined = "\n".join(result.text.upper() for result in contexts)
        if analysis.requires_comparison and any(entity not in joined for entity in analysis.entities):
            return EvidenceAssessment(False, "comparison_evidence_incomplete", analysis.entities)
        return EvidenceAssessment(True, "sufficient", selected_chunk_ids=[result.chunk_id for result in contexts])
