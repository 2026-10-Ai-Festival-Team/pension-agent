"""Validate and summarize completed manual answer-quality labels."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.answer_quality import load_completed_reviews, summarize_review_packet


parser = argparse.ArgumentParser()
parser.add_argument("--run", type=Path, required=True)
parser.add_argument("--reviews", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()

run_sha256 = hashlib.sha256(args.run.read_bytes()).hexdigest()
reviews = load_completed_reviews(args.reviews, run_sha256)
args.output.write_text(json.dumps(summarize_review_packet(reviews), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
