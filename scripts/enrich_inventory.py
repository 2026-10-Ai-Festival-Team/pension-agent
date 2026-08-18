from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "data" / "metadata" / "document_inventory.csv"
INDEX = ROOT / "data" / "processed" / "chunks.jsonl"


def classify(file_name: str, text: str) -> tuple[str, str]:
    if file_name.startswith("R2_") or "투자설명서" in text[:800]:
        return "product_prospectus", "product"
    if any(term in text for term in ("세액공제", "과세", "세금", "소득세")):
        return "tax", "tax"
    if any(term in text for term in ("신청방법", "신청서", "입금", "이전제도", "직접청구")):
        return "procedure", "procedure"
    if any(term in text for term in ("퇴직연금", "IRP", "연금저축", "디폴트옵션")):
        return "institution", "pension"
    return "other", "other"


def product_name(text: str) -> str:
    patterns = (r"집합투자기구 명칭\s+(.+?)(?=\s+2\.\s*집합투자업자)", r"투자설명서는\s+(.+?)에 대한")
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip()[:300]
    return ""


def main() -> None:
    texts = defaultdict(str)
    with INDEX.open(encoding="utf-8") as handle:
        for line in handle:
            chunk = json.loads(line)
            if len(texts[chunk["document_id"]]) < 3000:
                texts[chunk["document_id"]] += " " + chunk["text"]
    with INVENTORY.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fields = list(rows[0]) if rows else []
    for row in rows:
        text = texts[row["document_id"]]
        row["document_type"], row["topic"] = classify(row["file_name"], text)
        row["product_name"] = product_name(text) if row["document_type"] == "product_prospectus" else ""
        date = re.search(r"(?:작성\s*기준일|기준일)\s*[:：]?\s*(20\d{2})[년.\-/ ]+(\d{1,2})[월.\-/ ]+(\d{1,2})", text)
        row["effective_date"] = f"{date.group(1)}-{int(date.group(2)):02d}-{int(date.group(3)):02d}" if date else ""
        row["notes"] = "자동 분류·상품명·기준일은 원문 표본 검수 필요"
    with INVENTORY.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    counts = {kind: sum(row["document_type"] == kind for row in rows) for kind in sorted({row["document_type"] for row in rows})}
    print(f"enriched={len(rows)} types={counts}")


if __name__ == "__main__":
    main()
