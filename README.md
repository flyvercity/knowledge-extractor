# Knowledge Extractor

Extracts agent-accessible knowledge from document file trees into clean Markdown.

## Supported Formats

- Microsoft Word (.docx)
- Microsoft PowerPoint (.pptx)
- Microsoft Excel (.xlsx)
- PDF (.pdf)
- Images (.jpg, .jpeg, .png)

## Setup

```bash
uv sync
cp .env.example .env  # add your OpenRouter API key
```

## Usage

```bash
uv run python main.py --input ./input --output ./output --temp ./temp --model google/gemini-2.5-flash
```

### Parameters

| Flag | Default | Description |
|------|---------|-------------|
| `--input` | (required) | Input directory with source documents |
| `--output` | `./output` | Output directory for final Markdown files |
| `--temp` | `./temp` | Intermediate data directory (debug artifacts) |
| `--model` | `google/gemini-2.5-flash` | OpenRouter vision model for image analysis |

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENROUTER_API_KEY` | OpenRouter API key. If not set, AI steps are skipped and raw extractions are output. |

## Features

- **Incremental processing** — tracks completed files in `temp/progress.json`, skips on re-run
- **Intermediate results** — per-file markdown with original image references saved to temp dir
- **AI image analysis** — converts diagrams to Mermaid, charts to descriptions (requires API key)
- **OCR for scanned PDFs** — auto-detects scanned/image-only PDFs and extracts text via AI vision OCR (requires API key)
- **LaTeX formula extraction** — detects mathematical formulas in DOCX/PPTX (OMML) and PDF (heuristic font/character analysis), converts to LaTeX via AI vision. Inline formulas wrapped with `$...$`, display formulas with `$$...$$`. Requires API key; without it, a placeholder is inserted.
- **Heuristic filtering** — removes title slides, logo-only sections, repeated headers
- **Markdown linting** — auto-fixes formatting issues (trailing spaces, heading spacing, list indentation) via pymarkdownlnt
- **Logging** — console output + `output/extraction.log`

## Output

- `output/index.md` — flat index grouped by original folder structure
- `output/**/*.md` — one Markdown file per source document
