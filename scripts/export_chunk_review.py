"""Create a deterministic, Git-ignored CSV for representative chunk review."""
import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path


def load_chunks(path):
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def select_review_chunks(chunks):
    selected = {}
    def add(chunk, reason):
        item = selected.setdefault(chunk["chunk_id"], {**chunk, "review_reason": []})
        item["review_reason"].append(reason)
    for chunk in chunks:
        if len(chunk["text"]) > 1500: add(chunk, "over_1500_chars")
        if len(chunk["text"]) < 100: add(chunk, "under_100_chars")
    groups = defaultdict(list)
    for chunk in chunks: groups[f"{chunk['source_format']}:{chunk['chunk_type']}"] .append(chunk)
    rng = random.Random(42)
    for key, group in groups.items():
        short = [chunk for chunk in group if 100 <= len(chunk["text"]) < 500]
        for chunk in rng.sample(short, min(10, len(short))): add(chunk, f"short_sample:{key}")
        for chunk in rng.sample(group, min(5, len(group))): add(chunk, f"general_sample:{key}")
    products = [chunk for chunk in chunks if chunk.get("product_codes")]
    for chunk in rng.sample(products, min(20, len(products))): add(chunk, "product_sample")
    return [{**chunk, "review_reason": ", ".join(chunk["review_reason"])} for chunk in selected.values()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/parsed/representative_chunks.jsonl")
    parser.add_argument("--output", default="data/diagnostics/chunk_review.csv")
    args = parser.parse_args()
    reviewed = select_review_chunks(load_chunks(Path(args.input)))
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["chunk_id", "source_path", "source_format", "chunk_type", "title", "section", "locator", "character_count", "element_ids", "product_codes", "review_reason", "review_status", "issue_type", "review_note", "text"]
    with output.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields); writer.writeheader()
        for chunk in reviewed:
            writer.writerow({"chunk_id": chunk["chunk_id"], "source_path": chunk["source_path"], "source_format": chunk["source_format"], "chunk_type": chunk["chunk_type"], "title": chunk.get("title"), "section": chunk.get("section"), "locator": json.dumps(chunk["locator"], ensure_ascii=False), "character_count": len(chunk["text"]), "element_ids": json.dumps(chunk["element_ids"], ensure_ascii=False), "product_codes": json.dumps(chunk.get("product_codes", []), ensure_ascii=False), "review_reason": chunk["review_reason"], "review_status": "", "issue_type": "", "review_note": "", "text": chunk["text"]})
    print(f"검토 대상: {len(reviewed)}개\n출력: {output}")


if __name__ == "__main__": main()
