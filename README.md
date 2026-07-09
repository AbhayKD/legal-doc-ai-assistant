# Legal Document AI Assistant

An AI-powered document analysis assistant for commercial real estate lawyers. Upload a bundle of legal documents (leases, title reports, environmental assessments) and ask questions that span across them — with every answer cited back to the exact source.

> See [APPROACH.md](APPROACH.md) for architecture decisions and design rationale.

---

## Setup

### Prerequisites
- Docker and Docker Compose
- just (command runner) — install via `brew install just` or `cargo install just`

That's it. Everything else runs inside containers.

### Getting Started

1. Clone this repository

2. Run the setup command:
```
just setup
```
   This copies `.env.example` to `.env` and builds the Docker images.

3. Add your Anthropic API key to `.env`:
```
ANTHROPIC_API_KEY=your_key_here
```

4. Start everything:
```
just dev
```
   This starts PostgreSQL, the FastAPI backend (port 8000), and the React frontend (port 5173).
   Database migrations run automatically when the backend starts — no separate step needed.

5. Open http://localhost:5173 in your browser.

Your local `backend/src/` and `frontend/src/` directories are mounted into the containers —
edit files normally on your machine and changes hot-reload automatically.

### Running Tests

```bash
docker compose exec backend uv run pytest /app/backend/tests/ -v
```

### Running the Evaluation Harness

With the app running:
```bash
docker compose exec backend uv run python /app/scripts/eval.py
```
This uploads the synthetic docs, asks 5 test questions, and checks answers against expected criteria.

### Resetting the Database

If you need a clean slate (e.g., after schema changes):
```bash
just reset
just dev
```

---

## Features

### Cross-Document Analysis
Upload multiple PDFs per conversation. Ask questions that require finding and comparing information across documents — the retrieval pipeline selects relevant pages from across the entire bundle.

### Citation & Grounding
Every factual claim links to a specific document and page. Click a citation badge to navigate the PDF viewer directly to the source. Hallucinated citations are validated and silently dropped.

### Structured Report Generation
Click the report button to generate a structured property analysis (Property Overview, Financial Terms, Dates, Obligations, Risks, Summary) with collapsible sections and a "Copy Markdown" button for export.

### Confidence Scoring
When retrieval quality is low, the system warns the user rather than presenting uncertain answers as authoritative.

### Conflict Detection
When the same topic is addressed differently across documents, the system flags the discrepancy and identifies which document appears more recent.

---

## Project Structure

```
backend/src/takehome/
├── schemas/            # Pydantic request/response models
├── services/
│   ├── citations.py    # Citation parsing & validation
│   ├── llm.py          # LLM agent setup & streaming
│   ├── prompts.py      # System prompts
│   ├── retrieval.py    # BM25 + LLM re-ranker pipeline
│   ├── document.py     # PDF upload & page extraction
│   └── conversation.py # Conversation CRUD
├── web/routers/        # FastAPI endpoints
└── db/                 # SQLAlchemy models & session

frontend/src/
├── components/         # React components
├── hooks/              # State management
├── lib/                # Utilities (API client, citation parsing)
└── types.ts            # TypeScript interfaces

scripts/
├── eval.py             # Automated evaluation harness
└── generate-synthetic-docs.py

synthetic-docs/         # Test documents (3 legal PDFs)
real-docs/              # Real-world scanned documents
backend/tests/          # Unit tests (34 tests)
```

### Useful Commands

- `just dev` — Start full stack (Postgres + backend + frontend)
- `just stop` — Stop all services
- `just reset` — Stop everything and clear database
- `just check` — Run all linters and type checks
- `just fmt` — Format all code
- `just db-shell` — Open a psql shell
- `just logs-backend` — Tail backend logs

### Sample Documents

- `synthetic-docs/` — Programmatically generated legal documents (clean text PDFs). Use these as the primary test case.
- `real-docs/` — Real-world legal documents including scanned pages and title plans.
