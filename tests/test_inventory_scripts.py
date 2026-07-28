"""Unit tests for metadata-only inventory behavior."""

import csv
import importlib.util
import tempfile
import unittest
import unicodedata
from pathlib import Path


SCRIPTS = Path(__file__).parents[1] / "scripts"


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


class InventoryScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys
        sys.path.insert(0, str(SCRIPTS))
        cls.manifest = load_script("build_manifest")
        cls.inventory = load_script("analyze_inventory")

    def test_manifest_rows_keep_only_relative_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file_path = root / "투자설명서" / "KR123ABC" / "fund.PDF"
            file_path.parent.mkdir(parents=True)
            file_path.write_bytes(b"test")
            rows = list(self.manifest.build_rows(root))
        self.assertEqual(rows[0]["relative_path"], "투자설명서/KR123ABC/fund.PDF")
        self.assertEqual(rows[0]["product_code"], "KR123ABC")
        self.assertEqual(rows[0]["document_category"], "investment_product")
        self.assertEqual(rows[0]["extension"], ".pdf")

    def test_empty_manifest_writes_header(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "manifest.csv"
            count = self.manifest.write_manifest([], output)
            with output.open(encoding="utf-8-sig", newline="") as file:
                header = next(csv.reader(file))
        self.assertEqual(count, 0)
        self.assertEqual(header, self.manifest.FIELDNAMES)

    def test_category_handles_decomposed_korean_folder_names(self):
        decomposed = unicodedata.normalize("NFD", "투자설명서")
        self.assertEqual(
            self.manifest.infer_category(Path(decomposed) / "KR123ABC" / "fund.pdf"),
            "investment_product",
        )

    def test_representative_selection_does_not_repeat_a_file(self):
        rows = [
            {"file_id": str(index), "relative_path": f"docs_renamed/{index}.{extension}", "filename": f"{index}.{extension}", "extension": f".{extension}", "file_size": str(index), "product_code": "", "document_category": "pension_document"}
            for index, extension in enumerate(["pdf", "pdf", "pdf", "pdf", "pdf", "docx", "docx", "pptx"], start=1)
        ]
        samples = self.inventory.select_representative_documents(rows)
        self.assertEqual(len({sample["file_id"] for sample in samples}), len(samples))
        self.assertEqual(len(samples), 8)

    def test_representative_selection_includes_both_xlsx_candidates(self):
        rows = [
            {"file_id": str(index), "relative_path": f"docs_renamed/{index}.{extension}", "filename": f"{index}.{extension}", "extension": f".{extension}", "file_size": str(index), "product_code": "", "document_category": "pension_document"}
            for index, extension in enumerate(["pdf"] * 5 + ["docx"] * 2 + ["pptx", "xlsx", "xlsx"], start=1)
        ]
        samples = self.inventory.select_representative_documents(rows)
        self.assertEqual(len(samples), 10)
        self.assertEqual(sum(sample["sample_role"] == "xlsx_candidate" for sample in samples), 2)

    def test_representative_selection_has_twelve_rows_when_products_exist(self):
        rows = [
            {"file_id": str(index), "relative_path": f"docs_renamed/{index}.{extension}", "filename": f"{index}.{extension}", "extension": f".{extension}", "file_size": str(index), "product_code": "", "document_category": "pension_document"}
            for index, extension in enumerate(["pdf"] * 5 + ["docx"] * 2 + ["pptx", "xlsx", "xlsx"], start=1)
        ]
        rows.extend([
            {"file_id": "product-1", "relative_path": "투자설명서/KR123ABC/a.pdf", "filename": "a.pdf", "extension": ".pdf", "file_size": "100", "product_code": "KR123ABC", "document_category": "investment_product"},
            {"file_id": "product-2", "relative_path": "투자설명서/KR456DEF/b.pdf", "filename": "b.pdf", "extension": ".pdf", "file_size": "101", "product_code": "KR456DEF", "document_category": "investment_product"},
        ])
        samples = self.inventory.select_representative_documents(rows)
        self.assertEqual(len(samples), 12)
        self.assertEqual(sum(sample["sample_role"] == "investment_product_candidate" for sample in samples), 2)


if __name__ == "__main__":
    unittest.main()
