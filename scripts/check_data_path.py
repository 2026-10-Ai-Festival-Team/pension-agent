"""Check that the configured company data root is available without changing it."""

import os
from pathlib import Path

from dotenv import load_dotenv


def get_data_root() -> Path:
    """Return the configured data root, or raise a clear configuration error."""
    load_dotenv()
    data_root_value = os.getenv("PENSION_DATA_ROOT")
    if not data_root_value:
        raise RuntimeError("PENSION_DATA_ROOT 환경변수가 없습니다. .env를 설정하세요.")

    data_root = Path(data_root_value).expanduser()
    if not data_root.is_dir():
        raise FileNotFoundError(f"데이터 경로를 찾을 수 없습니다: {data_root}")
    return data_root


def main() -> None:
    data_root = get_data_root()
    files = [path for path in data_root.rglob("*") if path.is_file()]

    print(f"데이터 루트: {data_root}")
    print(f"전체 파일 수: {len(files)}")
    for path in files[:20]:
        print(path.relative_to(data_root))


if __name__ == "__main__":
    main()
