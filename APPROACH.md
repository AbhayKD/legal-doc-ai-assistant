# Approach

## Design Philosophy

Commercial real estate lawyers have professional liability for the advice they give. An AI assistant in this domain isn't useful unless it can be verified — every claim must trace back to a specific source, and the system must be honest about what it doesn't know. This shaped the architecture: retrieval accuracy and citation traceability were prioritised over response speed or feature breadth.

## Architecture

The system uses a two-stage retrieval pipeline: BM25 keyword scoring followed by an LLM re-ranker that selects genuinely relevant pages.

I chose BM25 over embeddings/vector search because legal queries are terminology-heavy — lawyers ask about "break clauses", "rent review mechanisms", and "restrictive covenants" using the exact terms that appear in documents. BM25 excels here without requiring embedding infrastructure. The LLM re-ranker adds semantic understanding on top: it reads the full text of BM25 candidates and decides which pages are needed to answer the query. There's no fixed page limit — a narrow question might need 2 pages, a cross-document comparison might need 12. The model decides.

Citations are parsed from the response, then validated against source documents. If a cited clause doesn't exist anywhere in the document, it's silently dropped — the user never sees an unverifiable reference. Navigation takes the user to the page where the content is, with in-page highlighting when the clause text is present.

I chose not to build an embedding-based retrieval layer because at the scale of a typical property bundle (3-50 documents), BM25 + re-ranker provides better precision for legal terminology with zero additional infrastructure. I also chose not to add external domain knowledge injection — at this stage, grounding answers strictly in the uploaded documents is more trustworthy than injecting legal knowledge that might not apply to the specific jurisdiction or transaction.

## What Was Built

### Core Features (from the brief)

- **Cross-Document Analysis** — Upload multiple PDFs per conversation. Questions that span documents (e.g., "how do the environmental risks affect the lease terms?") are answered by retrieving relevant pages from across the entire bundle. Works for 3 documents (tested) and scales architecturally to 50 via the BM25 pre-filter.

- **Citation & Grounding** — Every factual claim links to a specific document and page. Citations are clickable badges that navigate the PDF viewer to the source page with clause highlighting. Hallucinated citations are validated and silently dropped before reaching the user.

### Extensions Implemented

- **Structured Report Generation** — A "Generate Report" button produces a structured property analysis (Property Overview, Financial Terms, Important Dates, Obligations, Risk Factors, Summary) rendered in collapsible sections with a "Copy Markdown" button for export. Reuses the same retrieval pipeline with a report-specific prompt.

- **Confidence Scoring** — When retrieval quality is low (weak BM25 scores or few relevant pages found), the system warns the user that the answer may be incomplete rather than presenting low-confidence answers as authoritative.

- **Conflict Detection** — When the same topic is addressed differently across documents (e.g., rent amended by a deed of variation), the system flags the discrepancy and identifies which document appears more recent, rather than silently choosing one version.

### Deliberately Left Out

- **Visual Document Understanding** — The `DocumentPage` model supports adding an `image_path` column for vision-based extraction, but OCR/vision was not implemented. The synthetic test documents have clean text layers.

- **Portfolio Analysis** — The retrieval pipeline works across any number of documents, but there's no batch-query interface for running the same analysis across multiple properties simultaneously.

- **Domain Knowledge** — The system grounds answers strictly in uploaded documents. Injecting external legal knowledge (standard clause interpretations, jurisdiction-specific rules) risks applying concepts from the wrong jurisdiction or outdated precedents. For a v1, explicit document grounding is more trustworthy. A production system could add a curated, jurisdiction-aware knowledge base.

- **Web-Enriched Analysis** — External data sources (planning records, legal databases) were not integrated. Grounding strictly in uploaded documents is more trustworthy for a v1.

- **Embedding/Semantic Search** — Not needed at the current scale (≤50 docs). Would add value when queries use different terminology than the source text.

## What I'd Do Next

The architecture supports a model upgrade from Haiku to Sonnet (constrained by the provided API key). Sonnet would improve reasoning quality for complex cross-document queries.

The harder unsolved problem: conflicting information across documents. A deed of variation might supersede terms from the original lease. The current system flags conflicts at the prompt level — when the LLM sees the same topic stated differently across documents, it reports all versions and identifies which appears more recent. A production system would need a structural conflict-detection layer with document hierarchy (deed of variation > original lease) and temporal ordering, rather than relying on the LLM to notice discrepancies.

## Key Challenge

The most architecturally interesting problem was calibrating the re-ranker's selection behaviour. Initially it selected only 1 page per query — technically answering the question but missing cross-references that lawyers rely on (e.g., a break clause on page 7 references conditions defined in the interpretation section on page 2).

This revealed a design tension: aggressive filtering improves precision but risks missing the connective tissue between clauses that makes legal analysis possible. Fixed thresholds (top-K) don't solve this because query complexity varies. The solution was to remove the threshold entirely and let the re-ranker decide — prompting it to include pages that provide context for the answer, not just pages that directly contain it.
