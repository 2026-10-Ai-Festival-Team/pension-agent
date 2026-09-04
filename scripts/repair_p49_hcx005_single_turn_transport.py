"""Repair only CLOVA single-turn T_ID transport metadata for P49 v2."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT / "evaluation/fine_tuning/p49_hcx005_training_export_ncp_transport_v1.csv"
V2 = ROOT / "evaluation/fine_tuning/p49_hcx005_training_export_ncp_transport_v2.csv"
MANIFEST = ROOT / "evaluation/fine_tuning/p49_hcx005_training_export_ncp_transport_manifest_v2.json"
COLUMNS = ["System_Prompt", "C_ID", "T_ID", "Text", "Completion"]
PAYLOAD_COLUMNS = ["System_Prompt", "Text", "Completion"]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read(path: Path) -> list[dict[str, str]]:
    raw = path.read_bytes()
    if not raw.startswith(b"\xef\xbb\xbf"):
        raise RuntimeError(f"UTF-8 BOM missing: {path.name}")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != COLUMNS:
            raise RuntimeError(f"column order drift: {path.name}")
        rows = list(reader)
    if any(set(row) != set(COLUMNS) or any(row[column] == "" for column in COLUMNS) for row in rows):
        raise RuntimeError(f"blank/invalid row: {path.name}")
    return rows


def payload_hash(rows: list[dict[str, str]]) -> str:
    return sha("".join(json.dumps({key: row[key] for key in PAYLOAD_COLUMNS}, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows).encode("utf-8"))


def audit(rows: list[dict[str, str]]) -> dict:
    c_ids = [int(row["C_ID"]) for row in rows]
    t_ids = [int(row["T_ID"]) for row in rows]
    pairs = [(row["C_ID"], row["T_ID"]) for row in rows]
    per_c = Counter(row["C_ID"] for row in rows)
    return {
        "rows": len(rows), "column_order": COLUMNS, "utf8_bom": True,
        "c_id_min": min(c_ids), "c_id_max": max(c_ids), "c_id_unique_count": len(set(c_ids)),
        "t_id_min": min(t_ids), "t_id_max": max(t_ids), "t_id_unique_values": sorted(set(t_ids)),
        "each_c_id_row_count": sorted(set(per_c.values())),
        "blank_c_id_or_t_id": sum(not row["C_ID"] or not row["T_ID"] for row in rows),
        "duplicate_c_id_t_id": len(pairs) - len(set(pairs)),
    }


def write_once(path: Path, content: bytes) -> str:
    expected = sha(content)
    if path.exists():
        if sha(path.read_bytes()) != expected:
            raise RuntimeError(f"immutable artifact collision: {path.name}")
    else:
        path.write_bytes(content)
    return expected


def main() -> None:
    v1 = read(V1)
    before = audit(v1)
    repaired = [{**row, "C_ID": str(index), "T_ID": "0"} for index, row in enumerate(v1)]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=COLUMNS)
    writer.writeheader(); writer.writerows(repaired)
    v2_hash = write_once(V2, stream.getvalue().encode("utf-8-sig"))
    persisted = read(V2)
    after = audit(persisted)
    fields_same = {
        field: sum(left[field] != right[field] for left, right in zip(v1, persisted))
        for field in PAYLOAD_COLUMNS
    }
    if not (
        len(v1) == len(persisted) == 600
        and payload_hash(v1) == payload_hash(persisted)
        and after["c_id_min"] == 0 and after["c_id_max"] == 599 and after["c_id_unique_count"] == 600
        and after["t_id_unique_values"] == [0] and after["each_c_id_row_count"] == [1]
        and after["blank_c_id_or_t_id"] == after["duplicate_c_id_t_id"] == 0
        and not any(fields_same.values())
    ):
        raise RuntimeError("single-turn transport repair audit failed")
    manifest = {
        "stage": "P49 HCX-005 single-turn T_ID transport repair",
        "failure_preserved": {"task_id": "5s8pic1g", "reason": "file.format", "message": "Invalid dataset: t_id"},
        "source_transport": V1.name, "source_transport_sha256": sha(V1.read_bytes()), "source_audit": before,
        "repaired_transport": V2.name, "repaired_transport_sha256": v2_hash, "repaired_audit": after,
        "metadata_only_changes": ["T_ID"], "model_visible_payload_sha256": payload_hash(v1),
        "system_prompt_changed": fields_same["System_Prompt"], "text_changed": fields_same["Text"],
        "completion_changed": fields_same["Completion"], "transport_repair_go": True,
    }
    write_once(MANIFEST, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"transport_repair_go": True, "source_audit": before, "repaired_audit": after, "v2_sha256": v2_hash}, ensure_ascii=False))


if __name__ == "__main__":
    main()
