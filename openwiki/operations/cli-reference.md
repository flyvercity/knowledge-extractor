---
type: "Reference"
title: "CLI Reference"
openwiki_generated: true
verified:
  - by: openwiki/0.6.1
    at: 2026-10-03T09:19:39.759Z
sources:
  - id: openwiki-source-05ccef8d4cf1698187f20464
    resource: repo://pyproject.toml
  - id: openwiki-source-5d7aee63f8f84a40d6294699
    resource: repo://src/knowledge_extractor/cli.py
  - id: openwiki-source-3b8797ab19660e7c8ac5d542
    resource: repo://src/knowledge_extractor/discovery.py
  - id: openwiki-source-78ff1e85f34a0ebe28e4561b
    resource: repo://src/knowledge_extractor/index.py
  - id: openwiki-source-4d65aaccf577d7a55c9644ca
    resource: repo://src/knowledge_extractor/linter.py
  - id: openwiki-source-513342bd1eabc42db57c6c41
    resource: repo://src/knowledge_extractor/pipeline.py
generated: { by: "openwiki/0.6.1", at: "2026-10-03T09:19:39.759Z" }
---


# CLI Reference

<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../pyproject.toml] file "../pyproject.toml" does not exist. Fix the href or restore the target, then delete this comment. -->
The knowledge extractor is a Click-based CLI defined in [src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py). It ships two installable entry points ([pyproject.toml](../pyproject.toml)):

- `knowledge-extractor` → `knowledge_extractor.cli:main`
- `convert` → `knowledge_extractor.cli:convert_main`

<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
Both entry points share the same command group. The group is configured with a custom `_DefaultGroup` class and `default_command="convert"`, so invoking the tool with no subcommand still runs the extraction pipeline as long as the first argument is not a known subcommand or a group-level help flag ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)).

## Commands

### `convert` (default)

<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../README.md] file "../README.md" does not exist. Fix the href or restore the target, then delete this comment. -->
Extracts knowledge from the input directory. This is the default command and the primary workflow ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py), [README.md](../README.md)).

```bash
# Recommended form via the `convert` script
uv run convert --input ./input --output ./output --temp ./temp --model google/gemini-2.5-flash

# Equivalent forms via the command group
uv run knowledge-extractor convert --input ./input --output ./output
uv run python main.py --input ./input --output ./output   # subcommand optional; defaults to `convert`
```

### `clear`

<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
Removes the temp directory and optionally the output directory ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)).

```bash
uv run knowledge-extractor clear              # removes temp only
uv run knowledge-extractor clear --all       # also removes output
```

<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
The command lists the directories it will remove, then prompts for confirmation (default: no). Existing directories are removed with `shutil.rmtree(ignore_errors=True)`; if a directory still exists after removal (some files locked), a "Partially removed" message is logged ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)).

### `lint`

<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../src/knowledge_extractor/linter.py] file "../src/knowledge_extractor/linter.py" does not exist. Fix the href or restore the target, then delete this comment. -->
Re-lints all Markdown files in a given directory ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py), [src/knowledge_extractor/linter.py](../src/knowledge_extractor/linter.py)).

```bash
uv run knowledge-extractor lint ./output
```

<!-- openwiki: broken internal link [../src/knowledge_extractor/linter.py] file "../src/knowledge_extractor/linter.py" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
The directory is a required positional argument. Linting uses pymarkdownlnt for files at or below 512 KB and a fast regex-based fixer for larger files ([src/knowledge_extractor/linter.py](../src/knowledge_extractor/linter.py)). The command reports per-file results and a summary: total fixes applied, files with fixes, and remaining unfixed issues ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)).

### `reindex`

<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../README.md] file "../README.md" does not exist. Fix the href or restore the target, then delete this comment. -->
Rebuilds a single root `index.md` + `manifest.json` for an output directory purely from the Markdown already on disk — no extraction, no AI, no linting ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py), [README.md](../README.md)).

```bash
uv run knowledge-extractor reindex ./output
uv run knowledge-extractor reindex ./output --keep-nested
```

