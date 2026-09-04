"""Narrow required-fact equivalence checks for the Fresh P50 scorer."""

from scripts.run_fresh_p50_v2_final_holdout import _fact_present


def test_non_exemption_equivalence_is_negation_preserving_and_narrow():
    assert _fact_present("IRP 운용수익은 비과세가 아니라 과세이연됩니다.", "면세")
    assert not _fact_present("IRP 운용수익에 세금이 필요할 수 있습니다.", "면세")
