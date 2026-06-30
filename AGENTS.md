# AGENTS.md

## Project

Knowledge Extractor — CLI tool to convert document file trees into AI-agent-accessible Markdown.

## Architecture

```
src/knowledge_extractor/
├── cli.py              # Entry point, argparse, batch orchestration
├── discovery.py        # Recursive file walker, format filtering
├── tracker.py          # JSON-based resume/progress tracking
├── logging_setup.py    # Dual console + file logging
├── filters.py          # Heuristic boilerplate removal
├── ai.py               # OpenRouter client (vision + cleanup + formula conversion)
├── pipeline.py         # Per-file processing orchestration
├── index.py            # Flat index.md generation
├── formulas/
│   ├── __init__.py         # Shared types (FormulaRef, FormulaRegion, ExtractionResult)
│   ├── docx_formulas.py    # OMML detection in DOCX
│   ├── pptx_formulas.py    # OMML detection in PPTX
│   ├── pdf_formulas.py     # Heuristic math region detection in PDF
│   └── renderer.py         # PDF formula region → PNG cropping
└── extractors/
    ├── docx_extractor.py
    ├── pptx_extractor.py
    ├── excel_extractor.py
    ├── pdf_extractor.py
    └── image_extractor.py
```

## Key Decisions

- OpenRouter API via `openrouter` SDK; default model: `google/gemini-2.5-flash`
- Sequential processing (no concurrency) for simplicity and rate-limit safety
- Resume via `temp/progress.json` keyed on relative path + mtime
- AI gracefully skipped when `OPENROUTER_API_KEY` not set
- External image relationships in docx and linked images in pptx are skipped (not embedded)
- Formula detection: DOCX/PPTX use OMML XML parsing, PDF uses heuristic font/character analysis
- Formula conversion always via AI vision (no offline OMML→LaTeX library)
- Formula markers (`<<FORMULA:idx>>`) in intermediate output, replaced by LaTeX or placeholder in pipeline

## Dependencies

openrouter, python-docx, python-pptx, openpyxl, pymupdf, Pillow, lxml

## Tested

- 233 files (110 docx, 31 pptx, 43 xlsx, 42 pdf, 7 images), 0 failures, ~66s without AI
- Resume verified: second run skips all files instantly
