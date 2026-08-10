"""Create a reviewer packet from one HCX E2E run; no LLM scoring is performed."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.answer_quality import build_review_packet, summarize_review_packet
from src.evaluation.retrieval_dataset import load_questions


parser = argparse.ArgumentParser()
parser.add_argument("--run", type=Path, required=True)
parser.add_argument("--questions", type=Path, default=ROOT / "evaluation/retrieval_questions.jsonl")
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--summary", type=Path, required=True)
args = parser.parse_args()

run_bytes = args.run.read_bytes()
run = json.loads(run_bytes)
packet = build_review_packet(run["rows"], load_questions(args.questions), hashlib.sha256(run_bytes).hexdigest())
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in packet), encoding="utf-8")
args.summary.write_text(json.dumps(summarize_review_packet(packet), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summarize_review_packet(packet), ensure_ascii=False))
