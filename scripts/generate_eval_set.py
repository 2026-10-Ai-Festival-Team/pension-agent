from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    inventory = ROOT / "data" / "metadata" / "document_inventory.csv"
    index = ROOT / "data" / "processed" / "chunks.jsonl"
    if not inventory.exists() or not index.exists() or index.stat().st_size == 0:
        print("실제 문서 inventory/index가 필요합니다. 임의의 금융 정답은 생성하지 않습니다.")
        return 2
    print("평가문제는 실제 문서 근거를 검토해 작성해야 합니다. eval/SCHEMA.md를 참고하세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
