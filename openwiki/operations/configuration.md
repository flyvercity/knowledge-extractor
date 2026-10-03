---
type: "Reference"
title: "Configuration"
openwiki_generated: true
verified:
  - by: openwiki/0.6.1
    at: 2026-10-03T09:19:39.759Z
sources:
  - id: openwiki-source-4835a4ac60ade4980988746a
    resource: repo://.env
  - id: openwiki-source-5f5b95b3d6a215fa02ceb945
    resource: repo://.env.example
  - id: openwiki-source-68c9613209e5d75664a12d03
    resource: repo://.pymarkdown.json
  - id: openwiki-source-833e692518af9eeaf8564cc6
    resource: repo://main.py
  - id: openwiki-source-05ccef8d4cf1698187f20464
    resource: repo://pyproject.toml
  - id: openwiki-source-23775c3de52f3ab95a13cb8b
    resource: repo://README.md
  - id: openwiki-source-6819e7dda80c789beeb9df42
    resource: repo://src/knowledge_extractor/ai.py
  - id: openwiki-source-5d7aee63f8f84a40d6294699
    resource: repo://src/knowledge_extractor/cli.py
  - id: openwiki-source-4d65aaccf577d7a55c9644ca
    resource: repo://src/knowledge_extractor/linter.py
  - id: openwiki-source-3da941e00ebf8f0f52469988
    resource: repo://src/knowledge_extractor/logging_setup.py
  - id: openwiki-source-513342bd1eabc42db57c6c41
    resource: repo://src/knowledge_extractor/pipeline.py
  - id: openwiki-source-eb98f79f209f125b1dcb63ae
    resource: repo://tests/test_cli_translate.py
generated: { by: "openwiki/0.6.1", at: "2026-10-03T09:19:39.759Z" }
---


# Configuration

The knowledge extractor is configured primarily at runtime through environment variables and CLI flags. There are no build-time or app-level config files for the pipeline itself; the only project-level configuration files are the `.env` example, the pymarkdown configuration, and the installed dependency set declared in `pyproject.toml`. The entrypoint wiring and Click-based command group are defined in `src/knowledge_extractor/cli.py`, and the environment is loaded with `python-dotenv` at import time.

## Environment Setup

Copy the provided example file to `.env` and add your key:

```bash
cp .env.example .env  # add your OpenRouter API key
```

The example file contains only the key name with a placeholder value:

