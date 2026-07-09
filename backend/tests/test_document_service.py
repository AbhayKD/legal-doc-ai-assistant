"""Tests for document processing logic."""


from takehome.services.retrieval import _tokenize, PageCandidate, _assemble_context


class TestTokenize:
    def test_basic_tokenization(self):
        tokens = _tokenize("The tenant shall pay rent")
        assert tokens == ["the", "tenant", "shall", "pay", "rent"]

    def test_strips_punctuation(self):
        tokens = _tokenize("Section 3.1: rent-review mechanism (upward only)")
        assert "section" in tokens
        assert "rent" in tokens
        assert "review" in tokens
        assert "mechanism" in tokens

    def test_lowercases(self):
        tokens = _tokenize("LANDLORD and TENANT")
        assert tokens == ["landlord", "and", "tenant"]

    def test_empty_string(self):
        assert _tokenize("") == []


class TestAssembleContext:
    def test_formats_pages_with_metadata(self):
        pages = [
            PageCandidate(
                document_id="d1",
                document_name="Lease",
                page_number=3,
                content="Rent is £850,000 per annum",
            ),
            PageCandidate(
                document_id="d2",
                document_name="Title Report",
                page_number=1,
                content="Title number LN782451",
            ),
        ]
        context = _assemble_context(pages)

        assert '<page document="Lease" page="3">' in context
        assert '<page document="Title Report" page="1">' in context
        assert "Rent is £850,000 per annum" in context
        assert "Title number LN782451" in context

    def test_empty_pages(self):
        assert _assemble_context([]) == ""
