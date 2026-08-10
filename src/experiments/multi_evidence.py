"""P5용 requirement-aware context 선택기.

이 모듈은 BM25 결과를 다시 검색하거나 금융 사실을 보충하지 않는다. 평가
케이스가 질문에서 정의한 요구 슬롯을 기준으로, 이미 반환된 Top-k 안에서만
근거를 선택한다. 슬롯을 모두 채우지 못하면 호출자가 생성기를 호출하지 않아야
한다.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable

from src.generation.prompt_builder import PromptBuilder
from src.models.retrieval import SearchResult


@dataclass(frozen=True)
class RequirementSlot:
    """질문이 요구하는 하나의 답변 항목과 그 항목을 찾을 문자열 조건."""

    name: str
    terms: tuple[str, ...]
    min_matches: int = 1


@dataclass(frozen=True)
class RequirementCase:
    question_id: str
    role: str
    slots: tuple[RequirementSlot, ...]
    generation_enabled: bool = True
    semantic_equivalent_allowed: bool = False


@dataclass(frozen=True)
class SlotMatch:
    slot: RequirementSlot
    result: SearchResult | None
    matched_terms: tuple[str, ...]

    @property
    def covered(self) -> bool:
        return self.result is not None


@dataclass(frozen=True)
class EvidenceSelection:
    case: RequirementCase
    matches: tuple[SlotMatch, ...]
    contexts: tuple[SearchResult, ...]

    @property
    def complete(self) -> bool:
        return all(match.covered for match in self.matches)

    @property
    def missing_slot_names(self) -> list[str]:
        return [match.slot.name for match in self.matches if not match.covered]


class RequirementEvidenceSelector:
    """Top-k 내 lexical coverage로 requirement별 근거를 결정적으로 고른다."""

    @staticmethod
    def _matched_terms(slot: RequirementSlot, result: SearchResult) -> tuple[str, ...]:
        # PDF table rendering may insert a newline inside a phrase such as
        # ``운용\n손익``. Collapse whitespace without changing original context text.
        searchable = " ".join(
            " ".join(part.split()) for part in (result.title or "", result.section or "", result.text) if part
        ).casefold()
        return tuple(term for term in slot.terms if term.casefold() in searchable)

    def select(self, case: RequirementCase, results: Iterable[SearchResult]) -> EvidenceSelection:
        candidates = tuple(results)
        matches: list[SlotMatch] = []
        ordered_contexts: list[SearchResult] = []
        seen: set[str] = set()
        for slot in case.slots:
            scored = []
            for result in candidates:
                terms = self._matched_terms(slot, result)
                if len(terms) >= slot.min_matches:
                    # Match count is primary; original BM25 order remains the tie breaker.
                    scored.append((len(terms), result.score, -result.rank, result, terms))
            if not scored:
                matches.append(SlotMatch(slot, None, ()))
                continue
            _, _, _, selected, terms = max(scored, key=lambda item: item[:3])
            matches.append(SlotMatch(slot, selected, terms))
            if selected.chunk_id not in seen:
                ordered_contexts.append(selected)
                seen.add(selected.chunk_id)
        return EvidenceSelection(case, tuple(matches), tuple(ordered_contexts))


def load_requirement_cases(path: Path) -> list[RequirementCase]:
    """버전 관리되는 실험 슬롯 정의를 읽는다."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        RequirementCase(
            question_id=item["question_id"],
            role=item["role"],
            generation_enabled=item.get("generation_enabled", True),
            semantic_equivalent_allowed=item.get("semantic_equivalent_allowed", False),
            slots=tuple(
                RequirementSlot(
                    name=slot["name"],
                    terms=tuple(slot["terms"]),
                    min_matches=slot.get("min_matches", 1),
                )
                for slot in item["slots"]
            ),
        )
        for item in raw["cases"]
    ]


class RequirementAwarePromptBuilder(PromptBuilder):
    """기존 citation 계약 위에 요구 항목과 해당 근거를 명시한다."""

    def __init__(self, selection: EvidenceSelection) -> None:
        self.selection = selection

    def build(self, question, contexts):
        requirement_lines = []
        for match in self.selection.matches:
            if match.result is not None:
                requirement_lines.append(f"- {match.slot.name}: {match.result.chunk_id}")
        requirements = "\n".join(requirement_lines)
        base = super().build(question, contexts)
        return (
            "아래 [질문 요구 항목]을 각각 빠뜨리지 말고 답하세요. 각 항목은 괄호의 "
            "chunk_id 근거만 사용하세요. 근거가 항목을 뒷받침하지 않으면 추정하지 마세요.\n\n"
            f"[질문 요구 항목]\n{requirements}\n\n{base}"
        )


class CitationBindingPromptBuilder(PromptBuilder):
    """P6-A: citation_id 외의 식별자를 generation prompt에서 숨긴다."""

    def __init__(self, selection: EvidenceSelection) -> None:
        self.selection = selection

    def build(self, question, contexts):
        requirements = "\n".join(f"- {match.slot.name}" for match in self.selection.matches)
        evidence = "\n\n".join(
            "\n".join(
                (
                    f"[EVIDENCE E{position}]",
                    f"citation_id: {context.chunk_id}",
                    f"document: {context.source_path}",
                    f"location: {context.locator.page_start or context.locator.sheet or 'unknown'}",
                    f"content: {context.text}",
                )
            )
            for position, context in enumerate(contexts, start=1)
        )
        return (
            "제공된 evidence만 사용해 질문에 답하세요. JSON만 반환하세요: "
            '{"answer": string, "cited_chunk_ids": [string]}.\n\n'
            "[Citation binding]\n"
            "cited_chunk_ids에는 아래 evidence의 citation_id 값을 한 글자도 바꾸지 않고 그대로 복사하세요. "
            "citation_id가 아닌 문서명, 경로, 위치, source_id 또는 새 식별자는 절대 사용하지 마세요. "
            "answer가 비어 있지 않다면 citation_id를 하나 이상 넣어야 합니다.\n\n"
            f"[질문 요구 항목]\n{requirements}\n\n[질문]\n{question}\n\n{evidence}"
        )


def selection_record(selection: EvidenceSelection) -> dict:
    """비밀정보나 HCX 응답 원문 없이 선택 근거를 JSON으로 남긴다."""
    return {
        "requirement_evidence_complete": selection.complete,
        "missing_requirement_slots": selection.missing_slot_names,
        "selected_chunk_ids": [context.chunk_id for context in selection.contexts],
        "slot_matches": [
            {
                "slot": match.slot.name,
                "terms": list(match.slot.terms),
                "min_matches": match.slot.min_matches,
                "chunk_id": match.result.chunk_id if match.result else None,
                "rank": match.result.rank if match.result else None,
                "matched_terms": list(match.matched_terms),
            }
            for match in selection.matches
        ],
    }