```text
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

At runtime, `src/knowledge_extractor/cli.py` calls `load_dotenv()` near import time so `.env` values are available before the Click commands run. The extractor reads `OPENROUTER_API_KEY` from the process environment inside `AI**Client**` when it is constructed. If the key is missing, AI-assisted steps are skipped and the extractor still writes raw extractions to the output directory.

## OpenRouter API Key

The extractor authenticates to OpenRouter with a single required credential:

- **Variable:** `OPENROUTER_API_KEY`
- **Source of truth:** environment variable, loaded from `.env` by `python-dotenv`
- **Effect when unset:** `AI**Client**` logs a warning that the key is not set and AI steps will be skipped; the client is created with `client = None`, and downstream methods return `None` or placeholder output instead of calling the API
- **Operational note:** without the key, OCR, image analysis, formula-to-LaTeX conversion, AI cleanup, and translation are all skipped; formula conversion specifically inserts a placeholder such as `[FORMULA: no API key]`

This is the only external authentication credential the extractor needs for its optional AI features.

## Model Selection

Two model flags control which OpenRouter models are used:

- **`--model`** — default `openai/gpt-6-luna` in `src/knowledge_extractor/cli.py`. Used for the primary AI client and for vision/image analysis, OCR, formula conversion, and cleanup.
- **`--translate-model`** — default `mistralai/mistral-large-2512` in `src/knowledge_extractor/cli.py`. Used for translation when `--translate-from` is set. Falls back to `--model` if unset.

The README documents `google/gemini-2.5-flash` as a recommended example value, but the CLI code's `DEFAULT_MODEL` constant is `openai/gpt-6-luna`. The value is passed as the `model` argument when `AIClient` is constructed and later used in every `chat.send(model=...)` call in `src/knowledge_extractor/ai.py`.

Model selection is the main runtime lever for cost, latency, and capability trade-offs. The extractor keeps at most one `AIClient` per distinct model in memory, so a run with both the main model and a separate translation model can maintain two cached clients.

## Translation Configuration

Translation is an optional, opt-in stage controlled by these flags:

- **`--translate-from`** — source language name or code (for example `German` or `de`). If unset, no translation pass runs. The value is sanitized before use: whitespace is stripped, and any control characters including newlines cause `click.BadParameter` to be raised before processing starts.
- **`--translate-model`** — defaults to `mistralai/mistral-large-2512`. Falls back to `--model` when unset.

When `--translate-from` is set, the pipeline runs a dedicated final pass in `src/knowledge_extractor/pipeline.py` that translates the assembled Markdown into English after cleanup and before linting. The pass preserves code blocks, LaTeX, tables, URLs, and Mermaid structure. Translation requires an API key; without one, the original content is kept.

## Logging Setup

Logging is configured once per run by `src/knowledge_extractor/logging_setup.py`. The function `setup_logging(output_dir)` returns a logger named `knowledge_extractor` and configures:

- **Root level:** `DEBUG`
- **Console handler:** `INFO`, with a compact timestamped format using `%H:%M:%S`
- **File handler:** writes to `output/extraction.log` in append mode with UTF-8 encoding, level `DEBUG`, with the same timestamped format

The file handler is created at `output_dir / "extraction.log"`. Console output is mirrored to that file, so the extraction log ends up alongside the final Markdown output. Logging starts after the output directory is created in `_run`, and the logger is passed through the per-file pipeline and the index generation step.

The extractor logs startup information, per-format file counts, pending versus already-processed counts, per-file progress and stage timings, AI usage summaries, lint summaries, and a final summary. If any file fails, the process exits with code 1.

## Temp and Output Layout

The extractor maintains two working directories:

- **`--output`** — default `./output`. Final Markdown files are written here, one per source document, preserving the source folder structure under the output root. The root `index.md` and `manifest.json` are also generated here.
- **`--temp`** — default `./temp`. Intermediate Markdown with original image references and debug artifacts are saved here. Temp is also removed by the `clear` subcommand unless `--all` is used.

Both directories are created with `mkdir(parents=True, exist_ok=True)` at the start of a run. The temp directory holds intermediate artifacts such as extracted Markdown before AI post-processing, while the output directory holds the final cleaned results and the generated index.

## Incremental Processing

The `convert` command skips a source file if its output Markdown already exists. After discovery, the pipeline computes `pending = [f for f in files if not output_path(f).exists()]` and logs the pending count plus how many were already processed. This means that deleting the output file, the output directory, or running `clear` is the primary way to force re-processing.

When `--translate-from` is set and some files are skipped because their output already exists, a warning is logged because existing outputs are not re-translated.

## Linter Configuration

Markdown linting is performed by `pymarkdownlnt` for files at or below 512 KB and by a fast regex-based fixer for larger files. The project ships a `.pymarkdown.json` configuration that disables several plugins and enables markdown-table support:

```json
{
  "plugins": {
    "md013": { "enabled": false },
    "md024": { "enabled": false },
    "md025": { "enabled": false },
    "md033": { "enabled": false },
    "md041": { "enabled": false }
  },
  "extensions": {
    "markdown-tables": { "enabled": true }
  }
}
```

This configuration informs the auto-fix step that runs after each file is written to the output directory.

## Dependency and Entrypoint Wiring

The extractor's runtime surface is defined by `pyproject.toml`. Key points:

- **Dependencies:** `click`, `openrouter`, `python-docx`, `python-pptx`, `openpyxl`, `pymupdf`, `Pillow`, `python-dotenv`, `lxml`, and `pymarkdownlnt`
- **Scripts:** `knowledge-extractor` → `knowledge_extractor.cli:main`, and `convert` → `knowledge_extractor.cli:convert_main`
- **Environment loading:** `python-dotenv` is used to load `.env` at import time in `src/knowledge_extractor/cli.py`

The repository also has a small `main.py` wrapper at the root that inserts `src/` onto `sys.path` and calls `main()`, which is one supported way to invoke the tool without the `uv run` entrypoint forms.

## Related Pages

- [AI Client](../architecture/ai-client.md) — the `AIClient` wrapper around OpenRouter, retry behavior, and the operations behind OCR, image analysis, formula conversion, cleanup, and translation
- [CLI Reference](../operations/cli-reference.md) — command group, flag defaults, entrypoints, and per-file pipeline stages
