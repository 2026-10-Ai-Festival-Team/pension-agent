"""P12 고정 Router/Gate를 전체 40문항에 대해 offline 평가한다."""
from __future__ import annotations

import sys
from pathlib import Path

from evaluate_p11_shadow_offline import main


ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    sys.argv[1:1] = [
        "--experiment-name",
        "P12 shadow offline routing/gate",
        "--output",
        str(ROOT / "data/diagnostics/p12_shadow_offline.json"),
        "--requirements",
        str(ROOT / "evaluation/p12_requirement_cases.json"),
    ]
    main()
