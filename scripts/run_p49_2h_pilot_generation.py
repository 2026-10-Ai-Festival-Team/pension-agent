"""Run P49-2H pilot only with explicit live-HCX authorization.

This isolated runner never touches the browser/candidate runtime. The host
attaches all requirements and provenance after the model returns structured
question/completion text.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.generation import GenerationSettings
from src.generation.hcx import UrllibTransport
from src.generation.rate_limit import GlobalMinIntervalLimiter


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
        "modifiers": {"type": "object"},
        "required_gold_facts": {"type": "array", "items": {"type": "object", "properties": {"text": {"type": "string"}, "evidence_anchors": {"type": "array", "items": {"type": "string"}}, "completion_required_terms": {"type": "array", "items": {"type": "string"}}}, "required": ["text", "evidence_anchors", "completion_required_terms"]}},
        "optional_relevant_context": {"type": "array", "items": {"type": "string"}},
        "draft_completion": {"type": "string"},
    },
    "required": ["question", "modifiers", "required_gold_facts", "optional_relevant_context", "draft_completion"],
}


def build_payload(request: dict) -> dict:
    evidence = "\n\n".join("[원본 근거]\nchunk_id: {}\n내용: {}".format(item["chunk_id"], item["text"]) for item in request["direct_evidence"])
    rules = [
        "P49-2H 학습 후보 초안을 만드세요. 원본 근거 밖의 사실·수치·상품코드·미래 예측은 만들지 마세요.",
        f"target outcome: {request['target_outcome']}",
        f"question type: {request['question_type']}",
        f"domain: {request['factual_domain']}",
        "canonical requirement template: " + json.dumps(request["requirement_template"], ensure_ascii=False),
        "field constraints: " + json.dumps(request["generation_instructions"]["field_constraints"], ensure_ascii=False),
        "supported_answer는 direct evidence의 해당 field만 사용합니다.",
        "clarification_required는 필요한 사용자 조건만 재질문하고 required_gold_facts는 빈 배열로 둡니다.",
        "bounded_answer는 근거 없는 미래/추정값은 없다고 밝히며 required_gold_facts는 빈 배열로 둡니다.",
        "총보수와 기간별 비용, 표 header와 값, DB/DC scope, 긍정·부정 polarity를 혼동하지 마세요.",
        "draft_completion은 [답변]/[근거]/[유의사항] 형식을 사용합니다.",
        evidence,
    ]
    return {"messages": [{"role": "user", "content": "\n\n".join(rules)}], "temperature": 0, "maxCompletionTokens": 1400, "thinking": {"effort": "none"}, "responseFormat": {"type": "json", "schema": RESPONSE_SCHEMA}}


def parse_body(body: str) -> dict:
    data = json.loads(body)
    result = data.get("result", {}) if isinstance(data, dict) else {}
    content = result.get("message", {}).get("content") or data.get("message", {}).get("content") or data.get("choices", [{}])[0].get("message", {}).get("content")
    if not isinstance(content, str):
        raise ValueError("missing structured response content")
    if content.strip().startswith("```"):
        content = content.strip().split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(content)


def hydrate_candidate(request: dict, model: dict) -> dict:
    outcome = request["target_outcome"]
    supported = outcome == "supported_answer"
    facts = []
    if supported:
        requirement = request["requirement_template"][0]["canonical_requirement"]
        chunk_id = request["direct_evidence"][0]["chunk_id"]
        for index, fact in enumerate(model["required_gold_facts"], start=1):
            facts.append({"fact_id": f"F{index}", "requirement": requirement, "text": fact["text"], "evidence_chunk_ids": [chunk_id], "evidence_anchors": fact["evidence_anchors"], "completion_required_terms": fact["completion_required_terms"]})
    evidence_status = "full" if supported else ("unresolved" if outcome == "clarification_required" else "none")
    return {
        "candidate_id": request["pilot_request_id"].replace("PILOT", "AUG"), "source_seed_id": request["source_seed_id"], "question_type": request["question_type"], "factual_domain": request["factual_domain"], "outcome": outcome,
        "modifiers": {**model["modifiers"], "evidence_status": evidence_status}, "question": model["question"], "requirements": request["requirement_template"], "evidence_status": evidence_status,
        "direct_evidence": request["direct_evidence"] if supported else [], "required_gold_facts": facts,
        "optional_relevant_context": model["optional_relevant_context"], "draft_completion": model["draft_completion"],
        "generation_status": "generated", "validation_status": "pending", "human_review_status": "pending", "acceptance_status": "not_accepted",
        "pilot_request_id": request["pilot_request_id"], "pool_id": request["pool_id"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Required: makes paid external HCX-007 calls.")
    parser.add_argument("--requests", type=Path, default=ROOT / "evaluation/fine_tuning/p49_2h_pilot_generation_requests_v1.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/fine_tuning/p49_2h_pilot_raw_v1.jsonl")
    parser.add_argument("--max-requests", type=int, default=84)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        parser.error("P49-2H pilot makes external HCX calls. Re-run with --execute after reviewing the prepared queue.")
    if not 1 <= args.max_requests <= 84:
        parser.error("--max-requests must be within 1..84")
    if args.output.exists() and not args.resume:
        parser.error("Output exists. Use --resume or a new output path.")
    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend.lower() != "hcx" or settings.hcx_model.upper() != "HCX-007" or not settings.hcx_api_key or not settings.hcx_base_url:
        raise RuntimeError("Pilot requires configured HCX-007, HCX_API_KEY, and HCX_BASE_URL.")
    settings = replace(settings, hcx_min_interval_seconds=max(settings.hcx_min_interval_seconds, 4.0))
    completed = {row.get("pilot_request_id") for row in read_jsonl(args.output)} if args.output.exists() else set()
    requests = [row for row in read_jsonl(args.requests) if row["pilot_request_id"] not in completed][:args.max_requests]
    limiter = GlobalMinIntervalLimiter(settings.hcx_min_interval_seconds, guard_seconds=settings.hcx_pacing_guard_seconds)
    transport = UrllibTransport()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for request in requests:
        wait = limiter.acquire()
        status, body = transport.post(settings.hcx_base_url, {"Authorization": f"Bearer {settings.hcx_api_key}", "Content-Type": "application/json"}, build_payload(request), settings.timeout_seconds)
        if status >= 400:
            raise RuntimeError(f"HCX HTTP {status} for {request['pilot_request_id']}")
        candidate = hydrate_candidate(request, parse_body(body))
        with args.output.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(candidate, ensure_ascii=False) + "\n")
        print(json.dumps({"pilot_request_id": request["pilot_request_id"], "status": "generated", "rate_limit_wait_seconds": round(wait, 3)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
