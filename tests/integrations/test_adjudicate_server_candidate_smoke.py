from scripts.verify_server_candidate import SCENARIOS


def test_server_safety_trace_expects_the_explicit_safe_block_terminal_outcome():
    safety = next(item for item in SCENARIOS if item[0] == "safety")
    assert safety[-1] == "safe_block"
