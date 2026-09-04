"""Audit that the v2 export artifact and HCX runtime share one authority."""
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evaluation/fine_tuning/generator_prompt_final_v2_runtime_parity_audit_v1.json"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiments.direct_requirement_e2e import (
    DirectRequirementCitationPromptBuilder,
    RequiredFactRepairPromptBuilder,
)
from src.generation.bounded_evidence_prompt_builder import BoundedEvidencePromptBuilder
from src.generation.versioned_generator_prompt import load_generator_prompt


LEGACY_RUNTIME_BUILD_SHA256 = "e6b1171399ede7fd4a8c397ece8f64e1a51d90099499265e013faabb458a84d5"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", type=int, default=1)
    parser.add_argument("--baseline-prompt-id", default="generator_prompt_final_v1")
    parser.add_argument("--candidate-prompt-id", default="generator_prompt_final_v2")
    args = parser.parse_args()
    if args.revision < 1:
        parser.error("revision must be positive")
    global OUT
    OUT = ROOT / f"evaluation/fine_tuning/generator_prompt_final_v2_runtime_parity_audit_v{args.revision}.json"
    v1 = load_generator_prompt(args.baseline_prompt_id)
    v2 = load_generator_prompt(args.candidate_prompt_id)
    runtime_builders = (
        DirectRequirementCitationPromptBuilder,
        RequiredFactRepairPromptBuilder,
        BoundedEvidencePromptBuilder,
    )
    source_hashes = {
        builder.__name__: _sha(inspect.getsource(builder.build))
        for builder in runtime_builders
    }
    guard_parity = v1.semantic_guards == v2.semantic_guards
    input_parity = v1.runtime_input_contract == v2.runtime_input_contract
    output_parity = v1.output_contract == v2.output_contract
    v2_builder_sources_versioned = all(
        "runtime_instruction" in inspect.getsource(builder.build)
        for builder in runtime_builders
    )
    payload = {
        "experiment": f"{v2.prompt_id} runtime authority and parity audit",
        "hcx_calls": 0,
        "baseline_authority": {
            "artifact": str(v1.source_path.relative_to(ROOT)),
            "declared_prompt_sha256": v1.declared_prompt_sha256,
            "computed_prompt_sha256": v1.prompt_sha256,
            "declared_prompt_sha_matches": v1.declared_sha_matches,
            "runtime_call_site": "src/experiments/direct_requirement_e2e.py:DirectRequirementCitationPromptBuilder.build",
            "legacy_runtime_build_sha256_before_v2": LEGACY_RUNTIME_BUILD_SHA256 if v1.prompt_id == "generator_prompt_final_v1" else None,
        },
        "candidate_authority": {
            "artifact": str(v2.source_path.relative_to(ROOT)),
            "prompt_source": str(v2.source_path.relative_to(ROOT)),
            "prompt_id": v2.prompt_id,
            "declared_prompt_sha256": v2.declared_prompt_sha256,
            "computed_prompt_sha256": v2.prompt_sha256,
            "declared_prompt_sha_matches": v2.declared_sha_matches,
            "runtime_call_sites": [
                "DirectRequirementCitationPromptBuilder.build",
                "RequiredFactRepairPromptBuilder.build",
                "BoundedEvidencePromptBuilder.build",
            ],
            "runtime_builder_source_sha256": source_hashes,
        },
        "static_contract_diff": {
            "factual_contract_difference": 0 if guard_parity else 1,
            "evidence_contract_difference": 0 if guard_parity else 1,
            "outcome_contract_difference": 0 if input_parity else 1,
            "safety_contract_difference": 0 if guard_parity else 1,
            "citation_contract_difference": 0 if output_parity else 1,
            "style_change_only": bool(
                guard_parity and input_parity and output_parity and v2.style_rules
            ),
            "runtime_uses_versioned_authority": v2_builder_sources_versioned,
            "candidate_style_rules": list(v2.style_rules),
        },
    }
    static = payload["static_contract_diff"]
    payload["decision"] = "PASS" if (
        v2.declared_sha_matches
        and static["factual_contract_difference"] == 0
        and static["evidence_contract_difference"] == 0
        and static["outcome_contract_difference"] == 0
        and static["safety_contract_difference"] == 0
        and static["citation_contract_difference"] == 0
        and static["style_change_only"]
        and static["runtime_uses_versioned_authority"]
    ) else "FAIL"
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"decision": payload["decision"], "v2_sha": v2.prompt_sha256, "hcx_calls": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
