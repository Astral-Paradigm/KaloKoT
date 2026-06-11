# OpenTender + Counsel — PRD

**One-liner:** Upload a government tender document; get both a corruption-risk heatmap *and* a Digital Lawyer that tells you exactly which laws are being broken, who to report to, and how.

---

## Problem

Government procurement corruption is rampant in many countries, but most people hit two walls:

1. They can *smell* something wrong in a tender — inflated budgets, single-bidder specs, impossibly short deadlines — but can't articulate *why* it's illegal.
2. Even if they know it's wrong, they don't know *what to do about it* — which agency to report to, what law was violated, how to draft a complaint, or what evidence to preserve.

Existing tools like B4E's Bid Analyzer only flag risks. They stop at the red flag. Citizens need the *next step*.

---

## Solution

OpenTender + Counsel is a two-layer system with a unified frontend:

### Layer 1 — The Tender Analyzer (replaces B4E)

Upload a PDF/URL of a government tender. Get:

- **Corruption Risk Heatmap** — per-section risk scores (specification, budget, timeline, evaluation criteria)
- **Traffic Light Score** — overall Green/Yellow/Red
- **Red Flag Report** — specific clauses flagged with explanations (e.g., "Section 7.3: The 3-day bid submission period violates §4.1(a) of the Public Procurement Act — minimum is 14 days")
- **Vendor/Contractor Intelligence** — cross-reference winning bidders against past awards, shell company registries, politically exposed persons (PEPs)

### Layer 2 — The Digital Lawyer (KaloKoT)

A conversational AI counsel with three modes of operation:

#### 💬 Chat Mode
Ask any legal question about your tender, procurement law, constitutional rights, or how to file a report. The lawyer responds grounded in:
- The tender document itself (context window)
- The Constitution of Nepal 2015 via ChromaDB vector search (all-MiniLM-L6-v2 embeddings)
- LLM reasoning with citations

Every lawyer response has a **speaker button** that plays the reply via ElevenLabs TTS (deep male voice).

#### 📋 Analysis Mode
Describe a tender concern or legal issue. The lawyer generates a **structured legal analysis report** that includes:
- Issue summary
- Applicable laws and constitutional articles (with citations from ChromaDB search)
- Risk assessment and implications
- Recommended actions

The analysis is available as a **downloadable PDF** with KaloKoT branding.

#### ⚖️ Complaint Mode
Fill in personal details (Full Name, Permanent Address, Temporary Address, Citizenship No, Phone, Email) and describe the complaint. The lawyer drafts a **formal complaint letter** with:
- To (appropriate authority)
- Subject line
- Statement of facts
- Legal basis (specific laws/constitutional articles violated)
- Prayer / relief sought
- Signature block
- List of attached evidence

The complaint letter is available as a **downloadable PDF** with KaloKoT branding.

> **Chat is always available** — the input bar at the bottom works in all three modes. Users can ask follow-up questions while working on an analysis or complaint.

---

## Target Users

1. **Journalists** investigating procurement corruption — need fast analysis and draft FOIA requests
2. **Civil society / anti-corruption NGOs** — need to process many tenders and batch-produce complaints
3. **Whistleblowers inside government** — need to know their rights and safest reporting channel
4. **Citizens** who spot a suspicious tender in their district and want to act

---

## Design Language: KaloKoT

"KaloKoT" (dark + gold in Nepali) defines the visual identity:

| Element | Value |
|---------|-------|
| Background | Deep noir (`oklch(0.14 0.01 260)`) |
| Accent | Gold gradients (`oklch(0.72 0.14 85)` → `oklch(0.62 0.13 70)`) |
| Text | Cream (`oklch(0.88 0.02 80)`) |
| Muted text | `oklch(0.5 0.02 80)` |
| Grain overlay | Subtle noise texture via SVG filter |
| Glass effect | `background: color-mix(in oklab, white 4%, transparent)` with translucent borders |
| Typography | Inter, tracking-heavy uppercase for accents |

### Mascot: LowPolyLawyer

A low-poly SVG figure in hooded robes — abstract, genderless, faceless. Represents justice without identity. States:
- **idle**: standing still, gold accents
- **speaking**: subtle animation, glow effect

Rendered inline as React component, no external assets. Dark outline on dark background, gold internal highlights.

---

## Non-Technical User Interface

The app is designed for users who may not be comfortable with legal terminology or complex UIs:

- **Single-page chat-first layout** — the landing page IS the Digital Lawyer
- **No legalese** — all responses in plain conversational language
- **Enter to submit** — no multi-step forms for basic questions
- **Three toggle modes** — Chat / Analysis / Complaint — clearly labeled with emoji icons
- **All states visible** — thinking indicator (gold pulsing dots), error messages in plain text
- **PDF download buttons** appear after generation, one click to save