<!-- openwiki: broken internal link [../README.md] file "../README.md" does not exist. Fix the href or restore the target, then delete this comment. -->
This is the primary operation after **joining multiple vaults**: copy the per-document subfolders of several output directories into one combined directory, then run `reindex` to produce one unified index/manifest covering every subfolder ([README.md](../README.md)).

## `convert` Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--input` | (required) | Input directory with source documents |
| `--output` | `./output` | Output directory for final Markdown files |
| `--temp` | `./temp` | Intermediate data directory (debug artifacts) |
<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
| `--model` | `openai/gpt-6-luna` | OpenRouter vision model for image analysis. **Note:** the README lists `google/gemini-2.5-flash` as the documented default, but the CLI code defines `DEFAULT_MODEL = "openai/gpt-6-luna"` ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)). |
<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
| `--translate-from` | (unset) | Translate the output into English from this source language (e.g. `German`, `de`). If unset, no translation is performed. The value is sanitized before use — control characters and newlines cause a `click.BadParameter` error ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)). |
<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
| `--translate-model` | `mistralai/mistral-large-2512` | Model used for translation (text-only). Falls back to `--model` if unset ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)). |
<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
| `--dry-run` | `false` | List which files would be processed and which would be skipped, then exit without processing ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)). |

## Environment Variables

| Variable | Description |
|----------|-------------|
<!-- openwiki: broken internal link [../.env.example] file "../.env.example" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../README.md] file "../README.md" does not exist. Fix the href or restore the target, then delete this comment. -->
| `OPENROUTER_API_KEY` | OpenRouter API key. If not set, AI steps are skipped and raw extractions are output ([.env.example](../.env.example), [README.md](../README.md)). |

<!-- openwiki: broken internal link [../README.md] file "../README.md" does not exist. Fix the href or restore the target, then delete this comment. -->
Set the key by copying `.env.example` to `.env` and adding your key ([README.md](../README.md)):

```bash
cp .env.example .env  # add your OpenRouter API key
```

## Incremental Processing

<!-- openwiki: broken internal link [../README.md] file "../README.md" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
The `convert` command skips a source file if its output Markdown already exists ([README.md](../README.md), [src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)). This behavior is visible in the logging:

<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
- After discovery, the pipeline computes `pending = [f for f in files if not output_path(f).exists()]` and logs the pending count plus how many were already processed ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)).
<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../README.md] file "../README.md" does not exist. Fix the href or restore the target, then delete this comment. -->
- When `--translate-from` is set and some files are skipped because their output already exists, a warning is logged: existing outputs are **not** re-translated. Delete the output file(s)/directory or run `clear` to re-translate ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py), [README.md](../README.md)).

<!-- openwiki: broken internal link [../README.md] file "../README.md" does not exist. Fix the href or restore the target, then delete this comment. -->
To force re-processing, delete the output file or the output directory, or run `clear` ([README.md](../README.md)).

## Translation Caveats

<!-- openwiki: broken internal link [../README.md] file "../README.md" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../src/knowledge_extractor/pipeline.py] file "../src/knowledge_extractor/pipeline.py" does not exist. Fix the href or restore the target, then delete this comment. -->
The `--translate-from` flag triggers a dedicated final pass that translates the assembled Markdown into English after cleanup and before linting ([README.md](../README.md), [src/knowledge_extractor/pipeline.py](../src/knowledge_extractor/pipeline.py)). The translation pass:

<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../src/knowledge_extractor/pipeline.py] file "../src/knowledge_extractor/pipeline.py" does not exist. Fix the href or restore the target, then delete this comment. -->
- Uses `--translate-model` (defaults to `mistralai/mistral-large-2512`), falling back to `--model` if unset ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py), [src/knowledge_extractor/pipeline.py](../src/knowledge_extractor/pipeline.py)).
<!-- openwiki: broken internal link [../README.md] file "../README.md" does not exist. Fix the href or restore the target, then delete this comment. -->
- Preserves code blocks, LaTeX, tables, URLs, and Mermaid structure ([README.md](../README.md)).
<!-- openwiki: broken internal link [../README.md] file "../README.md" does not exist. Fix the href or restore the target, then delete this comment. -->
- Requires an API key; without one, translation is skipped and the original content is kept ([README.md](../README.md)).
<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../README.md] file "../README.md" does not exist. Fix the href or restore the target, then delete this comment. -->
- Is subject to incremental skip: pre-existing outputs are **not** re-translated. When files are skipped while `--translate-from` is set, a warning is logged ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py), [README.md](../README.md)).

