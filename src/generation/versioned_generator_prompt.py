"""Versioned authority for the generator's export and runtime prompt contract."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROMPT_DIR = ROOT / "evaluation/fine_tuning"
ACTIVE_PROMPT_ID = "generator_prompt_final_v2_1"


@dataclass(frozen=True)
class VersionedGeneratorPrompt:
    prompt_id: str
    prompt: str
    prompt_sha256: str
    declared_prompt_sha256: str
    runtime_input_contract: tuple[str, ...]
    output_contract: tuple[str, ...]
    semantic_guards: tuple[str, ...]
    style_rules: tuple[str, ...]
    runtime_style_checklist: str
    runtime_transport: dict[str, str]
    source_path: Path

    @property
    def declared_sha_matches(self) -> bool:
        return self.prompt_sha256 == self.declared_prompt_sha256

    def assert_runtime_ready(self) -> None:
        if not self.declared_sha_matches:
            raise ValueError(f"prompt SHA mismatch for {self.prompt_id}")
        if self.runtime_transport.get("response_format") != "json_answer_and_cited_chunk_ids":
            raise ValueError(f"unsupported runtime transport for {self.prompt_id}")

    def trace_fields(self) -> dict[str, str]:
        return {
            "generator_prompt_version": self.prompt_id,
            "generator_prompt_sha256": self.prompt_sha256,
        }

    def runtime_instruction(self) -> str:
        """The exact versioned contract injected before runtime-only context."""
        self.assert_runtime_ready()
        return self.prompt

    def runtime_checklist(self) -> str:
        return self.runtime_style_checklist


def _artifact_data(prompt_id: str, seen: tuple[str, ...] = ()) -> dict:
    path = PROMPT_DIR / f"{prompt_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("prompt_id") != prompt_id:
        raise ValueError(f"invalid versioned prompt artifact: {path}")
    base_id = data.get("base_prompt_id")
    if not base_id:
        return data
    if prompt_id in seen:
        raise ValueError(f"cyclic versioned prompt inheritance: {prompt_id}")
    base = _artifact_data(base_id, (*seen, prompt_id))
    expected_base_sha = data.get("base_prompt_sha256")
    base_prompt = _resolved_runtime_contract_text(base)
    actual_base_sha = hashlib.sha256(base_prompt.encode("utf-8")).hexdigest()
    if expected_base_sha != actual_base_sha:
        raise ValueError(f"base prompt SHA mismatch for {prompt_id}")
    merged = {**base, **data}
    merged["runtime_input_contract"] = base["runtime_input_contract"]
    merged["output_contract"] = base["output_contract"]
    merged["semantic_guards"] = base["semantic_guards"]
    merged["style_rules"] = [*base.get("style_rules", ()), *data.get("style_rules_append", ())]
    return merged


def _resolved_runtime_contract_text(data: dict) -> str:
    prompt = data["prompt"]
    checklist = data.get("runtime_style_checklist", "")
    return prompt if not checklist else f"{prompt}\n\n[Final style checklist]\n{checklist}"


def load_generator_prompt(prompt_id: str = ACTIVE_PROMPT_ID) -> VersionedGeneratorPrompt:
    path = PROMPT_DIR / f"{prompt_id}.json"
    data = _artifact_data(prompt_id)
    prompt = data["prompt"]
    if not isinstance(prompt, str):
        raise ValueError(f"invalid versioned prompt artifact: {path}")
    checklist = data.get("runtime_style_checklist", "")
    runtime_contract_text = _resolved_runtime_contract_text(data)
    return VersionedGeneratorPrompt(
        prompt_id=prompt_id,
        prompt=prompt,
        prompt_sha256=hashlib.sha256(runtime_contract_text.encode("utf-8")).hexdigest(),
        declared_prompt_sha256=data.get("prompt_sha256", ""),
        runtime_input_contract=tuple(data.get("runtime_input_contract", ())),
        output_contract=tuple(data.get("output_contract", ())),
        semantic_guards=tuple(data.get("semantic_guards", ())),
        style_rules=tuple(data.get("style_rules", ())),
        runtime_style_checklist=checklist,
        runtime_transport=dict(data.get("runtime_transport", {})),
        source_path=path,
    )
