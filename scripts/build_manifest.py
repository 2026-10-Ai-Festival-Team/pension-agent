"""Create a metadata-only manifest for the configured read-only data root."""

import csv
import hashlib
import re
import unicodedata
from pathlib import Path
from typing import Dict, Iterable

from check_data_path import get_data_root


PRODUCT_CODE_PATTERN = re.compile(r"^KR[A-Z0-9]+$")
FIELDNAMES = [
    "file_id",
    "relative_path",
    "filename",
    "extension",
    "file_size",
    "parent_folder",
    "product_code",
    "document_category",
    "parse_status",
    "notes",
]


def make_file_id(relative_path: str) -> str:
    return hashlib.sha256(relative_path.encode("utf-8")).hexdigest()[:16]


def find_product_code(path: Path) -> str:
    for part in path.parts:
        if PRODUCT_CODE_PATTERN.fullmatch(part):
            return part
    return ""


def infer_category(relative_path: Path) -> str:
    # macOS commonly exposes Korean filenames in decomposed (NFD) form.
    # Normalize only for classification; preserve the original relative path in the manifest.
    parts = {unicodedata.normalize("NFC", part) for part in relative_path.parts}
    if "투자설명서" in parts:
        return "investment_product"
    if "docs_renamed" in parts:
        return "pension_document"
    return "unknown"


def build_rows(data_root: Path) -> Iterable[Dict[str, str]]:
    for file_path in sorted(data_root.rglob("*"), key=lambda path: path.as_posix()):
        if not file_path.is_file():
            continue
        relative_path = file_path.relative_to(data_root)
        yield {
            "file_id": make_file_id(relative_path.as_posix()),
            "relative_path": relative_path.as_posix(),
            "filename": file_path.name,
            "extension": file_path.suffix.lower(),
            "file_size": str(file_path.stat().st_size),
            "parent_folder": file_path.parent.name,
            "product_code": find_product_code(relative_path),
            "document_category": infer_category(relative_path),
            "parse_status": "not_started",
            "notes": "",
        }


def write_manifest(rows: Iterable[Dict[str, str]], output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def main() -> None:
    data_root = get_data_root()
    output_path = Path("data/manifest.csv")
    count = write_manifest(build_rows(data_root), output_path)
    print(f"파일 수: {count}")
    print(f"생성 완료: {output_path}")


if __name__ == "__main__":
    main()