## `dry-run` Mode

<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
When `--dry-run` is set, the pipeline logs what would happen and exits without processing ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)):

- "Would process" lists files whose output does not yet exist.
- "Would skip" lists files whose output already exists.

This is useful for previewing the scope of a run before committing to it.

## Processing Pipeline (per file)

<!-- openwiki: broken internal link [../src/knowledge_extractor/pipeline.py] file "../src/knowledge_extractor/pipeline.py" does not exist. Fix the href or restore the target, then delete this comment. -->
When not in dry-run mode, each pending file goes through a staged pipeline ([src/knowledge_extractor/pipeline.py](../src/knowledge_extractor/pipeline.py)):

<!-- openwiki: broken internal link [../src/knowledge_extractor/pipeline.py] file "../src/knowledge_extractor/pipeline.py" does not exist. Fix the href or restore the target, then delete this comment. -->
1. **Extract** — the format-specific extractor (`docx`, `pptx`, `xlsx`, `pdf`, `image`) runs against the source file, returning either a `str` or an `ExtractionResult`. Strings are wrapped as `ExtractionResult(markdown=result, formulas=[])` ([src/knowledge_extractor/pipeline.py](../src/knowledge_extractor/pipeline.py)). Intermediate Markdown is saved to the temp directory.
<!-- openwiki: broken internal link [../src/knowledge_extractor/pipeline.py] file "../src/knowledge_extractor/pipeline.py" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../README.md] file "../README.md" does not exist. Fix the href or restore the target, then delete this comment. -->
2. **Formulas** — formula markers are converted to LaTeX via AI. Inline formulas are wrapped with `$...$`, display formulas with `$$...$$`. Without an API key, a placeholder is inserted ([src/knowledge_extractor/pipeline.py](../src/knowledge_extractor/pipeline.py), [README.md](../README.md)).
<!-- openwiki: broken internal link [../src/knowledge_extractor/pipeline.py] file "../src/knowledge_extractor/pipeline.py" does not exist. Fix the href or restore the target, then delete this comment. -->
3. **OCR** — scanned/image-only PDFs are OCR'd via AI vision before filtering ([src/knowledge_extractor/pipeline.py](../src/knowledge_extractor/pipeline.py)).
<!-- openwiki: broken internal link [../src/knowledge_extractor/pipeline.py] file "../src/knowledge_extractor/pipeline.py" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../README.md] file "../README.md" does not exist. Fix the href or restore the target, then delete this comment. -->
4. **Heuristic filter** — title slides, logo-only sections, and repeated headers are removed ([src/knowledge_extractor/pipeline.py](../src/knowledge_extractor/pipeline.py), [README.md](../README.md)).
<!-- openwiki: broken internal link [../src/knowledge_extractor/pipeline.py] file "../src/knowledge_extractor/pipeline.py" does not exist. Fix the href or restore the target, then delete this comment. -->
5. **AI image analysis** — image references are replaced with text descriptions or Mermaid diagrams ([src/knowledge_extractor/pipeline.py](../src/knowledge_extractor/pipeline.py)).
<!-- openwiki: broken internal link [../src/knowledge_extractor/pipeline.py] file "../src/knowledge_extractor/pipeline.py" does not exist. Fix the href or restore the target, then delete this comment. -->
6. **AI cleanup** — skipped for scanned PDFs (OCR output is used directly) ([src/knowledge_extractor/pipeline.py](../src/knowledge_extractor/pipeline.py)).
<!-- openwiki: broken internal link [../src/knowledge_extractor/pipeline.py] file "../src/knowledge_extractor/pipeline.py" does not exist. Fix the href or restore the target, then delete this comment. -->
7. **AI translation** (optional) — when `--translate-from` is set ([src/knowledge_extractor/pipeline.py](../src/knowledge_extractor/pipeline.py)).
8. **Write final output** — the processed Markdown is written to the output directory.
<!-- openwiki: broken internal link [../src/knowledge_extractor/pipeline.py] file "../src/knowledge_extractor/pipeline.py" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../src/knowledge_extractor/linter.py] file "../src/knowledge_extractor/linter.py" does not exist. Fix the href or restore the target, then delete this comment. -->
9. **Markdown lint** — auto-fixes formatting issues via pymarkdownlnt ([src/knowledge_extractor/pipeline.py](../src/knowledge_extractor/pipeline.py), [src/knowledge_extractor/linter.py](../src/knowledge_extractor/linter.py)).

