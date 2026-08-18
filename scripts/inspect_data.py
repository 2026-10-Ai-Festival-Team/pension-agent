from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.config import get_settings
from src.ingestion.loader import discover_documents, load_document

COLUMNS = ["document_id", "file_name", "document_type", "topic", "subtopic", "product_name", "effective_date", "page_count", "contains_table", "contains_numeric_data", "notes"]


def main() -> int:
    settings = get_settings()
    paths = discover_documents(settings.raw_data_dir)
    output = ROOT / "data" / "metadata" / "document_inventory.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for path in paths:
        document = load_document(path, settings.raw_data_dir)
        full_text = "\n".join(page.text for page in document.pages)
        rows.append({"document_id": document.document_id, "file_name": str(path.relative_to(settings.raw_data_dir)), "document_type": "unclassified", "topic": "", "subtopic": "", "product_name": "", "effective_date": "", "page_count": len(document.pages), "contains_table": document.contains_table, "contains_numeric_data": bool(re.search(r"\d", full_text)), "notes": "분류 및 표 파싱 품질 수동 검토 필요"})
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"documents={len(rows)} inventory={output}")
    if not rows:
        print("대회 원본 자료가 없습니다. data/raw에 자료를 추가한 뒤 다시 실행하세요.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
