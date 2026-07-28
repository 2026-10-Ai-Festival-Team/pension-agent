"""Print one PDF parse as JSON for manual source-location inspection."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.pdf_parser import PdfParser
from src.ingestion.docx_parser import DocxParser
from src.ingestion.pptx_parser import PptxParser


def main() -> None:
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("--file", required=True)
    argument_parser.add_argument("--source-root", default="data/raw/연금")
    args = argument_parser.parse_args()

    source_root = Path(args.source_root).resolve()
    file_path = Path(args.file).resolve()
    parsers = {".pdf": PdfParser(), ".docx": DocxParser(), ".pptx": PptxParser()}
    try:
        parser = parsers[file_path.suffix.lower()]
    except KeyError as exc:
        supported = ", ".join(sorted(parsers))
        raise ValueError(f"unsupported file extension: {file_path.suffix} ({supported})") from exc
    result = parser.parse(file_path, source_root)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