<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../src/knowledge_extractor/index.py] file "../src/knowledge_extractor/index.py" does not exist. Fix the href or restore the target, then delete this comment. -->
After all files are processed, `generate_index` rebuilds the root `index.md` and `manifest.json` ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py), [src/knowledge_extractor/index.py](../src/knowledge_extractor/index.py)).

## Output Structure

<!-- openwiki: broken internal link [../README.md] file "../README.md" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../src/knowledge_extractor/index.py] file "../src/knowledge_extractor/index.py" does not exist. Fix the href or restore the target, then delete this comment. -->
- `output/index.md` — flat index grouped by original folder structure ([README.md](../README.md), [src/knowledge_extractor/index.py](../src/knowledge_extractor/index.py)).
<!-- openwiki: broken internal link [../README.md] file "../README.md" does not exist. Fix the href or restore the target, then delete this comment. -->
- `output/**/*.md` — one Markdown file per source document ([README.md](../README.md)).
<!-- openwiki: broken internal link [../src/knowledge_extractor/index.py] file "../src/knowledge_extractor/index.py" does not exist. Fix the href or restore the target, then delete this comment. -->
- `output/manifest.json` — JSON array of entries carrying `path`, `title`, `group`, `headings`, and `word_count` ([src/knowledge_extractor/index.py](../src/knowledge_extractor/index.py)).
<!-- openwiki: broken internal link [../README.md] file "../README.md" does not exist. Fix the href or restore the target, then delete this comment. -->
- `output/extraction.log` — console output is mirrored to this log file ([README.md](../README.md)).

## Reindex Behavior

<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../src/knowledge_extractor/index.py] file "../src/knowledge_extractor/index.py" does not exist. Fix the href or restore the target, then delete this comment. -->
`reindex` regenerates the root `index.md` and `manifest.json` from Markdown already on disk ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py), [src/knowledge_extractor/index.py](../src/knowledge_extractor/index.py)).

By default, `reindex` removes nested `index.md`/`manifest.json` files found in **subdirectories**, but **only** when they are verified extractor-generated artifacts:

<!-- openwiki: broken internal link [../src/knowledge_extractor/index.py] file "../src/knowledge_extractor/index.py" does not exist. Fix the href or restore the target, then delete this comment. -->
- A nested `index.md` must start with `# Knowledge Index` ([src/knowledge_extractor/index.py](../src/knowledge_extractor/index.py)).
<!-- openwiki: broken internal link [../src/knowledge_extractor/index.py] file "../src/knowledge_extractor/index.py" does not exist. Fix the href or restore the target, then delete this comment. -->
- A nested `manifest.json` must be a JSON array of entries carrying `path`/`title`/`group` ([src/knowledge_extractor/index.py](../src/knowledge_extractor/index.py)).

<!-- openwiki: broken internal link [../src/knowledge_extractor/index.py] file "../src/knowledge_extractor/index.py" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../README.md] file "../README.md" does not exist. Fix the href or restore the target, then delete this comment. -->
User-content `index.md` files (e.g. Obsidian folder notes, Hugo/Docusaurus/MkDocs index pages) are **preserved** and logged at warning level ([src/knowledge_extractor/index.py](../src/knowledge_extractor/index.py), [README.md](../README.md)). The root-level pair is always regenerated.

