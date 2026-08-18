from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.api.main import build_service
from src.config import get_settings
from src.retrieval.bm25_retriever import BM25Retriever


def gold_ids(item: dict) -> list[str]:
    return list(dict.fromkeys(evidence["document_id"] for evidence in item.get("required_evidence", []) if evidence.get("document_id")))


def main() -> int:
    eval_path = ROOT / "eval" / "eval_questions.json"
    if not eval_path.exists():
        print("eval_questions.json이 없습니다. 실제 대회 문서 기반 30문항이 먼저 필요합니다.")
        return 2
    questions = json.loads(eval_path.read_text("utf-8"))
    service = build_service()
    retriever = BM25Retriever.from_jsonl(get_settings().index_path)
    rows = []
    hits = Counter()
    reciprocal_ranks = []
    behavior_pairs = Counter()
    category_stats = defaultdict(lambda: Counter(total=0))
    for item in questions:
        result = service.answer(item["id"], item["question"])
        trace = json.loads(result.think_trace)
        predicted = trace["action"].upper()
        expected = item["expected_behavior"].upper()
        gold = gold_ids(item)
        ranked = retriever.retrieve(item["question"], 10)
        ranked_ids = [entry.document_id for entry in ranked]
        first_rank = next((index for index, doc_id in enumerate(ranked_ids, 1) if doc_id in gold), None)
        reciprocal_ranks.append(1 / first_rank if first_rank else 0)
        for k in (1, 3, 5, 10):
            hit = bool(set(gold) & set(ranked_ids[:k])) if gold else False
            hits[k] += int(hit)
            category_stats[item["category"]][f"hit@{k}"] += int(hit)
        category_stats[item["category"]]["total"] += int(bool(gold))
        behavior_pairs[(expected, predicted)] += 1
        rows.append({"question_id": item["id"], "question": item["question"], "expected_behavior": expected, "predicted_behavior": predicted, "retrieved_document_ids": ranked_ids, "gold_document_ids": gold, "answer": result.answer, "retrieval_hit": bool(set(gold) & set(ranked_ids[:5]))})
    output_dir = ROOT / "eval" / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "baseline_results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf-8")
    with (output_dir / "baseline_results.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys() if rows else [])
        if rows:
            writer.writeheader()
            for row in rows:
                writer.writerow({**row, "retrieved_document_ids": json.dumps(row["retrieved_document_ids"]), "gold_document_ids": json.dumps(row["gold_document_ids"])})
    behavior_total = len(questions) or 1
    retrieval_total = sum(bool(gold_ids(item)) for item in questions) or 1
    print(json.dumps({"recall": {f"@{k}": hits[k] / retrieval_total for k in (1, 3, 5, 10)}, "mrr": sum(reciprocal_ranks) / retrieval_total, "behavior_accuracy": sum(count for (expected, predicted), count in behavior_pairs.items() if expected == predicted) / behavior_total, "confusion_matrix": {f"{expected}->{predicted}": count for (expected, predicted), count in behavior_pairs.items()}, "category": category_stats}, ensure_ascii=False, indent=2, default=dict))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
