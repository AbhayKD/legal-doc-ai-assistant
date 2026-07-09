"""Citation parsing and validation.

Extracts structured citations from LLM responses and validates them
against actual document content to catch hallucinations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from takehome.db.models import Document, DocumentPage

CITATION_BLOCK_PATTERN = re.compile(r"【([^】]+)】")
PAGE_REF_PATTERN = re.compile(
    r"Page\s+(\d+)(?:\s*,\s*(?:Clause|Section)\s+([\w.()]+))?"
)


@dataclass
class ParsedCitation:
    document_name: str
    page_number: int
    clause: str | None
    status: str = "verified"


def normalize_name(name: str) -> str:
    """Normalize a document name for fuzzy matching."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def parse_citations(response: str) -> list[ParsedCitation]:
    """Extract structured citations from LLM response text.

    Handles both single and multi-page citations:
    - 【Doc | Page 3, Clause 8.1】
    - 【Doc | Page 3, Section 1.1; Page 4, Section 3.2.1】
    """
    citations: list[ParsedCitation] = []
    for block_match in CITATION_BLOCK_PATTERN.finditer(response):
        block = block_match.group(1)
        parts = block.split("|", 1)
        if len(parts) != 2:
            continue
        doc_name = parts[0].strip()
        refs_text = parts[1].strip()

        for page_match in PAGE_REF_PATTERN.finditer(refs_text):
            citations.append(
                ParsedCitation(
                    document_name=doc_name,
                    page_number=int(page_match.group(1)),
                    clause=page_match.group(2),
                )
            )
    return citations


def validate_citations(
    citations: list[ParsedCitation],
    documents: list[Document],
    pages: list[DocumentPage],
) -> list[ParsedCitation]:
    """Validate each citation against actual documents and pages.

    Sets status to: verified, partial, unverified, or dropped.
    """
    doc_name_map: dict[str, Document] = {}
    for doc in documents:
        name_without_ext = doc.filename.replace(".pdf", "").replace(".PDF", "")
        doc_name_map[normalize_name(name_without_ext)] = doc

    page_content_map: dict[tuple[str, int], str] = {}
    for page in pages:
        page_content_map[(page.document_id, page.page_number)] = page.content

    validated: list[ParsedCitation] = []
    for citation in citations:
        normalized = normalize_name(citation.document_name)

        # Find matching document (fuzzy)
        matched_doc: Document | None = None
        for key, doc in doc_name_map.items():
            if normalized in key or key in normalized:
                matched_doc = doc
                break

        if not matched_doc:
            citation.status = "dropped"
            validated.append(citation)
            continue

        if citation.page_number > matched_doc.page_count or citation.page_number < 1:
            citation.status = "unverified"
            validated.append(citation)
            continue

        # Check if clause exists anywhere in the document (validates it's not hallucinated)
        if citation.clause:
            clause_ref = citation.clause.strip()
            base_clause = clause_ref.split("(")[0]  # "8.3.1(a)" → "8.3.1"

            found = False
            for (doc_id, _pg), page_text in page_content_map.items():
                if doc_id != matched_doc.id:
                    continue
                page_text_normalized = " ".join(page_text.split())
                if (
                    clause_ref in page_text_normalized
                    or f"Section {clause_ref}" in page_text_normalized
                    or f"Clause {clause_ref}" in page_text_normalized
                    or f"clause {clause_ref}" in page_text_normalized
                    or base_clause in page_text_normalized
                ):
                    found = True
                    break

            citation.status = "verified" if found else "partial"
        else:
            citation.status = "verified"

        validated.append(citation)

    return validated
