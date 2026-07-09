from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass

import structlog
from pydantic_ai import Agent
from sqlalchemy.ext.asyncio import AsyncSession

from takehome.config import settings
from takehome.services.document import get_document_pages_for_conversation

logger = structlog.get_logger()

BM25_CANDIDATES = settings.bm25_candidates

reranker_agent = Agent(
    "anthropic:claude-haiku-4-5-20251001",
    system_prompt=(
        "You are a relevance judge for legal document retrieval. "
        "Given a user's query and a set of document pages, determine which pages "
        "contain information needed to fully answer the query.\n\n"
        "IMPORTANT: Be generous with inclusion. Include pages that:\n"
        "- Directly answer the query\n"
        "- Provide context needed to understand the answer\n"
        "- Contain related clauses or definitions referenced by the answer\n"
        "- Come from different documents when the query spans multiple documents\n\n"
        "For cross-document queries, you MUST include pages from all relevant documents.\n"
        "When in doubt, include the page — it's better to include slightly too many than to miss relevant information.\n\n"
        "Return ONLY a JSON array of page indices (0-based).\n"
        "Example output: [0, 2, 5, 7, 12]"
    ),
)


@dataclass
class PageCandidate:
    document_id: str
    document_name: str
    page_number: int
    content: str
    bm25_score: float = 0.0


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\b\w+\b", text.lower())


class BM25Index:
    """In-memory BM25 index over page-level chunks."""

    def __init__(self, pages: list[PageCandidate], k1: float = 1.5, b: float = 0.75):
        self.pages = pages
        self.k1 = k1
        self.b = b
        self.corpus = [_tokenize(p.content) for p in pages]
        self.doc_lengths = [len(d) for d in self.corpus]
        self.avg_dl = sum(self.doc_lengths) / len(self.doc_lengths) if self.corpus else 1
        self.n = len(self.corpus)
        self.df: dict[str, int] = {}
        for doc_tokens in self.corpus:
            seen = set(doc_tokens)
            for token in seen:
                self.df[token] = self.df.get(token, 0) + 1

    def score(self, query: str, top_n: int = BM25_CANDIDATES) -> list[PageCandidate]:
        query_tokens = _tokenize(query)
        scores = [0.0] * self.n

        for token in query_tokens:
            if token not in self.df:
                continue
            idf = math.log((self.n - self.df[token] + 0.5) / (self.df[token] + 0.5) + 1)
            for i, doc_tokens in enumerate(self.corpus):
                tf = doc_tokens.count(token)
                dl = self.doc_lengths[i]
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * dl / self.avg_dl)
                scores[i] += idf * numerator / denominator

        for i, page in enumerate(self.pages):
            page.bm25_score = scores[i]

        ranked = sorted(self.pages, key=lambda p: p.bm25_score, reverse=True)
        return ranked[:top_n]


async def _rerank_pages(query: str, candidates: list[PageCandidate]) -> list[PageCandidate]:
    """Use Haiku to select genuinely relevant pages from BM25 candidates."""
    if not candidates:
        return []

    numbered_pages = "\n\n".join(
        f"[{i}] Document: {c.document_name} | Page {c.page_number}\n{c.content}"
        for i, c in enumerate(candidates)
    )

    prompt = (
        f"User query: {query}\n\n"
        f"Document pages ({len(candidates)} total):\n\n"
        f"{numbered_pages}\n\n"
        "Which page indices contain information needed to answer this query? "
        "Return a JSON array of indices."
    )

    try:
        result = await reranker_agent.run(prompt)
        response_text = str(result.output).strip()
        logger.info("Re-ranker raw response", response=response_text[:500])
        # Extract JSON array from response (may be wrapped in code fences)
        match = re.search(r"\[[\d,\s]+\]", response_text)
        if match:
            indices = json.loads(match.group())
            relevant = [candidates[i] for i in indices if 0 <= i < len(candidates)]
            if relevant:
                logger.info(
                    "Re-ranker selected pages",
                    total_candidates=len(candidates),
                    selected=len(relevant),
                )
                return relevant
            else:
                logger.warning("Re-ranker returned no valid indices, falling back")
        else:
            logger.warning("Re-ranker response did not contain JSON array", response=response_text[:200])
    except Exception:
        logger.exception("Re-ranker failed, falling back to all candidates")

    return candidates


def _assemble_context(pages: list[PageCandidate]) -> str:
    """Assemble selected pages into a formatted context string for the LLM."""
    sections: list[str] = []
    for page in pages:
        sections.append(
            f"<page document=\"{page.document_name}\" page=\"{page.page_number}\">\n"
            f"{page.content}\n"
            f"</page>"
        )
    return "\n\n".join(sections)


def _compute_confidence(
    relevant_pages: list[PageCandidate],
    bm25_top: list[PageCandidate],
) -> str:
    """Compute a confidence level based on retrieval quality signals.

    - "high": re-ranker selected >= 3 pages AND top BM25 score > 2.0
    - "medium": re-ranker selected >= 1 page AND top BM25 score > 1.0
    - "low": re-ranker selected 0 pages OR top BM25 score < 1.0
    """
    num_selected = len(relevant_pages)
    top_bm25_score = bm25_top[0].bm25_score if bm25_top else 0.0

    if num_selected >= 3 and top_bm25_score > 2.0:
        return "high"
    elif num_selected >= 1 and top_bm25_score > 1.0:
        return "medium"
    else:
        return "low"


async def retrieve_context(
    session: AsyncSession,
    conversation_id: str,
    query: str,
) -> tuple[str, list[PageCandidate], str]:
    """Run the full retrieval pipeline: load pages → BM25 → re-rank → assemble context.

    Returns (assembled_context_string, pages_used, confidence).
    """
    document_pages = await get_document_pages_for_conversation(session, conversation_id)

    if not document_pages:
        return "", [], "low"

    candidates = [
        PageCandidate(
            document_id=dp.document_id,
            document_name=dp.document.filename.replace(".pdf", ""),
            page_number=dp.page_number,
            content=dp.content,
        )
        for dp in document_pages
    ]

    logger.info(
        "Retrieval pipeline starting",
        conversation_id=conversation_id,
        total_pages=len(candidates),
        query=query[:100],
    )

    index = BM25Index(candidates)
    bm25_top = index.score(query, top_n=BM25_CANDIDATES)

    relevant_pages = await _rerank_pages(query, bm25_top)

    context = _assemble_context(relevant_pages)
    confidence = _compute_confidence(relevant_pages, bm25_top)

    logger.info(
        "Retrieval pipeline complete",
        pages_selected=len(relevant_pages),
        context_length=len(context),
        confidence=confidence,
    )

    return context, relevant_pages, confidence
