from src.llm.hyperclova import HyperClovaClient


def test_merge_stream_supports_deltas():
    assert HyperClovaClient._merge_stream("안녕", "하세요") == "안녕하세요"


def test_merge_stream_deduplicates_cumulative_and_final_events():
    assert HyperClovaClient._merge_stream("안녕", "안녕하세요") == "안녕하세요"
    assert HyperClovaClient._merge_stream("안녕하세요", "안녕하세요") == "안녕하세요"
