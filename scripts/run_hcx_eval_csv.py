from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from src.api.main import build_service
from src.config import get_settings


FIELDNAMES = [
    "question_id",
    "category",
    "subcategory",
    "difficulty",
    "question_type",
    "expected_behavior",
    "predicted_behavior",
    "question",
    "answer",
    "retrieved_context",
    "used_document_ids",
    "search_queries",
    "think_trace",
    "elapsed_seconds",
    "status",
    "error",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="eval_questions.csv를 HyperCLOVA X RAG pipeline으로 실행합니다."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "eval" / "eval_questions.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "eval" / "results" / "hcx_answers.csv",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=0.3)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="기존 결과를 지우고 처음부터 실행합니다.",
    )
    return parser.parse_args()


def completed_ids(output: Path) -> set[str]:
    if not output.exists() or output.stat().st_size == 0:
        return set()
    with output.open(encoding="utf-8-sig", newline="") as handle:
        return {
            row["question_id"]
            for row in csv.DictReader(handle)
            if row.get("question_id") and row.get("status") == "ok"
        }


def main() -> int:
    args = parse_args()
    settings = get_settings()
    if not settings.hcx_api_key:
        print("HCX_API_KEY를 .env에 설정하세요.", file=sys.stderr)
        return 2
    if not args.input.exists():
        print(f"입력 파일이 없습니다: {args.input}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.overwrite and args.output.exists():
        args.output.unlink()

    done = completed_ids(args.output)
    with args.input.open(encoding="utf-8-sig", newline="") as handle:
        questions = list(csv.DictReader(handle))
    pending = [row for row in questions if row["id"] not in done]
    if args.limit is not None:
        pending = pending[: max(args.limit, 0)]

    service = build_service()
    needs_header = not args.output.exists() or args.output.stat().st_size == 0
    print(
        f"total={len(questions)} completed={len(done)} pending={len(pending)} "
        f"output={args.output}"
    )

    with args.output.open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        if needs_header:
            writer.writeheader()
            handle.flush()

        for index, row in enumerate(pending, 1):
            started = time.monotonic()
            output_row = {
                "question_id": row["id"],
                "category": row["category"],
                "subcategory": row["subcategory"],
                "difficulty": row["difficulty"],
                "question_type": row["question_type"],
                "expected_behavior": row["expected_behavior"].upper(),
                "question": row["question"],
                "status": "error",
                "error": "",
            }
            try:
                result = service.answer(row["id"], row["question"])
                trace = json.loads(result.think_trace)
                output_row.update(
                    {
                        "predicted_behavior": str(trace.get("action", "")).upper(),
                        "answer": result.answer,
                        "retrieved_context": result.retrieved_context,
                        "used_document_ids": json.dumps(
                            trace.get("used_documents", []), ensure_ascii=False
                        ),
                        "search_queries": json.dumps(
                            trace.get("search_queries", []), ensure_ascii=False
                        ),
                        "think_trace": result.think_trace,
                        "status": "ok",
                    }
                )
            except Exception as exc:  # 다음 문항은 계속 처리하고 오류 행을 남긴다.
                output_row["error"] = f"{type(exc).__name__}: {exc}"
            output_row["elapsed_seconds"] = round(time.monotonic() - started, 3)
            writer.writerow(output_row)
            handle.flush()
            print(
                f"[{index}/{len(pending)}] {row['id']} "
                f"status={output_row['status']} "
                f"elapsed={output_row['elapsed_seconds']}s"
            )
            if args.delay > 0 and index < len(pending):
                time.sleep(args.delay)

    print(f"saved={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
