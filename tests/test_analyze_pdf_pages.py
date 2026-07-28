from scripts.analyze_pdf_pages import (
    _coverage_ratio,
    _parse_manual_candidates,
    _parse_manual_notes,
    _union_area,
    classify_ocr_candidate,
)


def test_union_area_avoids_double_counting_overlap() -> None:
    assert _union_area([(0, 0, 2, 2), (1, 1, 3, 3)]) == 7


def test_coverage_ratio_clips_to_page_bounds() -> None:
    assert _coverage_ratio([(-1, -1, 5, 5)], 4, 4) == 1.0


def test_high_coverage_page_without_native_text_is_candidate() -> None:
    assert classify_ocr_candidate(0, 1, 0.8, False, 0.35) == (
        True,
        "no_native_text_high_image_coverage",
    )


def test_likely_cover_and_no_image_pages_are_not_candidates() -> None:
    assert classify_ocr_candidate(0, 1, 0.8, True, 0.35) == (
        False,
        "likely_cover_page",
    )
    assert classify_ocr_candidate(0, 0, 0.0, False, 0.35) == (
        False,
        "no_native_text_without_embedded_image",
    )


def test_manual_candidate_parser_preserves_unicode_path() -> None:
    assert _parse_manual_candidates(["docs_renamed/문서.pdf:2"]) == [
        ("docs_renamed/문서.pdf", 2)
    ]


def test_manual_note_parser_preserves_note() -> None:
    assert _parse_manual_notes(["docs_renamed/doc.pdf:이미지 기반 본문"]) == [
        ("docs_renamed/doc.pdf", "이미지 기반 본문")
    ]
