"""P34-A attribution must stay bound to the frozen pre-HCX artifact."""
from __future__ import annotations

from scripts import attribute_p34_pre_hcx as attribution


def test_p34_attribution_covers_the_pre_hcx_failure_sets() -> None:
    assert len(attribution.PLANNER_ATTRIBUTION) == 7
    assert len(attribution.SOURCE_RELEVANCE) == 8
    assert set(attribution.PLANNER_ATTRIBUTION) == {
        "P34-001", "P34-002", "P34-003", "P34-008", "P34-012", "P34-014", "P34-018",
    }
    assert {item["status"] for item in attribution.SOURCE_RELEVANCE.values()} == {
        "semantic_equivalent", "partial", "wrong_scope",
    }