---

## Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| Frontend | Vite + React 19 + TanStack Router | Modern SPA with SSR, fast builds |
| UI framework | Tailwind CSS 4 + shadcn/ui + custom KaloKoT tokens | Dark theme, gold accents, glassmorphism |
| Design system | CSS custom properties (noir, cream, gold, muted-ink) | Themeable, consistent across components |
| Mascot | Inline SVG React component (LowPolyLawyer) | No external assets, adaptable |
| Backend | Python + FastAPI | Async-friendly, familiar |
| LLM | Gemini 2.5 Flash / Claude Sonnet via unified LLMClient | Long context, structured output, citations |
| Document parsing | PyMuPDF / Marker-PDF | High-fidelity PDF → text |
| Embeddings | all-MiniLM-L6-v2 (sentence-transformers) | Local, no API key needed |
| Vector store | ChromaDB | Local-first, persistent, cosine similarity |
| Legal knowledge base | ChromaDB-indexed YAML | Hierarchical: Part → Article → Clause → SubClause |
| Constitution | Constitution of Nepal 2015 (YAML → ChromaDB chunks) | Semantic search with parent-child resolution |
| PDF generation | fpdf2 | Lightweight, pure Python, branded output |
| Text-to-Speech | ElevenLabs API (Adam, deep male voice) | Natural voice for accessibility |
| Dev proxy | Vite dev server → FastAPI (`/api` → `:8000`) | No CORS issues in dev |
| OS | Linux (Bazzite) | Already the target environment |

