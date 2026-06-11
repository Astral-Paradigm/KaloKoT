# OpenTender + Counsel — PRD

**One-liner:** Upload a government tender document; get both a corruption-risk heatmap *and* a Virtual Lawyer that tells you exactly which laws are being broken, who to report to, and how.

---

## Problem

Government procurement corruption is rampant in many countries, but most people hit two walls:

1. They can *smell* something wrong in a tender — inflated budgets, single-bidder specs, impossibly short deadlines — but can't articulate *why* it's illegal.
2. Even if they know it's wrong, they don't know *what to do about it* — which agency to report to, what law was violated, how to draft a complaint, or what evidence to preserve.

Existing tools like B4E's Bid Analyzer only flag risks. They stop at the red flag. Citizens need the *next step*.

---

## Solution

OpenTender + Counsel is a two-layer system:

### Layer 1 — The Tender Analyzer (replaces B4E)

Upload a PDF/URL of a government tender. Get:

- **Corruption Risk Heatmap** — per-section risk scores (specification, budget, timeline, evaluation criteria)
- **Traffic Light Score** — overall Green/Yellow/Red
- **Red Flag Report** — specific clauses flagged with explanations (e.g., "Section 7.3: The 3-day bid submission period violates §4.1(a) of the Public Procurement Act — minimum is 14 days")
- **Vendor/Contractor Intelligence** — cross-reference winning bidders against past awards, shell company registries, politically exposed persons (PEPs)

### Layer 2 — The Virtual Counsel (new)

After the analysis, the user enters an interactive chat with a "Virtual Lawyer" that can:

- **Legal Violation Analysis** — tells you the *specific* law, regulation, or procurement code clause being violated, with citations
- **Jurisdiction-Specific Guidance** — if you say "I'm in Nepal," it maps violations to Nepali procurement law (Public Procurement Act 2063, PPMO guidelines) and the appropriate oversight body (PPMO, CIAA, OAG)
- **Complaint Drafting** — generates a ready-to-file complaint letter, whistleblower report, or FOIA/access-to-information request tailored to the jurisdiction
- **Evidence Checklist** — what to screenshot, save, and timestamp before the tender vanishes
- **Who to Tell** — maps the violation type to the right oversight body (anti-corruption commission, ombudsman, procurement authority, media)
- **Risk Assessment** — honest appraisal of personal risk if you blow the whistle (retaliation likelihood, anonymity options, witness protection where available)

---

## Target Users

1. **Journalists** investigating procurement corruption — need fast analysis and draft FOIA requests
2. **Civil society / anti-corruption NGOs** — need to process many tenders and batch-produce complaints
3. **Whistleblowers inside government** — need to know their rights and safest reporting channel
4. **Citizens** who spot a suspicious tender in their district and want to act

---

## Tech Stack (Initial)

| Component | Choice | Why |
|---|---|---|
| LLM | Gemini 2.5 Pro / Claude Sonnet | Long context (tender PDFs), structured output, citations |
| Document parsing | PyMuPDF / Marker-PDF | High-fidelity PDF -> text |
| Embeddings | text-embedding-004 | Semantic search across tender clauses + legal corpus |
| Vector store | ChromaDB / SQLite + mps | Local-first, no API key needed for retrieval |
| Legal knowledge base | Jurisdiction-specific YAML/JSON | Per-country procurement law corpus (maintainable by crowd) |
| Frontend (later) | Gradio / Streamlit quick UI | Fastest path to demo; Next.js for production |
| Backend | Python + FastAPI | Familiar, async-friendly for PDF processing |
| OS | Linux (Bazzite) | Already the target environment |

---

## MVP Feature Set (Phase 1)

1. **Upload PDF** → extract text → structured tender analysis (sections, budget, timeline, criteria)
2. **Corruption risk scoring** → Red/Yellow/Green per section with explanations
3. **Virtual Lawyer chat** — user types questions, gets answers grounded in:
   - The tender document itself (context window)
   - Hardcoded jurisdiction legal knowledge (YAML-based)
   - LLM reasoning with citations
2. **Two reference jurisdictions** for MVP:
   - Nepal (user's timezone, relevant context, growing procurement reform)
5. **Downloadable complaint draft** — .txt/.docx output
6. **Evidence checklist** — printable step-by-step

---

## Phase 2 (Post-MVP)

- Multi-jurisdiction legal corpus (India, Bangladesh, Philippines, Kenya, Nigeria)
- Cross-reference winning bidders with open corporate registries (OpenCorporates API)
- PEP (politically exposed persons) matching
- Batch analysis mode for NGOs
- Multilingual support (Nepali, Hindi, etc.)
- FOIA/RTI request generator per jurisdiction
- Anonymized whistleblower submission channel (via SecureDrop integration)

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

---

## User Flow (MVP)

```
User lands → Uploads PDF tender (or pastes URL)
    ↓
System extracts & structures text
    ↓
Corruption Risk Heatmap generated [1-2 min]
    ↓
User sees: Traffic Light (Overall) + Section Scores + Red Flag Report
    ↓
User clicks "Talk to Virtual Lawyer"
    ↓
Chat interface opens with tender context pre-loaded
    ↓
User asks: "Is it illegal to have only 3 days for bids?"
    ↓
Lawyer responds: Cites specific clause, jurisdiction law, suggests action
    ↓
User: "Draft a complaint to KPK"
    ↓
Lawyer generates downloadable complaint letter
```

---

## Directory Structure

```
├── docs/
│   ├── PRD.md               ← this file
│   ├── architecture.md       ← system architecture
│   └── legal/
│       └── np.yaml        ← Nepal procurement law corpus
├── src/
│   ├── analyzer/
│   │   ├── __init__.py
│   │   ├── extractor.py      ← PDF/text extraction
│   │   ├── parser.py         ← Tender structure parser
│   │   ├── scorer.py         ← Corruption risk scoring logic
│   │   └── reporter.py       ← Heatmap + red flag report generator
│   ├── lawyer/
│   │   ├── __init__.py
│   │   ├── counsel.py        ← Virtual Lawyer chat engine
│   │   ├── jurisprudence.py  ← Legal knowledge base query
│   │   ├── drafting.py       ← Complaint/FOIA draft generator
│   │   └── disclaimers.py    ← Liability disclaimers
│   ├── shared/
│   │   ├── __init__.py
│   │   ├── models.py         ← Pydantic data models
│   │   ├── llm.py            ← LLM client wrapper
│   │   └── jurisdiction.py   ← Jurisdiction loader
│   └── main.py               ← FastAPI entry point + Gradio UI
├── data/
│   └── sample_tenders/       ← Test PDFs (public domain examples)
├── tests/
│   ├── test_analyzer.py
│   └── test_lawyer.py
├── requirements.txt
└── README.md
```

---

## Next Steps

1. [x] Approve concept
2. [x] Write PRD
3. [ ] Build Legal Knowledge Base files (Nepal YAML)
4. [ ] Build Tender Extractor + Parser (src/analyzer/)
5. [ ] Build Corruption Risk Scorer (src/analyzer/)
6. [ ] Build Virtual Lawyer engine (src/lawyer/)
7. [ ] Wire up FastAPI + Gradio UI
8. [ ] Test with real tender documents
9. [ ] Deploy demo
