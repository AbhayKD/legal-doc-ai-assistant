from __future__ import annotations

import re
from collections.abc import AsyncIterator
from dataclasses import dataclass

from pydantic_ai import Agent

import takehome.config  # noqa: F401 — triggers ANTHROPIC_API_KEY export
from takehome.db.models import Document, DocumentPage

QA_SYSTEM_PROMPT = """\
You are a legal document analysis assistant for commercial real estate lawyers.
You help lawyers review and understand documents during due diligence.

CITATION FORMAT:
When you reference information from the documents, you MUST cite your sources using this exact format:
【Document Name | Page N, Clause X】

Examples:
- 【Commercial Lease | Page 3, Clause 3.2】
- 【Title Report | Page 1】
- 【Environmental Assessment | Page 4, Section 6.1】

Rules:
- Every factual claim from a document MUST have an inline citation immediately after the claim.
- Use the exact document filename (without .pdf extension) as the Document Name.
- Page numbers are required. Clause/Section references are included when identifiable.
- If information spans multiple pages, cite each relevant page.
- If the answer is not in the provided documents, say so clearly. Do NOT fabricate citations.
- Be concise and precise. Lawyers value accuracy over verbosity.
- You may receive content from multiple documents. Always specify which document you are citing.

CONFLICT DETECTION:
When the same topic (rent, obligations, dates, rights) is addressed in multiple documents:
- Report ALL versions found, citing each source.
- Identify which document appears to be more recent (by date in the document title or content).
- Explicitly flag the discrepancy so the lawyer can verify which takes precedence.
- Do NOT silently choose one version over another.
- Use this format: "Note: [topic] differs between [Doc A] and [Doc B]. [Doc B] (dated later) may supersede, but this should be verified."

CONTEXT FORMAT:
You will receive relevant pages from the conversation's document bundle, pre-selected for relevance.
Each page is wrapped in <page> tags with document name and page number attributes.
Use these attributes for your citations.
"""

title_agent = Agent(
    "anthropic:claude-haiku-4-5-20251001",
    system_prompt="Generate concise conversation titles.",
)

qa_agent = Agent(
    "anthropic:claude-haiku-4-5-20251001",
    system_prompt=QA_SYSTEM_PROMPT,
)


async def generate_title(user_message: str) -> str:
    """Generate a 3-5 word conversation title from the first user message."""
    result = await title_agent.run(
        f"Generate a concise 3-5 word title for a conversation that starts with: '{user_message}'. "
        "Return only the title, nothing else."
    )
    title = str(result.output).strip().strip('"').strip("'")
    if len(title) > 100:
        title = title[:97] + "..."
    return title


REPORT_SYSTEM_PROMPT = """\
You are a legal document analysis assistant generating a structured property report.
Based on the provided document pages, produce a report with the following sections:

## Property Overview
Key details: address, parties, title number, tenure type.

## Key Financial Terms
Rent, service charge, insurance, rent review mechanism.

## Important Dates
Term dates, break dates, rent review dates, lease expiry.

## Obligations & Restrictions
Tenant obligations, landlord obligations, restrictive covenants, permitted use.

## Risk Factors
Environmental risks, title defects, onerous clauses, unusual provisions.

## Summary
2-3 sentence overall assessment.

For each fact, cite the source using: 【Document Name | Page N, Section X】
If information is not available in the documents, state "Not found in documents" for that field.
Use markdown formatting with tables where appropriate.
"""

report_agent = Agent(
    "anthropic:claude-haiku-4-5-20251001",
    system_prompt=REPORT_SYSTEM_PROMPT,
)


async def generate_report(
    retrieved_context: str,
    document_names: list[str],
) -> AsyncIterator[str]:
    """Stream a structured property analysis report from the retrieved document context."""
    prompt_parts: list[str] = []

    if retrieved_context:
        prompt_parts.append(
            "The following are relevant pages from the document bundle:\n\n"
            f"{retrieved_context}\n\n"
            f"Documents in this conversation: {', '.join(document_names)}\n"
        )
    else:
        prompt_parts.append(
            "No documents have been uploaded yet. Cannot generate a report without documents.\n"
        )

    prompt_parts.append(
        "Generate a comprehensive structured property analysis report based on the documents above."
    )

    full_prompt = "\n".join(prompt_parts)

    async with report_agent.run_stream(full_prompt) as result:
        async for text in result.stream_text(delta=True):
            yield text


async def chat_with_documents(
    user_message: str,
    retrieved_context: str,
    document_names: list[str],
    conversation_history: list[dict[str, str]],
    confidence: str = "high",
) -> AsyncIterator[str]:
    """Stream a response to the user's message with citation-grounded answers."""
    prompt_parts: list[str] = []

    if confidence == "low":
        prompt_parts.append(
            "IMPORTANT: The retrieved context may not fully cover this query. "
            "If you cannot find a clear answer in the provided pages, explicitly state "
            "that the information is not available in the uploaded documents rather than speculating.\n"
        )

    if retrieved_context:
        prompt_parts.append(
            "The following are relevant pages from the document bundle:\n\n"
            f"{retrieved_context}\n\n"
            f"Documents in this conversation: {', '.join(document_names)}\n"
        )
    else:
        prompt_parts.append(
            "No documents have been uploaded yet. If the user asks about a document, "
            "let them know they need to upload one first.\n"
        )

    if conversation_history:
        prompt_parts.append("Previous conversation:\n")
        for msg in conversation_history:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                prompt_parts.append(f"User: {content}\n")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}\n")
        prompt_parts.append("\n")

    prompt_parts.append(f"User: {user_message}")

    full_prompt = "\n".join(prompt_parts)

    async with qa_agent.run_stream(full_prompt) as result:
        async for text in result.stream_text(delta=True):
            yield text


# ---------------------------------------------------------------------------
# Citation Parsing & Validation
# ---------------------------------------------------------------------------

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


def normalize_name(name: str) -> str:
    """Normalize a document name for fuzzy matching."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


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
