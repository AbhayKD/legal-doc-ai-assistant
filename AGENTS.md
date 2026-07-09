# AI Agent Instructions

Configuration for AI coding assistants working on this repository.

## Project Overview

A document Q&A application for commercial real estate lawyers. FastAPI backend with a React frontend, using Claude as the LLM. The system supports multi-document analysis with a two-stage retrieval pipeline (BM25 + LLM re-ranker) and produces citation-grounded responses.

## Repository Structure

```
backend/src/takehome/
├── services/
│   ├── retrieval.py    # BM25 index + LLM re-ranker pipeline
│   ├── llm.py          # LLM agents, system prompts, citation parsing & validation
│   ├── document.py     # PDF upload, text extraction, page-level chunking
│   └── conversation.py # Conversation CRUD
├── web/routers/
│   ├── messages.py     # Chat + report streaming endpoints (SSE)
│   ├── documents.py    # Document upload + listing
│   └── conversations.py
├── db/
│   ├── models.py       # Conversation, Message, Document, DocumentPage, Citation
│   └── session.py
└── config.py           # Settings (BM25_CANDIDATES, model names, etc.)

frontend/src/
├── components/         # React components (ChatWindow, DocumentViewer, CitationBadge, ReportView)
├── hooks/              # State management (useMessages, useDocuments, useConversations)
├── lib/                # Utilities (api.ts, citations.ts)
└── types.ts            # TypeScript interfaces

scripts/
└── eval.py             # Evaluation harness (5 test questions, keyword checks)

synthetic-docs/         # Test documents (3 legal PDFs)
real-docs/              # Real-world scanned documents
```

## Working Rules

### 1. No changes without confirmation
Propose changes with reasoning first. Implement only after explicit approval. This applies to architecture decisions, new files, and modifications to existing logic.

### 2. Deliberate decision-making
When facing a design choice, present options with trade-offs. Explain why one approach is preferred over alternatives. Never silently pick an approach — the reasoning matters as much as the result.

### 3. Test-driven quality validation
- Run tests after every change: `docker compose exec backend uv run pytest /app/backend/tests/ -v`
- Verify backend logs: `docker compose logs backend | grep -i error`
- Verify frontend compilation: `docker compose logs frontend | grep -i error`
- Test API endpoints directly with curl before relying on frontend
- Don't assume it works — verify at each layer

### 4. Code review before shipping
Before considering any piece of work complete, review for:
- Dead code, unused imports, copy-paste errors
- Naming consistency (functions, variables, files)
- Potential runtime issues (null access, type mismatches, race conditions)
- Things that look careless to a reviewer

### 5. Incremental verification
Build and verify in layers:
1. Backend logic (unit tests)
2. API endpoints (curl/httpx)
3. Frontend integration (browser)

Never build the full stack and hope it works end-to-end.

## Architecture Decisions

| Component | Choice | Why |
|-----------|--------|-----|
| Retrieval | BM25 + LLM re-ranker | No vector DB infra needed. BM25 handles legal keyword matching. Re-ranker adds semantic understanding. |
| Chunking | Page-level | Maps 1:1 to PDF pages for citation navigation. |
| Citations | Inline 【...】 markers | Streaming-compatible. Unicode brackets never appear in legal text. |
| Validation | Document-wide clause search | Confirms clause isn't hallucinated. Page navigation goes to content location. |
| Highlighting | Clause text on page, fallback to banner | Highlights when possible, honest "Referenced page" banner when clause is on a different page. |
| Confidence | BM25 score + re-ranker selection count | Warns users when retrieval quality is low. |

## Key Commands

```bash
# Start the app
docker compose up -d

# Run tests
docker compose exec backend uv run pytest /app/backend/tests/ -v

# Run evaluation harness (requires app running)
docker compose exec backend uv run python /app/scripts/eval.py

# Reset database
docker compose down -v && docker compose up -d

# View logs
docker compose logs backend -f
docker compose logs frontend -f
```

## Important Notes

- `.env` contains the API key — never commit it (gitignored)
- Model is currently Haiku (API key limitation) — architecture supports Sonnet/Opus swap in `services/llm.py`
- `BM25_CANDIDATES` in config.py controls pre-filter size (default 20, tunable)
- Citation status: `verified` (green) = clause exists in document. `partial` (yellow) = clause not found, possible hallucination. `dropped` = document doesn't exist (not shown to user).
