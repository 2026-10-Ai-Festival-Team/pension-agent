"""Evaluate the evidence-aware Agent API without using an LLM."""
from __future__ import annotations
import statistics
import time


def percentile(values, fraction):
    return statistics.quantiles(values, n=100, method="inclusive")[int(fraction * 100) - 1] if len(values) > 1 else (values[0] if values else 0.0)


def evaluate_agent(client, questions, request_delay_seconds=0):
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
        direct_ids = question.direct_evidence_ids
        all_relevant_ids = getattr(question, "all_relevant_ids", direct_ids)
        evidence_requirement = getattr(question, "evidence_requirement", "any")
        retrieved_id_set = set(returned_ids)
        cited_ids = trace.get("cited_chunk_ids", [])
        cited_documents = trace.get("cited_documents", [])
        # User-facing answers deliberately must not expose runtime identifiers.
        # The trace binds citations to selected chunks; presentation may use a
        # verified DOC ID or, when no DOC authority exists, the original source
        # filename. A document-level source citation is valid when the source
        # format has no page/slide/sheet locator.
        def valid_citation_document(item):
            if not isinstance(item, dict):
                return False
            if not isinstance(item.get("source_id"), str) or not isinstance(item.get("source_path"), str):
                return False
            if not isinstance(item.get("source_filename"), str) or not item["source_filename"]:
                return False
            if item.get("citation_scope") not in {"document_location", "document"}:
                return False
            document_id = item.get("document_id")
            if document_id is not None and (not isinstance(document_id, str) or not document_id.startswith("DOC-")):
                return False
            identity = document_id or item["source_filename"]
            if identity not in body["answer"] or item["source_id"] in body["answer"]:
                return False
            if item["citation_scope"] == "document_location":
                locator = item.get("locator")
                return isinstance(locator, dict) and len(locator) == 1 and next(iter(locator)) in {"page", "slide", "sheet"}
            return "locator" not in item

        citation_valid = (
            bool(cited_ids)
            and set(cited_ids).issubset(returned_ids)
            and not any(chunk_id in body["answer"] for chunk_id in cited_ids)
            and bool(cited_documents)
            and all(valid_citation_document(item) for item in cited_documents)
        ) if trace["generator_called"] else True
        diagnostic = trace.get("generation_diagnostic") or {}
        row.update({"intent": trace["query_type"], "route": trace.get("route"), "route_reasons": trace.get("route_reasons", []), "extracted_entities": trace.get("extracted_entities"), "requirement_plan": trace.get("requirement_plan"), "base_retrieved_chunk_ids": trace.get("base_retrieved_chunk_ids", []), "candidate_chunk_ids": trace.get("candidate_chunk_ids", []), "selected_merged_evidence_ids": trace.get("selected_merged_evidence_ids", []), "missing_requirement_slots": trace.get("missing_requirement_slots", []), "answer": body["answer"], "retrieved_context": body["retrieved_context"], "retrieved_count": len(returned_ids), "retrieved_chunk_ids": returned_ids, "direct_evidence_ids": sorted(direct_ids), "all_relevant_ids": sorted(all_relevant_ids), "direct_evidence_hit_at_10": bool(retrieved_id_set & direct_ids) if question.answerable else None, "all_relevant_evidence_hit_at_10": bool(all_relevant_ids.issubset(retrieved_id_set)) if question.answerable and evidence_requirement == "all" else None, "unlabeled_retrieved_chunk_count": len(retrieved_id_set - all_relevant_ids) if question.answerable else None, "evidence_sufficient": trace["evidence_sufficient"], "evidence_reason": trace["assessment_reason"], "generator_attempted": trace.get("generator_attempted", False), "generator_called": trace["generator_called"], "citation_valid": citation_valid, "cited_chunk_ids": cited_ids, "cited_documents": cited_documents, "generation_model": trace.get("generation_model"), "generation_latency_ms": trace.get("generation_latency_ms"), "generation_finish_reason": trace.get("generation_finish_reason"), "generation_usage": trace.get("generation_usage"), "generation_error": trace.get("generation_error"), "generation_diagnostic": diagnostic, "generation_attempt_history": diagnostic.get("attempt_history", []), "failure_stage": "retrieval_failure" if retrieval_failure else "evidence_rejection" if not trace["evidence_sufficient"] else "citation_failure" if not citation_valid else "generation_failure" if not trace["generator_called"] else "success"})
        rows.append(row)
        if request_delay_seconds:
            time.sleep(request_delay_seconds)
    return rows


def summarize_agent(rows):
    answerable = [row for row in rows if row["answerable"]]
    return {"api_success_rate": sum(row["status_code"] == 200 for row in rows) / len(rows), "generator_invocation_rate": sum(row.get("generator_called", False) for row in rows) / len(rows), "evidence_rejection_rate": sum(row.get("failure_stage") == "evidence_rejection" for row in rows) / len(rows), "unsupported_handling": sum(not row["answerable"] and not row.get("generator_called", False) for row in rows), "citation_validity": sum(row.get("citation_valid", False) for row in rows if row.get("generator_called")) / max(1, sum(row.get("generator_called", False) for row in rows)), "answerable_retrieval_success": sum(row.get("failure_stage") != "retrieval_failure" for row in answerable), "mean_latency_ms": statistics.mean(row["elapsed_ms"] for row in rows), "p95_latency_ms": percentile([row["elapsed_ms"] for row in rows], .95)}
