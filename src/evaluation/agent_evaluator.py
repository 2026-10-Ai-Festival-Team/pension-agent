"""Evaluate the evidence-aware Agent API without using an LLM."""
from __future__ import annotations
import statistics
import time


def percentile(values, fraction):
    return statistics.quantiles(values, n=100, method="inclusive")[int(fraction * 100) - 1] if len(values) > 1 else (values[0] if values else 0.0)


def evaluate_agent(client, questions):
    rows = []
    for question in questions:
        started = time.perf_counter()
        response = client.get("/answer", params={"question_id": question.question_id, "question": question.question, "top_k": 10})
        elapsed = (time.perf_counter() - started) * 1000
        row = {"question_id": question.question_id, "answerable": question.answerable, "status_code": response.status_code, "elapsed_ms": round(elapsed, 3)}
        if response.status_code != 200:
            row["failure_stage"] = "api_failure"; rows.append(row); continue
        body = response.json(); trace = body["think_trace"]
        returned_ids = trace["retrieved_chunk_ids"]
        retrieval_failure = question.answerable and not (set(returned_ids) & question.direct_evidence_ids)
        citation_valid = all(chunk_id in body["answer"] for chunk_id in returned_ids) if trace["generator_called"] else True
        row.update({"intent": trace["query_type"], "retrieved_count": len(returned_ids), "evidence_sufficient": trace["evidence_sufficient"], "evidence_reason": trace["assessment_reason"], "generator_called": trace["generator_called"], "citation_valid": citation_valid, "failure_stage": "retrieval_failure" if retrieval_failure else "evidence_rejection" if not trace["evidence_sufficient"] else "citation_failure" if not citation_valid else "generation_failure" if not trace["generator_called"] else "success"})
        rows.append(row)
    return rows


def summarize_agent(rows):
    answerable = [row for row in rows if row["answerable"]]
    return {"api_success_rate": sum(row["status_code"] == 200 for row in rows) / len(rows), "generator_invocation_rate": sum(row.get("generator_called", False) for row in rows) / len(rows), "evidence_rejection_rate": sum(row.get("failure_stage") == "evidence_rejection" for row in rows) / len(rows), "unsupported_handling": sum(not row["answerable"] and not row.get("generator_called", False) for row in rows), "citation_validity": sum(row.get("citation_valid", False) for row in rows if row.get("generator_called")) / max(1, sum(row.get("generator_called", False) for row in rows)), "answerable_retrieval_success": sum(row.get("failure_stage") != "retrieval_failure" for row in answerable), "mean_latency_ms": statistics.mean(row["elapsed_ms"] for row in rows), "p95_latency_ms": percentile([row["elapsed_ms"] for row in rows], .95)}
