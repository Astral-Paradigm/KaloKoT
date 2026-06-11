# Sample Tender Files

These are dummy/synthetic tender documents for development and testing.
They are not real government tenders. Each file embeds specific corruption
indicators for testing the analyzer's red-flag detection.

## Files

| File | Description | Red Flags |
|------|-------------|-----------|
| `nepal_road_construction.txt` | Road construction tender with multiple red flags | Insufficient timeline, tailored specs, budget inflation |
| `nepal_clean_water.txt` | Clean water supply tender — compliant | None |
| `nepal_emergency_procurement.txt` | Emergency procurement used for routine goods | Emergency abuse, contract splitting |

## Usage

These text files can be passed directly to the CLI analyzer:

```bash
python src/main.py --file data/sample_tenders/nepal_road_construction.txt
```

For PDF pipeline testing, run `python generate_sample_pdfs.py` to convert
these to PDF format (requires fpdf2 or PyMuPDF).
