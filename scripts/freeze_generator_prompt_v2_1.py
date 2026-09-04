"""Freeze the candidate v2.1 runtime prompt after its v3 regression GO."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.generation.versioned_generator_prompt import load_generator_prompt


PROMPT_ARTIFACT = ROOT / "evaluation/fine_tuning/generator_prompt_final_v2_1.json"
PARITY = ROOT / "evaluation/fine_tuning/generator_prompt_final_v2_runtime_parity_audit_v6.json"
STYLE_SMOKE = ROOT / "evaluation/generator_prompt_v2_style_smoke_v6.json"
REGRESSION = ROOT / "evaluation/fresh_p50_v2_regression_execution_v6.json"
OUTPUT = ROOT / "evaluation/fine_tuning/generator_prompt_final_v2_1_freeze_manifest_v1.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("v2.1 freeze manifest already exists; frozen authority is immutable")
    prompt = load_generator_prompt("generator_prompt_final_v2_1")
    parity = json.loads(PARITY.read_text(encoding="utf-8"))
    style = json.loads(STYLE_SMOKE.read_text(encoding="utf-8"))
    regression = json.loads(REGRESSION.read_text(encoding="utf-8"))
    if not prompt.declared_sha_matches:
        raise RuntimeError("candidate prompt SHA does not match its declared authority")
    if parity.get("decision") != "PASS":
        raise RuntimeError("runtime/artifact parity is not PASS")
    if style.get("decision") != "PASS":
        raise RuntimeError("targeted v2.1 style smoke is not GO")
    if regression.get("gate", {}).get("decision") != "GO" or regression.get("summary", {}).get("pass_count") != 50:
        raise RuntimeError("v3 regression is not 50/50 GO")

    artifact = {
        "artifact": "generator_prompt_final_v2_1 freeze manifest",
        "version": 1,
        "decision": "FROZEN_GO",
        "prompt": {
            "id": prompt.prompt_id,
            "runtime_prompt_sha256": prompt.prompt_sha256,
            "declared_prompt_sha256": prompt.declared_prompt_sha256,
            "artifact": str(PROMPT_ARTIFACT.relative_to(ROOT)),
            "artifact_sha256": _sha(PROMPT_ARTIFACT),
        },
        "evidence": {
            "runtime_artifact_parity": {"path": str(PARITY.relative_to(ROOT)), "sha256": _sha(PARITY)},
            "targeted_style_smoke": {"path": str(STYLE_SMOKE.relative_to(ROOT)), "sha256": _sha(STYLE_SMOKE)},
            "p50_v3_regression": {"path": str(REGRESSION.relative_to(ROOT)), "sha256": _sha(REGRESSION)},
        },
        "frozen_contract": [
            "style-only v2.1 supported-answer structure",
            "factual/evidence/outcome/safety/citation contract unchanged from v2",
            "host-owned evidence-scoped completeness contract",
        ],
        "immutable_after_freeze": [
            "generator prompt artifact", "runtime prompt resolution", "semantic guards", "output contract",
        ],
        "next_unlocked_phase": "Fresh P50 v4 static preflight and one E2E execution",
    }
    OUTPUT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"decision": artifact["decision"], "prompt_sha256": prompt.prompt_sha256, "output": str(OUTPUT.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
