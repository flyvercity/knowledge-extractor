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
# Using the `convert` script (recommended)
uv run convert --input ./input --output ./output --temp ./temp --model google/gemini-2.5-flash

# Equivalent forms via the command group
uv run knowledge-extractor convert --input ./input --output ./output
uv run python main.py --input ./input --output ./output   # subcommand optional; defaults to `convert`
```

Other subcommands: `convert` (extract, the default), `clear` (remove temp/output dirs), `lint` (re-lint markdown), `reindex` (rebuild the root index/manifest across all subfolders).

```bash
# Rebuild a single root index/manifest across all subfolders (e.g. after joining vaults)
uv run knowledge-extractor reindex --output ./output
uv run knowledge-extractor reindex --output ./output --keep-nested
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

## Joining Vaults (`reindex`)

The `reindex` command rebuilds a single root `index.md` + `manifest.json` for an output
directory purely from the Markdown already on disk — no extraction, no AI, no linting.
This is useful after **joining multiple vaults**: copy the per-document subfolders of
several output directories into one combined directory, then run `reindex` to produce one
unified index/manifest covering every subfolder.

```bash
uv run knowledge-extractor reindex --output ./output
uv run knowledge-extractor reindex --output ./output --keep-nested
```

- `--output` defaults to `./output`.
- By default, `reindex` removes nested `index.md`/`manifest.json` files found in
  **subdirectories**, but **only** when they are verified extractor-generated artifacts
  (a nested `index.md` must start with `# Knowledge Index`; a nested `manifest.json` must
  be a JSON array of entries carrying `path`/`title`/`group`). User-content `index.md`
  files (e.g. Obsidian folder notes, Hugo/Docusaurus/MkDocs index pages) are **preserved**
  and logged. The root-level pair is always regenerated.
- `--keep-nested` opts out of removal entirely, leaving all nested artifacts in place.
- Files inside hidden directories (any path component starting with `.`, e.g. `.git`,
  `.obsidian`) are neither indexed nor removed.
- **Avoiding collisions**: place each joined vault under a **distinct parent folder**
  inside the combined directory (e.g. `combined/VaultA/`, `combined/VaultB/`). Documents
  with identical relative paths would otherwise silently overwrite each other on the
  filesystem before `reindex` runs.
