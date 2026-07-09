"""Tests for citation parsing and validation."""


from takehome.services.llm import (
    ParsedCitation,
    normalize_name,
    parse_citations,
    validate_citations,
)


class TestParseCitations:
    def test_single_citation_with_clause(self):
        text = "The rent is £850,000【Commercial Lease | Page 3, Clause 3.1】per annum."
        citations = parse_citations(text)

        assert len(citations) == 1
        assert citations[0].document_name == "Commercial Lease"
        assert citations[0].page_number == 3
        assert citations[0].clause == "3.1"

    def test_single_citation_page_only(self):
        text = "See the title register【Title Report | Page 2】for details."
        citations = parse_citations(text)

        assert len(citations) == 1
        assert citations[0].document_name == "Title Report"
        assert citations[0].page_number == 2
        assert citations[0].clause is None

    def test_multi_page_citation(self):
        text = "The rent review mechanism【Lease | Page 3, Section 1.1; Page 4, Section 3.2.1】applies."
        citations = parse_citations(text)

        assert len(citations) == 2
        assert citations[0].page_number == 3
        assert citations[0].clause == "1.1"
        assert citations[1].page_number == 4
        assert citations[1].clause == "3.2.1"
        assert citations[0].document_name == "Lease"
        assert citations[1].document_name == "Lease"

    def test_multiple_separate_citations(self):
        text = (
            "The rent is £850k【Lease | Page 3, Clause 3.1】"
            "and covenants exist【Title | Page 2】on the title."
        )
        citations = parse_citations(text)

        assert len(citations) == 2
        assert citations[0].document_name == "Lease"
        assert citations[1].document_name == "Title"

    def test_no_citations(self):
        text = "This is a plain response with no citations at all."
        citations = parse_citations(text)

        assert citations == []

    def test_citation_with_section_keyword(self):
        text = "See【Environmental Report | Page 5, Section 6.3.1】for details."
        citations = parse_citations(text)

        assert len(citations) == 1
        assert citations[0].clause == "6.3.1"

    def test_citation_with_parenthesized_clause(self):
        text = "Condition (a)【Lease | Page 7, Clause 8.3.1(a)】must be met."
        citations = parse_citations(text)

        assert len(citations) == 1
        assert citations[0].clause == "8.3.1(a)"


class TestNormalizeName:
    def test_strips_special_characters(self):
        assert normalize_name("Commercial Lease — 100 Bishopsgate") == "commerciallease100bishopsgate"

    def test_strips_hyphens_and_underscores(self):
        assert normalize_name("commercial-lease-100-bishopsgate") == "commerciallease100bishopsgate"

    def test_matching_different_formats(self):
        llm_name = "Commercial Lease — 100 Bishopsgate"
        file_name = "commercial-lease-100-bishopsgate"
        assert normalize_name(llm_name) == normalize_name(file_name)


class TestValidateCitations:
    def _make_doc(self, doc_id: str, filename: str, page_count: int):
        class FakeDoc:
            pass
        d = FakeDoc()
        d.id = doc_id
        d.filename = filename
        d.page_count = page_count
        return d

    def _make_page(self, doc_id: str, page_num: int, content: str):
        class FakePage:
            pass
        p = FakePage()
        p.document_id = doc_id
        p.page_number = page_num
        p.content = content
        return p

    def test_verified_citation(self):
        docs = [self._make_doc("d1", "commercial-lease.pdf", 10)]
        pages = [self._make_page("d1", 3, "Section 3.1 The tenant shall pay rent quarterly")]
        citations = [ParsedCitation(document_name="commercial-lease", page_number=3, clause="3.1")]

        result = validate_citations(citations, docs, pages)

        assert result[0].status == "verified"

    def test_partial_citation_clause_not_on_page(self):
        docs = [self._make_doc("d1", "lease.pdf", 10)]
        pages = [self._make_page("d1", 3, "This page discusses rent payment schedules")]
        citations = [ParsedCitation(document_name="lease", page_number=3, clause="9.9")]

        result = validate_citations(citations, docs, pages)

        assert result[0].status == "partial"

    def test_unverified_citation_page_out_of_range(self):
        docs = [self._make_doc("d1", "lease.pdf", 5)]
        pages = []
        citations = [ParsedCitation(document_name="lease", page_number=15, clause=None)]

        result = validate_citations(citations, docs, pages)

        assert result[0].status == "unverified"

    def test_dropped_citation_unknown_document(self):
        docs = [self._make_doc("d1", "lease.pdf", 10)]
        pages = []
        citations = [ParsedCitation(document_name="nonexistent-document", page_number=1, clause=None)]

        result = validate_citations(citations, docs, pages)

        assert result[0].status == "dropped"

    def test_fuzzy_name_matching(self):
        docs = [self._make_doc("d1", "commercial-lease-100-bishopsgate.pdf", 10)]
        pages = [self._make_page("d1", 4, "Clause 3.2 rent review mechanism")]
        citations = [ParsedCitation(
            document_name="Commercial Lease — 100 Bishopsgate",
            page_number=4,
            clause="3.2",
        )]

        result = validate_citations(citations, docs, pages)

        assert result[0].status == "verified"
