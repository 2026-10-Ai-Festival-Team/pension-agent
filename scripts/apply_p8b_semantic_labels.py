"""HCX 재호출 없이 P8-B raw run에 수동 semantic labels를 결합한다."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, default=ROOT / "data/diagnostics/p8b_compound_citation_stability.json")
    parser.add_argument("--labels", type=Path, default=ROOT / "evaluation/p8b_manual_semantic_labels.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/diagnostics/p8b_compound_citation_stability_reviewed.json")
    args = parser.parse_args()
    payload = json.loads(args.run.read_text(encoding="utf-8"))
    labels = json.loads(args.labels.read_text(encoding="utf-8"))["labels"]
    lookup = {(item["question_id"], item["representation"]): item for item in labels}
    for row in payload["rows"]:
        label = lookup.get((row["question_id"], row.get("representation")))
        if label:
            row.update({key: value for key, value in label.items() if key not in {"question_id", "representation"}})
    payload["semantic_labels_source"] = str(args.labels.relative_to(ROOT))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"rows": len(payload["rows"]), "labeled_rows": sum(row.get("semantic_correctness") not in {None, "pending_manual_review", "not_applicable"} for row in payload["rows"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
