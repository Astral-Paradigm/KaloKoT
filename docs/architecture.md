# OpenTender + Counsel — Architecture

## System Overview

```
┌─────────────────────────────────────────────────┐
│                    User                         │
│  (Uploads PDF tender / pastes URL / chats)      │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│           Gradio / FastAPI Frontend              │
│  - File upload handler                          │
│  - Chat interface (Virtual Lawyer)              │
│  - Session management                           │
└────┬─────────────────────────────────┬──────────┘
     │                                 │
┌────▼──────────┐           ┌──────────▼──────────┐
│  /analyze     │           │   /counsel           │
│  Tender       │           │   Virtual            │
│  Pipeline     │           │   Lawyer             │
└────┬──────────┘           └──────────┬──────────┘
     │                                 │
┌────▼─────────────────────────────────▼──────────┐
│              LLM Orchestrator                    │
│  (Gemini 2.5 Pro / Claude — structured output)   │
└────┬─────────────────────────────────┬──────────┘
     │                                 │
┌────▼──────────┐           ┌──────────▼──────────┐
│  Analyzer     │           │  Counsel             │
│  Pipeline     │           │  Pipeline            │
│               │           │                      │
│  - PDF→Text   │           │  - Legal KB Query    │
│  - Section    │           │  - Jurisdiction      │
│    Extraction │           │    Resolution        │
│  - Risk       │           │  - Draft Generator   │
│    Scoring    │           │  - Risk Assessment   │
│  - Red Flag   │           │  - Citation Builder  │
│    Report     │           │                      │
└───────────────┘           └──────────────────────┘
```

## Data Flow

### Analysis Pipeline
1. PDF uploaded → `extractor.py` (PyMuPDF/Marker-PDF) → raw text
2. Raw text → `parser.py` → structured sections (spec, budget, timeline, evaluation, terms)
3. Structured tender + Scoring rules → `scorer.py` → per-section risk scores
4. Scores + flagged clauses → `reporter.py` → HTML heatmap + JSON report
5. Report cached in memory (no server-side persistence)

### Counsel Pipeline
1. User question + tender context → `counsel.py`
2. `counsel.py` identifies jurisdiction from user or tender metadata
3. Loads jurisdiction YAML from `docs/legal/<jurisdiction>.yaml`
4. Builds LLM prompt: tender context + legal KB + user question
5. LLM returns structured answer with citations
6. If user requests complaint draft → `drafting.py` formats output
7. Response streamed to chat UI

## Key Design Decisions

### Local-First
- No user data stored server-side
- PDFs processed in memory and discarded
- Session state in browser (sessionStorage) or in-memory dict
- Optional: encrypted export for user to save their own session

### Legal Knowledge is Data, Not Code
- Each jurisdiction = a YAML file in `docs/legal/`
- Schema: violation type → law reference → actionable steps → oversight body
- Versioned with `last_reviewed` dates
- Crowd-contributable via PRs
- LLM reasons over this data; never generates fake law

### LLM Strategy
- **Analysis pass:** structured output mode (constrained generation)
  - Output: JSON with sections, scores, flagged clauses
  - Schema defined in `shared/models.py`
- **Counsel pass:** free-form but grounded
  - System prompt includes: tender text, legal KB, hard instructions to cite
  - Temperature 0.3 (low creativity, high faithfulness)
- **Failsafe:** If the legal KB doesn't cover the user's jurisdiction, the lawyer openly says so rather than guessing

## Component Details

### src/analyzer/extractor.py
- Accepts: file path (PDF) or URL
- Uses: PyMuPDF (fitz) for text extraction
- Returns: plain text + page numbers
- Falls back to: Marker-PDF for complex layouts (tables, columns)

### src/analyzer/parser.py
- Accepts: raw tender text
- Uses: LLM call with structured output schema
- Returns: `TenderDocument` model with sections
- Sections: `details` (title, ref, authority, value), `specification`, `budget`, `timeline`, `evaluation_criteria`, `terms_and_conditions`

### src/analyzer/scorer.py
- Accepts: structured tender + scoring config
- Red flags (examples):
  - Timeline < 14 days from publication → timeline risk
  - Single technical spec that matches only one vendor → spec capture risk
  - Budget > 30% above market rate → budget inflation risk
  - Evaluation criteria >70% price weight → lowest-bidder trap
  - Missing or vague evaluation criteria → opaque award risk
  - "Negotiable" budget → slush fund risk
- Returns: `RiskReport` with per-section scores + flagged clauses

### src/lawyer/counsel.py
- Accepts: tender context, user question, jurisdiction (optional)
- Loads legal KB for detected jurisdiction
- Constructs system prompt with:
  - Tender summary (from analysis stage)
  - Legal articles and their penalties (from YAML)
  - Hard guardrails: "If you don't know, say 'This is outside my knowledge base'"
- Returns: natural language answer + citations + suggested actions

### src/lawyer/jurisprudence.py
- Loads all `docs/legal/*.yaml` files
- Provides `query_jurisdiction(jurisdiction: str, violation_type: str) -> List[LegalArticle]`
- Semantic fallback: if exact match fails, uses embedding similarity

### src/lawyer/drafting.py
- Accepts: violation details, jurisdiction, user info (optional)
- Generates: complaint letter, FOIA request, or whistleblower report
- Templates per jurisdiction (YAML-defined)
- Returns: markdown text (convertible to .docx)

### src/lawyer/disclaimers.py
- Constitutional-quality disclaimers for each jurisdiction
- Rendered at the top of every counsel session
- Warns: AI is not a lawyer, advice is informational, consult real counsel for legal action

## MVP Diagram

```
                         Tender PDF
                             │
                             ▼
                    ╔══════════════════╗
                    ║  PDF Extractor   ║
                    ╚══════════════════╝
                             │
                             ▼
                    ╔══════════════════╗
                    ║  LLM Parser      ║  ← Structured JSON extraction
                    ╚══════════════════╝
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        ╔═══════════╗ ╔═══════════╗ ╔═══════════╗
        ║ Scorer    ║ ║ Reporter  ║ ║ Counsel   ║
        ╚═══════════╝ ╚═══════════╝ ╚═══════════╝
              │              │              │
              ▼              ▼              ▼
        Risk Scores    Heatmap HTML    Lawyer Chat
```

## Deployment

### Local (Current)
- `python src/main.py` → launches Gradio on localhost:7860
- All processing local; LLM calls via API key (Gemini / OpenRouter / Anthropic)

### Future (Production)
- Containerized with Docker
- Optional: Ollama for fully local LLM inference
- Nginx reverse proxy + SSL
- No database; stateless ephemeral sessions
