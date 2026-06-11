<<<<<<< HEAD
# Justice System

A comprehensive justice system implementation.

## Overview

This project provides tools and utilities for managing justice system operations and workflows.

## Getting Started

### Prerequisites

- Git
- Your system's standard development tools

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Astral-Paradigm/Justice_system.git
   cd Justice_system
   ```

2. Follow any setup instructions specific to your development environment.

## Usage

For detailed information on how to use this project, please refer to the documentation in the repository.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

Please refer to the LICENSE file for licensing information.

## Support

For issues or questions, please open an issue on GitHub.
=======
# 🛡️ OpenTender + Counsel

**Procurement corruption risk analyzer + Virtual Lawyer**

Upload a government tender document, get a corruption-risk heatmap with traffic-light scores, then chat with a Virtual Lawyer who tells you exactly which laws are being violated, how to report it, and how to draft a complaint.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set API key (Gemini recommended — supports structured JSON output)
cp .env.example .env
# Edit .env with your API key

# 3. Run
python src/main.py
```

Opens a Gradio UI at http://127.0.0.1:7860

### CLI Mode

```bash
# Analyze a tender PDF directly
python src/main.py --file ~/Downloads/tender.pdf

# Rule-based only (no LLM needed for scoring)
python src/main.py --file tender.pdf --no-llm
```

## Architecture

```
src/
├── main.py              ← Entry point (Gradio UI + CLI)
├── analyzer/
│   ├── extractor.py     ← PDF/URL text extraction
│   ├── parser.py        ← LLM-based tender structure extraction
│   ├── scorer.py        ← Corruption risk scoring engine
│   └── reporter.py      ← HTML/text/heatmap report generation
├── lawyer/
│   ├── counsel.py       ← Virtual Lawyer engine
│   ├── jurisprudence.py ← Legal knowledge base query
│   ├── drafting.py      ← Complaint/RTI draft generator
│   └── disclaimers.py   ← Jurisdiction-specific disclaimers
└── shared/
    ├── models.py        ← Pydantic data models
    ├── llm.py           ← LLM client (Gemini / Anthropic / OpenRouter)
    └── jurisdiction.py  ← YAML legal corpus loader

docs/
└── legal/
    └── np.yaml          ← Nepal procurement law corpus
```

## How It Works

1. **Upload** a PDF tender or paste a URL
2. **Analyzer** extracts text, parses sections, scores red flags (timeline, specs, budget, evaluation, emergency procurement, conflict of interest)
3. **Risk Report** shows per-section scores + overall traffic light (Green/Yellow/Red)
4. **Virtual Lawyer** — chat with an AI that knows procurement law for your jurisdiction
   - Cites specific laws and sections
   - Identifies the right oversight body (KPK, CIAA, BPKP, PPMO, LKPP)
   - Drafts complaint letters, RTI/FOIA requests, whistleblower reports
   - Assesses personal risk and recommends safe reporting channels

## Supported Jurisdictions

| Code | Country | Laws Covered | Oversight Bodies |
|------|---------|--------------|------------------|
| `np` | Nepal | Public Procurement Act 2063, Regulations 2064 | PPMO, CIAA, OAG |

## Key Design Features

- **Local-first:** No server-side data storage. PDFs processed in memory.
- **Rule-based scoring:** No LLM needed for the red-flag analysis. All patterns hardcoded in `scorer.py`.
- **Jurisdiction as data:** Legal knowledge in YAML files — easy to add new countries via PR.
- **Failsafe citations:** Lawyer never fabricates laws. If the KB doesn't cover it, it says so.

## Adding a New Jurisdiction

1. Create `docs/legal/<code>.yaml` following the Nepal structure
2. Add detection signals in `detect_jurisdiction_from_text()` in `shared/jurisdiction.py`
3. Add `JurisdictionCode` enum entry in `shared/models.py`

## Disclaimer

⚠️ **This is NOT a law firm. This AI does not provide legal advice.**

The Virtual Lawyer is an informational tool. It uses a knowledge base of procurement laws and an LLM to generate guidance. Laws change. Facts matter. Always consult a qualified attorney licensed in your jurisdiction before taking legal action.
>>>>>>> 7541619 (Initial commit)
