"""Tests for confidence scoring logic."""


from takehome.services.retrieval import _compute_confidence, PageCandidate


def _page(score: float = 0.0) -> PageCandidate:
    p = PageCandidate(
        document_id="d1",
        document_name="Doc",
        page_number=1,
        content="content",
    )
    p.bm25_score = score
    return p


class TestComputeConfidence:
    def test_high_confidence(self):
        relevant = [_page(), _page(), _page()]  # 3 pages selected
        bm25_top = [_page(3.5), _page(2.1)]  # top score > 2.0
        assert _compute_confidence(relevant, bm25_top) == "high"

    def test_medium_confidence_few_pages(self):
        relevant = [_page(), _page()]  # 2 pages (< 3)
        bm25_top = [_page(2.5)]  # top score > 2.0 but fewer pages
        assert _compute_confidence(relevant, bm25_top) == "medium"

    def test_medium_confidence_low_bm25(self):
        relevant = [_page(), _page(), _page()]  # 3 pages
        bm25_top = [_page(1.5)]  # top score > 1.0 but < 2.0
        assert _compute_confidence(relevant, bm25_top) == "medium"

    def test_low_confidence_no_pages(self):
        relevant = []  # no pages selected
        bm25_top = [_page(0.5)]
        assert _compute_confidence(relevant, bm25_top) == "low"

    def test_low_confidence_weak_bm25(self):
        relevant = [_page()]
        bm25_top = [_page(0.3)]  # top score < 1.0
        assert _compute_confidence(relevant, bm25_top) == "low"

    def test_low_confidence_empty_bm25(self):
        relevant = []
        bm25_top = []
        assert _compute_confidence(relevant, bm25_top) == "low"

    def test_boundary_high(self):
        relevant = [_page(), _page(), _page()]  # exactly 3
        bm25_top = [_page(2.01)]  # just above 2.0
        assert _compute_confidence(relevant, bm25_top) == "high"

    def test_boundary_medium(self):
        relevant = [_page()]  # exactly 1
        bm25_top = [_page(1.01)]  # just above 1.0
        assert _compute_confidence(relevant, bm25_top) == "medium"
