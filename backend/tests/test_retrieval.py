"""Tests for the BM25 retrieval pipeline."""


from takehome.services.retrieval import BM25Index, PageCandidate


def _make_page(doc_name: str, page: int, content: str) -> PageCandidate:
    return PageCandidate(
        document_id=f"doc-{doc_name}",
        document_name=doc_name,
        page_number=page,
        content=content,
    )


class TestBM25Index:
    def test_scores_relevant_page_higher(self):
        pages = [
            _make_page("Lease", 1, "This lease is between the landlord and tenant"),
            _make_page("Lease", 7, "The tenant may break the lease by giving twelve months notice"),
            _make_page("Environmental", 3, "Phase I environmental site assessment contamination"),
        ]
        index = BM25Index(pages)
        results = index.score("break clause notice", top_n=3)

        assert results[0].page_number == 7
        assert results[0].document_name == "Lease"

    def test_returns_top_n_results(self):
        pages = [_make_page("Doc", i, f"page {i} content about topic {i}") for i in range(1, 25)]
        index = BM25Index(pages)
        results = index.score("topic", top_n=5)

        assert len(results) == 5

    def test_empty_corpus(self):
        index = BM25Index([])
        results = index.score("anything", top_n=10)

        assert results == []

    def test_query_with_no_matching_terms(self):
        pages = [
            _make_page("Lease", 1, "rent payment quarterly landlord"),
            _make_page("Lease", 2, "repair maintenance obligation tenant"),
        ]
        index = BM25Index(pages)
        results = index.score("xylophone zebra", top_n=2)

        assert len(results) == 2
        assert all(p.bm25_score == 0.0 for p in results)

    def test_cross_document_scoring(self):
        pages = [
            _make_page("Lease", 5, "The annual rent is eight hundred thousand pounds"),
            _make_page("Title", 2, "Restrictive covenant no industrial use"),
            _make_page("Environmental", 4, "Risk of soil contamination from former industrial use"),
        ]
        index = BM25Index(pages)
        results = index.score("industrial use restriction", top_n=3)

        names = [r.document_name for r in results[:2]]
        assert "Title" in names
        assert "Environmental" in names