---

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Browser    │────▶│  FastAPI (:8000)  │────▶│  ChromaDB    │
│  :5173      │     │                  │     │  (local)     │
│  React SPA  │     │  /counsel        │     └──────────────┘
│  KaloKoT    │     │  /constitution-  │          │
│  Theme      │     │    search        │     ┌──────────────┐
│             │     │  /draft-complaint│────▶│  LLMClient   │
│             │     │  /analysis-report│     │  (Gemini/    │
│             │     │  /tts            │     │   Claude)    │
│             │     │  /analyze        │     └──────────────┘
│             │     │  /constitution-  │
│             │     │    context       │
└─────────────┘     └──────────────────┘
```

All frontend `/api/*` requests are proxied to the FastAPI backend during development. ChromaDB runs in-process with the Python backend (no separate server). Constitution YAML is indexed on startup and reused across requests.

---

## LEGAL RAG ARCHITECTURE

### Parent-Child Chunking (Implemented)

Legal text is hierarchical — Part → Article → Clause → SubClause. Standard token-based chunking would break this structure, causing ChromaDB to retrieve fragments without full article context. The system uses **parent-child chunking**:

```
[Parent: Full Article 17 - Right to Freedom]
      ├── [Child 1: Clause 1 (vectorized)]
      ├── [Child 2: Clause 2 (vectorized)]
      └── [Child 3: Clause 3 (vectorized)]
```

When a child chunk matches a query, the **full parent article** is passed to the LLM. This ensures Gemini never sees an orphaned clause fragment.

### Two-Tier Retrieval Strategy

| Tier | Store | Contents | Strategy |
|------|-------|----------|----------|
| **Static** | Gemini Context Cache | Constitution of Nepal 2015 (full text) | Pre-loaded at session start, cached for up to 2 hours. The constitution is ~40K tokens — well within Gemini's 1M-token context cache. |
| **Dynamic** | ChromaDB | User-uploaded tender PDFs, gazettes (Rajpatra), supplementary laws, previous analyses | Vector search at query time. ChromaDB stores both the vectorized child chunks and the full parent text for context resolution. |

**Flow:**
1. User asks a question about procurement law
2. System checks Gemini context cache for Constitution (static ground truth)
3. System also queries ChromaDB for tender-specific content + supplementary laws
4. Both contexts are merged and sent to the LLM for a grounded response
5. Citations are returned with both article numbers and tender clause locations

### Context Caching (Gemini)

Gemini's context caching lets us pre-load the full constitution and keep it warm:
- **Cache key:** hash of constitution YAML version
- **TTL:** 2 hours (configurable)
- **Hit rate expected:** >90% for constitutional queries
- **Fallback:** When cache misses, re-load from ChromaDB `get_context_cache_text()`

ChromaDB is NOT queried for static constitution lookups during cached sessions — only for new documents, tender PDFs, and supplementary laws. This reduces latency from ~500ms (ChromaDB search + parent resolution) to ~50ms (cache fetch).

### Future Optimization: Hybrid Search

For Phase 2, combine ChromaDB's semantic search with BM25 keyword search for legal terminology that vectors may miss (specific article numbers, Latin terms, Nepali legal phrases).

---

## MVP Feature Set (Phase 1)

1. **Upload PDF** → extract text → structured tender analysis (sections, budget, timeline, criteria)
2. **Corruption risk scoring** → Red/Yellow/Green per section with explanations
3. **Constitution of Nepal 2015** indexed in ChromaDB with parent-child chunking (Part → Article → Clause → SubClause)
4. **Semantic constitution search** — query returns matching clauses with parent article context and score
5. **Browse full constitution text** — rendered as downloadable plain text
6. **Digital Lawyer chat** — conversational legal advice grounded in constitution + LLM, with **ElevenLabs TTS** (deep male voice, speaker button per response)
7. **Tender Review mode** — upload PDF or paste text, get corruption risk heatmap + flagged clauses + section scores
8. **Analysis Report mode** — describe an issue → structured legal analysis → **downloadable PDF** with KaloKoT branding
9. **Complaint Drafting mode** — fill personal info + describe complaint → formal complaint letter → **downloadable PDF** with KaloKoT branding
10. **Chat always available** — input bar persists across all four modes (Chat / Tender Review / Analysis / Complaint)
11. **KaloKoT design** — dark noir/gold theme, LowPolyLawyer SVG mascot, glassmorphism panels, grain texture
12. **Two reference jurisdictions** for MVP: Nepal (primary)

---

## User Flow (MVP)

```
User lands on http://localhost:5173
    ↓
Sees the Digital Lawyer mascot (left) and chat interface (right)
    ↓
Mode tabs at top: [💬 Chat] [📄 Tender Review] [📋 Analysis] [⚖️ Complaint]
    ↓
─── Chat Mode (default) ─────────────────────────────
User types: "Is it illegal to have only 3 days for bids?"
    ↓
Lawyer responds with constitutional/procurement law citations
    ↓
User clicks speaker icon → hears response in deep male voice
    ↓
User: "Draft a complaint to PPMO"
    ↓
User switches to Complaint mode
    ↓
─── Complaint Mode ──────────────────────────────────
Form appears: Name, Address, Citizenship No, Phone, Email
User fills details + describes the complaint
    ↓
Clicks "Draft Complaint Letter"
    ↓
LLM generates formal complaint letter grounded in law
    ↓
"Download PDF" button appears → one click saves
    ↓
─── Tender Review Mode ──────────────────────────────
User uploads a tender PDF (drag & drop or click)
    ↓
System extracts text → runs corruption risk analysis
    ↓
Results: Risk badge + Summary + Section scores + Flagged clauses
    ↓
User clicks "Discuss with Lawyer" → returns to Chat with context
    ↓
User switches to Analysis mode for a deep legal report
    ↓
─── Analysis Mode ───────────────────────────────────
User describes: "A road contract awarded at 40% above market rate"
    ↓
Clicks "Generate Analysis Report"
    ↓
LLM searches constitution, returns structured legal analysis
    ↓
"Download PDF" button appears
    ↓
User can still type questions in the chat bar at any time
```

---

## PDF Output Format

### Complaint Letter PDF
- KaloKoT header (dark gold branding bar)
- Title: "FORMAL COMPLAINT LETTER"
- Filing party details (name, address, citizenship no, contact)
- To: [appropriate authority determined by LLM]
- Subject line
- Statement of facts (numbered paragraphs)
- Legal basis (specific laws and constitutional articles violated)
- Prayer / relief sought
- Signature block with date
- Attached evidence list
- Disclaimer footer: "This document is AI-generated and does not constitute legal advice."

### Analysis Report PDF
- KaloKoT header
- Title: "LEGAL ANALYSIS REPORT"
- Issue summary
- Applicable laws (with article citations)
- Risk assessment
- Implications
- Recommended actions
- Disclaimer footer

---

## Directory Structure

```
├── docs/
│   ├── PRD.md               ← this file
│   ├── architecture.md       ← system architecture
│   └── legal/
│       ├── np_constitution.yaml  ← Constitution of Nepal (Parts 1-5)
│       └── np.yaml               ← Nepal procurement law corpus
├── src/
│   ├── analyzer/
│   │   ├── __init__.py
│   │   ├── extractor.py      ← PDF/text extraction
│   │   ├── parser.py         ← Tender structure parser
│   │   ├── scorer.py         ← Corruption risk scoring logic
│   │   └── reporter.py       ← Heatmap + red flag report generator
│   ├── lawyer/
│   │   ├── __init__.py
│   │   ├── counsel.py        ← Digital Lawyer chat engine
│   │   ├── jurisprudence.py  ← Legal knowledge base query
│   │   ├── drafting.py       ← Complaint/FOIA draft generator
│   │   └── disclaimers.py    ← Liability disclaimers
│   ├── shared/
│   │   ├── __init__.py
│   │   ├── models.py         ← Pydantic data models
│   │   ├── llm.py            ← LLM client wrapper (Gemini/Claude/OpenAI/Phi)
│   │   ├── jurisdiction.py   ← Jurisdiction loader
│   │   ├── chroma_store.py   ← ChromaDB + parent-child chunking
│   │   ├── chunking.py       ← Legal text chunking utilities
│   │   ├── pdf_generator.py  ← fpdf2 complaint/analysis PDF generation
│   │   └── tts.py            ← ElevenLabs text-to-speech (male voice "Adam")
│   ├── api.py                ← FastAPI entry point with all endpoints
│   └── main.py               ← Gradio fallback UI
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   └── lawyer/
│   │   │       ├── LowPolyLawyer.tsx  ← SVG mascot component
│   │   │       ├── Backdrop.tsx       ← Animated grain overlay
│   │   │       └── HeroDock.tsx       ← (legacy) Input dock
│   │   ├── lib/
│   │   │   └── api.ts         ← API client (FormData-based)
│   │   ├── routes/
│   │   │   ├── index.tsx      ← Landing page: Chat/Analysis/Complaint modes
│   │   │   ├── chat.tsx       ← (legacy) Separate chat page
│   │   │   ├── constitution.tsx  ← Constitution search + browse page
│   │   │   ├── analysis-report.tsx ← Analysis report viewer
│   │   │   └── __root.tsx     ← Root layout with HeroDock
│   │   └── styles.css         ← Global KaloKoT theme + variables
│   ├── vite.config.ts         ← Vite config with API proxy
│   └── package.json
├── data/
│   └── sample_tenders/       ← Test PDFs (public domain examples)
├── tests/
│   ├── test_analyzer.py
│   └── test_lawyer.py
├── systemd/
│   └── justice.service       ← systemd unit
├── .env                       ← API keys (gitignored)
├── requirements.txt
└── README.md
```

---

## Phase 2 (Post-MVP)

- Multi-jurisdiction legal corpus (India, Bangladesh, Philippines, Kenya, Nigeria)
- Cross-reference winning bidders with open corporate registries (OpenCorporates API)
- PEP (politically exposed persons) matching
- Batch analysis mode for NGOs
- Multilingual support (Nepali, Hindi, etc.)
- FOIA/RTI request generator per jurisdiction
- Anonymized whistleblower submission channel (via SecureDrop integration)
- **PDF file upload** for complaint evidence attachment
- **Saved sessions** — return to previous conversations
- **Enhanced TTS** — emotion/urgency-aware speech variations

---

## Monetization / Sustainability

- **Free tier:** 5 tender analyses/month + basic legal guidance
- **NGO/journalist tier:** Batch processing + priority jurisdiction additions
- **Enterprise (World Bank, UNDP, govt agencies):** Bulk analysis + custom jurisdiction onboarding

---

## Key Risks

- **Legal liability** — the "lawyer" MUST clearly disclaim it's not a real lawyer, AI-generated advice is informational only
- **Jurisdiction accuracy** — procurement law changes; the legal YAML files need versioning and clear last-reviewed dates
- **Retaliation risk for users** — the app must never log user IPs or tender documents server-side; local-first processing with optional encrypted sync
- **PDF quality variance** — scanned PDFs with OCR errors will degrade analysis quality; set expectations upfront
- **TTS API dependency** — ElevenLabs requires internet; degrade gracefully to no-audio when offline

---

## Next Steps

1. [x] Approve concept
2. [x] Write PRD
3. [x] Build Frontend React SPA (KaloKoT design: dark/gold, mascot, glassmorphism)
4. [x] Build Legal Knowledge Base files (Nepal YAML + Constitution YAML)
5. [x] Index Constitution of Nepal in ChromaDB with parent-child chunking
6. [x] Build Constitution search + browse UI
7. [x] Build Digital Lawyer chat with ChromaDB grounding + LLM
8. [x] Build Analysis Report mode with PDF generation
9. [x] Build Complaint Draft mode with PDF generation
10. [x] Integrate ElevenLabs TTS (male voice)
11. [x] Wire up FastAPI + React dev proxy
12. [ ] Test with real tender documents
13. [ ] Deploy demo
14. [ ] User testing with non-technical users
