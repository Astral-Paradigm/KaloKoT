<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Astral-Paradigm/Justice_system/main/docs/screenshots/counsel-landing.jpg">
  <img alt="KaloKoT — Digital Counsel" src="https://raw.githubusercontent.com/Astral-Paradigm/Justice_system/main/docs/screenshots/counsel-landing.jpg" width="100%">
</picture>

<div align="center">

# कालो कोट — KaloKoT

**Digital Counsel** — _the judge who never sleeps, the clerk who never forgets._

</div>

> **Drop in a government tender → get a corruption-risk heatmap. Then go one step further: a Digital Lawyer who tells you exactly which law is being bent, who to report it to, and how.**

| Badge | Value |
|---|---|
| **Status** | 🚀 Live — [kalokot.netlify.app](https://kalokot.netlify.app/) |
| **Backend** | Python · FastAPI · ChromaDB RAG |
| **Frontend** | React 19 · Vite · TanStack Start (SSR) |
| **License** | MIT — free for civic use |

---

## 💡 What is KaloKoT?

Government procurement is where public money goes to die — inflated budgets, impossibly short deadlines, single-brand specs, vanished evaluation criteria. Ordinary citizens and journalists can *smell* a rigged tender, but they hit two walls:

1. **They can't articulate *why* it's illegal.** They *feel* something is wrong but can't name the law.
2. **They don't know *what to do about it*.** Which agency to report to, what evidence to preserve, or how to draft a complaint.

KaloKoT breaks both walls. It **scans the tender**, flags corruption patterns with traffic-light severity, and hands you a **Digital Lawyer** that cites the actual statute, names the oversight body (PPMO, CIAA, OAG), and drafts a finished complaint letter or legal analysis report — downloadable as a branded PDF.

> ⚠️ **Not a law firm.** KaloKoT is an informational tool built for activists, journalists, NGOs, and citizens. It never fabricates law — and never claims to replace a qualified attorney.

---

## ✨ Features

### 🎯 The Tender Analyzer
Upload a PDF, paste text, or point it at a URL. KaloKoT extracts the document and scores **nine corruption-risk heuristics** — no LLM required for the red-flag engine:

- ⏱️ **Suspiciously short timeline** (incl. Bikram Sambat date conversion)
- 🏷️ **Single brand / tailored specifications**
- 💰 **Budget inflation & missing rate analysis**
- 🕳️ **Vague or missing evaluation criteria**
- 🚨 **Unjustified emergency procurement**
- 🔗 **Conflict-of-interest signals**
- ⚖️ **One-sided contract terms**

Every flag comes with a **risk level** (Green / Yellow / Red), the section it lives in, *why it matters*, and a concrete remedy.

### 🧑‍⚖️ The Digital Lawyer
- **💬 Counsel chat** — grounded answers with legal citations and suggested actions
- **📋 Legal analysis reports** — structured briefs, downloadable as branded PDFs
- **⚖️ Complaint drafting** — a formal complaint letter with statement of facts, legal basis, prayer, evidence list, and authority — exported as PDF/DOCX
- **📖 Constitution search** — semantic browse of the Constitution of Nepal 2015 via ChromaDB parent-child RAG
- **🗣️ Text-to-speech** — every answer can be read aloud (ElevenLabs deep voice)

### 🧱 Under the hood
- **Rule-based scoring** — the corruption engine runs with **zero LLM calls**
- **Failsafe citations** — the lawyer never invents law; if the knowledge base doesn't cover a question, it says so
- **Jurisdiction as data** — every country's legal corpus is a YAML file you can ship in a PR
- **Local-first & private** — no server-side persistence, PDFs processed in memory, sessions encrypted in the browser

---

## 🖼️ The Product

### The Counsel — land, then talk.

![KaloKoT Digital Counsel](/docs/screenshots/counsel-landing.jpg)

### Drop a tender in. Watch the flags fly.

The extractor accepts PDFs, text, HTML, and images (OCR via Gemini). Paste a document and hit **Analyze**:

![Tender upload](/docs/screenshots/tender-upload.jpg)

### A corruption-risk heatmap in seconds.

Suspiciously short timeline, no evaluation criteria, inflated budget, emergency procurement — all scored, all cited:

![RED-flag analysis](/docs/screenshots/analysis-red-flag.jpg)

The full section-level heatmap with per-flag risk reasons and remedies:

![Analysis heatmap](/docs/screenshots/analysis-heatmap.jpg)

### Formal legal output, without the forms.

Draft a complaint letter or generate a full legal analysis — one click to a KaloKoT-branded PDF:

![Complaint drafting](/docs/screenshots/complaint-mode.jpg)

![Legal analysis](/docs/screenshots/analysis-mode.jpg)

### The Constitution, semantically searchable.

Built on parent-child chunking (Part → Article → Clause → SubClause) with ChromaDB:

![Constitution search](/docs/screenshots/constitution-search.jpg)

---

## 📦 Tech Stack

| Layer | Choice |
|---|---|
| Frontend | React 19 · Vite 7 · TanStack Router + Start (SSR) |
| UI | Tailwind CSS 4 · shadcn/ui · glassmorphism "KaloKoT" design system |
| Backend | Python · FastAPI · Uvicorn |
| Legal RAG | ChromaDB · all-MiniLM-L6-v2 · parent-child chunking |
| LLM | Unified client — **Gemini** · Claude · OpenAI · OpenRouter · local Phi-3, with rate-limit failover |
| Documents | PyMuPDF · fpdf2 (PDF) · python-docx (DOCX) |
| Audio | ElevenLabs text-to-speech (deep voice) |
| Dates | `nepali-datetime` (Bikram Sambat −56y −8m) |
| Deploy | Docker · docker-compose · Nginx · systemd · GitHub Actions |

---

## 🚀 Getting Started

### 1 · Frontend (the app you see)

```bash
cd frontend
npm ci
npm run dev        # → http://localhost:8080
```

In dev, the Vite proxy forwards `/api/*` to the FastAPI backend on `:8000`.

### 2 · Backend (the brain)

```bash
# Create a virtualenv & install dependencies
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Set up environment
cp .env.example .env
# → add at least one LLM API key (Gemini recommended) + optional ElevenLabs key

# Run the API server
.venv/bin/python -m uvicorn src.api:app --port 8000
```

### 3 · One-shot Docker (production shape)

```bash
make docker-build
make docker-up      # serves SSR frontend + FastAPI behind Nitro proxy
```

### 4 · Legacy CLI / Gradio

```bash
# CLI — analyze a single tender, no LLM needed for scoring
.venv/bin/python src/main.py --file ~/Downloads/tender.pdf --no-llm

# Gradio UI (legacy)
.venv/bin/python src/main.py
# → http://127.0.0.1:7860
```

### 5 · Run the tests

```bash
.venv/bin/python -m pytest tests/ -v
```

---

## 🗺️ Architecture

```
                          ┌──────────────────────────────┐
                          │         FRONTEND             │
                          │  React 19 · Vite / SSR       │
                          └───────────────┬──────────────┘
                                          │ /api/*
                          ┌───────────────▼──────────────┐
                          │         FASTAPI :8000        │
                          └───┬─────────────┬────────────┘
         ┌────────────────────▼──┐      ┌───▼─────────────────────┐
         │   TENDER ANALYZER     │      │     DIGITAL LAWYER       │
         │                       │      │                          │
         │  extractor → parser   │      │  jurisdiction resolver   │
         │  → scorer (rule-based)│      │  → legal KB query         │
         │  → reporter (heatmap) │      │  → LLM counsel            │
         └───────────┬───────────┘      │  → drafting (complaints)  │
                     │                   └───┬──────────────────────┘
                     │                       │
              ┌──────▼───────────────────────▼──────┐
              │     LEGAL KNOWLEDGE BASE (YAML)      │
              │  docs/legal/np.yaml · np_constitution │
              └───────────────┬──────────────────────┘
                              │ parent-child RAG
                     ┌────────▼────────────┐
                     │       CHROMADB      │
                     │  (local, in-process)│
                     └─────────────────────┘
```

**The RAG trick:** legal text is chunked hierarchically — Part → Article → Clause → SubClause. ChromaDB matches the small *child* clause, then resolves back to the full *parent* Article before the LLM sees it. No orphaned fragments, ever.

```
docs/
├── README.md
├── PRD.md
├── architecture.md
├── legal/                     # ← the law, as data
│   ├── np.yaml                #   Nepal Public Procurement Act 2063 + Regulations 2064
│   └── np_constitution.yaml   #   Constitution of Nepal 2015
└── screenshots/               # ← this README's images
src/
├── api.py                     # FastAPI app (all /api endpoints)
└── main.py                    # CLI + legacy Gradio UI
    ├── analyzer/              # extraction · parsing · scoring · reporting
    ├── lawyer/                # counsel · jurisprudence · drafting · disclaimers
    └── shared/                # models · LLM · jurisdiction · RAG · PDF · TTS
frontend/
├── src/routes/                # index (4 modes) · constitution · chat · reports
└── src/components/lawyer/     # LowPolyLawyer mascot · Backdrop
tests/                         # pytest suite
```

---

## 🌍 Supported Jurisdictions

| Code | Country | Laws Covered | Oversight |
|---|---|---|---|
| `np` | Nepal | Public Procurement Act 2063 · Regulations 2064 | PPMO, CIAA, OAG |

### Adding a new jurisdiction (≈ a PR)

1. Create `docs/legal/<code>.yaml` following the Nepal structure
2. Add detection signals in `detect_jurisdiction_from_text()` in `src/shared/jurisdiction.py`
3. Register the code in `JurisdictionCode` in `src/shared/models.py`

The knowledge base stays **human-reviewed and versioned** — the LLM reasons over it, never fabricates it.

---

## 🏗️ Operations

| Task | Command |
|---|---|
| Dev UI + API | `make start` |
| Production server | `make prod` |
| Health check | `make health` |
| Docker | `make docker-up` / `make docker-down` |
| systemd service | `make install` / `make uninstall` |
| Logs | `make logs` |
| Backup / restore | `make backup` / `make restore` |

---

## 🤝 Contributing

This is a public-interest tool. Issues, tenders, synthetic test-cases, jurisdiction YAMLs, and UI polish are all welcome.

- **Bug reports & ideas** → open an issue
- **New legal corpus** → see [Adding a new jurisdiction](#-supported-jurisdictions)
- **Code** → fork, branch, PR. Keep the failsafe-citation rule sacred.

Please run the test suite before submitting:

```bash
.venv/bin/python -m pytest tests/ -v
```

---

## 📜 License & Disclaimer

**License:** MIT — see [LICENSE](LICENSE). Use it, fork it, deploy it against your own corruption.

⚠️ **IMPORTANT — NOT LEGAL ADVICE.** KaloKoT is an informational tool, not a law firm, and does not provide legal advice. Laws change, and facts matter. The generated analysis, complaints, and citations are AI-assisted drafts based on a human-reviewed knowledge base — **always consult a qualified attorney licensed in your jurisdiction before taking legal action.**

---

<p align="center">
  <sub>Built with <span style="color:#d4a94e">⚖️</span> by <a href="https://github.com/Astral-Paradigm">Astral Paradigm</a> — for the journalists, the whistleblowers, and the citizens who refuse to look away.</sub>
</p>