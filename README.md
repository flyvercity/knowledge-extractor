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
| `--translate-from` | (unset) | Translate the output into English from this source language (e.g. `German`, `de`). If unset, no translation is performed. |
| `--translate-model` | `mistralai/mistral-large-2512` | Model used for translation (text-only). Falls back to `--model` if unset. |
| `--dry-run` | `false` | List which files would be processed and which would be skipped, then exit without processing |

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENROUTER_API_KEY` | OpenRouter API key. If not set, AI steps are skipped and raw extractions are output. |

## Features

- **Incremental processing** — skips a source file if its output Markdown already exists; delete the output file (or the output dir) to re-run
- **Intermediate results** — per-file markdown with original image references saved to temp dir
- **AI image analysis** — converts diagrams to Mermaid, charts to descriptions (requires API key)
- **OCR for scanned PDFs** — auto-detects scanned/image-only PDFs and extracts text via AI vision OCR (requires API key)
- **LaTeX formula extraction** — detects mathematical formulas in DOCX/PPTX (OMML) and PDF (heuristic font/character analysis), converts to LaTeX via AI vision. Inline formulas wrapped with `$...$`, display formulas with `$$...$$`. Requires API key; without it, a placeholder is inserted.
- **Heuristic filtering** — removes title slides, logo-only sections, repeated headers
- **Translation to English** — with `--translate-from <language>`, a dedicated final pass translates the assembled Markdown into English after cleanup (before linting), preserving code blocks, LaTeX, tables, URLs, and Mermaid structure. Uses `--translate-model` (defaults to a text model, falls back to `--model`). Requires an API key; without one, translation is skipped and the original content is kept. Incremental skip still applies — pre-existing outputs are **not** re-translated (a warning is logged when files are skipped while `--translate-from` is set); delete the outputs or run `clear` to re-translate.
- **Markdown linting** — auto-fixes formatting issues (trailing spaces, heading spacing, list indentation) via pymarkdownlnt
- **Logging** — console output + `output/extraction.log`

## Output

- `output/index.md` — flat index grouped by original folder structure
- `output/**/*.md` — one Markdown file per source document