<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../README.md] file "../README.md" does not exist. Fix the href or restore the target, then delete this comment. -->
- `--keep-nested` opts out of removal entirely, leaving all nested artifacts in place ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py), [README.md](../README.md)).
<!-- openwiki: broken internal link [../src/knowledge_extractor/index.py] file "../src/knowledge_extractor/index.py" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../README.md] file "../README.md" does not exist. Fix the href or restore the target, then delete this comment. -->
- Files inside hidden directories (any path component starting with `.`, e.g. `.git`, `.obsidian`) are neither indexed nor removed ([src/knowledge_extractor/index.py](../src/knowledge_extractor/index.py), [README.md](../README.md)).

<!-- openwiki: broken internal link [../README.md] file "../README.md" does not exist. Fix the href or restore the target, then delete this comment. -->
**Avoiding collisions**: place each joined vault under a **distinct parent folder** inside the combined directory (e.g. `combined/VaultA/`, `combined/VaultB/`). Documents with identical relative paths would otherwise silently overwrite each other on the filesystem before `reindex` runs ([README.md](../README.md)).

## Logging

<!-- openwiki: broken internal link [../README.md] file "../README.md" does not exist. Fix the href or restore the target, then delete this comment. -->
Console output is mirrored to `output/extraction.log` ([README.md](../README.md)). The log includes:

<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
- Startup information: input, output, temp, model, and (if set) translation configuration ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)).
<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
- Per-format file counts after discovery ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)).
<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
- Pending vs already-processed counts ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)).
<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../src/knowledge_extractor/pipeline.py] file "../src/knowledge_extractor/pipeline.py" does not exist. Fix the href or restore the target, then delete this comment. -->
- Per-file progress and stage timings ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py), [src/knowledge_extractor/pipeline.py](../src/knowledge_extractor/pipeline.py)).
<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
- AI usage summary (one per distinct model, e.g. main + translation) ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)).
<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
- Lint summary ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)).
<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
- Final summary: processed, skipped, failed counts and elapsed time ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)).

<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
If any file fails, the process exits with code 1 ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)).

## Error Handling

<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
- **AI provider unavailable**: if an `AIProviderError` is raised during processing, the pipeline logs the error and aborts — no further files are processed ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)).
<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
- **Per-file failures**: other exceptions are caught per-file, logged with traceback, and the pipeline continues. The failed count is included in the final summary ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)).
<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
- **`--translate-from` validation**: if the value contains control characters or newlines, `click.BadParameter` is raised before any processing begins ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)).

## Supported Formats

<!-- openwiki: broken internal link [../README.md] file "../README.md" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../src/knowledge_extractor/discovery.py] file "../src/knowledge_extractor/discovery.py" does not exist. Fix the href or restore the target, then delete this comment. -->
The CLI discovers and extracts from ([README.md](../README.md), [src/knowledge_extractor/discovery.py](../src/knowledge_extractor/discovery.py)):

- Microsoft Word (`.docx`)
- Microsoft PowerPoint (`.pptx`)
- Microsoft Excel (`.xlsx`)
- PDF (`.pdf`)
- Images (`.jpg`, `.jpeg`, `.png`)

<!-- openwiki: broken internal link [../src/knowledge_extractor/discovery.py] file "../src/knowledge_extractor/discovery.py" does not exist. Fix the href or restore the target, then delete this comment. -->
Discovery skips `.git` directories and only yields files whose lowercased suffix is in the `SUPPORTED` set ([src/knowledge_extractor/discovery.py](../src/knowledge_extractor/discovery.py)).

## Entry Points and Script Invocation

<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../main.py] file "../main.py" does not exist. Fix the href or restore the target, then delete this comment. -->
The `convert` script entry point (`convert_main`) enables `uv run convert <options>` without needing to type the subcommand ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)). The `main.py` wrapper at the repository root inserts the `src` directory onto `sys.path` and calls `main()` ([main.py](../main.py)).

## See Also

- [Architecture Overview](../architecture/overview.md) — entrypoints, file discovery, per-format extractors, AI-assisted post-processing, linting, and index generation.
- [AI Client](../architecture/ai-client.md) — the AI client wrapper, retry behavior, and the operations that back image analysis, OCR, formula conversion, cleanup, and translation.
- [Formulas Concept](../concepts/formulas.md) — formula detection, marker replacement, and LaTeX conversion.
