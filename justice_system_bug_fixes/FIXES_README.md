# Justice System Bug Fixes

## What was fixed
All 25 bugs from the original audit, plus 3 newly discovered issues.

## How to apply
1. Backup your existing files
2. Extract this zip to your project root (overwriting existing files)
3. Install new dependency: `pip install slowapi` (for rate limiting)
4. Restart your application

## Files included
- docs/legal/np.yaml — Added pep_indicators section
- src/analyzer/vendor_intel.py — Dynamic PEP loading from YAML
- src/main.py — Logging, image OCR, evidence checklist, constitution context
- src/api.py — Rate limiting on all endpoints, logging
- src/shared/chroma_store.py — Graceful shutdown, logging
- docker-compose.yml — Removed deprecated version
- src/analyzer/extractor.py — Image OCR support
- src/analyzer/reporter.py — Verified HTML escaping

## Verification
Run: python -m pytest tests/ -v
