---
type: testing strategy
title: Test Strategy
description: Describes the test layout and what is covered by unit tests around CLI parsing, reindex, index generation, pipeline translation, and AI client chunking/translation behavior.
tags: [testing, cli, index, pipeline, ai]
verified:
  - by: openwiki/0.6.1
    at: 2026-10-03T09:19:39.759Z
sources:
  - id: openwiki-source-6819e7dda80c789beeb9df42
    resource: repo://src/knowledge_extractor/ai.py
  - id: openwiki-source-5d7aee63f8f84a40d6294699
    resource: repo://src/knowledge_extractor/cli.py
  - id: openwiki-source-78ff1e85f34a0ebe28e4561b
    resource: repo://src/knowledge_extractor/index.py
  - id: openwiki-source-513342bd1eabc42db57c6c41
    resource: repo://src/knowledge_extractor/pipeline.py
  - id: openwiki-source-f3f149d5b221aaeeee1055d5
    resource: repo://tests/test_cli_reindex.py
  - id: openwiki-source-eb98f79f209f125b1dcb63ae
    resource: repo://tests/test_cli_translate.py
  - id: openwiki-source-2eba846ab3cbfcc6150d04e3
    resource: repo://tests/test_index.py
  - id: openwiki-source-00c97ff13875c3dfc03942e6
    resource: repo://tests/test_pipeline_translate.py
  - id: openwiki-source-70966e163cb44e277ec6715e
    resource: repo://tests/test_translate_content.py
generated: { by: "openwiki/0.6.1", at: "2026-10-03T09:19:39.759Z" }
---

This page summarizes where unit tests live and what they cover for the CLI, indexing, pipeline translation, and AI translation/chunking behavior. It documents the intended boundaries between parsing/validation tests, behavioral tests with stubbed pipelines, and resilience tests for chunked AI calls.

## Test layout

Tests are under `tests/` and are organized by the subsystem they exercise:

- `tests/test_cli_reindex.py` — the `reindex` command’s regeneration and cleanup behavior.
- `tests/test_cli_translate.py` — CLI parsing, defaults, and sanitization of `--translate-from`.
- `tests/test_index.py` — index generation, title extraction, hidden-file filtering, and nested-artifact cleanup.
- `tests/test_pipeline_translate.py` — the pipeline’s optional translation step (`process_file` step 5b).
- `tests/test_translate_content.py` — `AIClient.translate_content`, chunking, prompt shape, and chunk-failure resilience.
- `tests/test_smoke.py` — minimal import sanity check for the package under test.

The code under test lives in `src/knowledge_extractor/`, with the LLM-facing logic in `src/knowledge_extractor/ai.py` and the pipeline orchestration in `src/knowledge_extractor/pipeline.py`.

## CLI parsing and sanitization

CLI tests focus on argument parsing, defaults, and input validation, not on the full extraction pipeline. The CLI surface is the click group `knowledge_extractor.cli.cli` with `convert` as the default command, plus `clear`, `lint`, and `reindex`.

Key behaviors covered:

- Invoking the CLI with `--input` and no subcommand routes to the `convert` command.
- `convert --input in` sets `translate_from` to `None` and picks up the documented default translation model.
- `--translate-from` and `--translate-model` are parsed and forwarded to the pipeline args.
- Whitespace around `--translate-from` is stripped before the pipeline sees it.
- The `convert` command can be invoked directly (as the `convert` script entry point does).
- `--translate-from` values containing newlines or other control characters are rejected.
- `convert` requires `--input`.

Sanitization is tested directly through `knowledge_extractor.cli._sanitize_translate_from`:

- `None` returns `None`.
- Surrounding whitespace is stripped, so `"  German  "` becomes `"German"`.
- Whitespace-only input returns `None`.
- Newlines and other control characters cause rejection (return `None`).
- Plain language names and short codes such as `"Ukrainian"` and `"de"` are accepted.

CLI tests stub the pipeline entrypoint (`_run`) so these cases only exercise argument parsing and sanitization.

## Reindex command

`tests/test_cli_reindex.py` covers the `reindex` CLI command through `CliRunner` invocations against temporary directories. It builds on the generated-index and generated-manifest fixtures:

- `GENERATED_INDEX` — an extractor-style root index body.
- `GENERATED_MANIFEST` — a one-entry manifest array.

Covered behaviors:

- Happy path: a directory with documents in the root and in nested groups produces a root `index.md` and `manifest.json`, and removes previously generated nested artifacts.
- Grouping: a three-document tree across `Root`, `VaultA`, and `VaultA/sub` produces manifest groups matching that set.
- Output wording: successful reindex reports the document and group counts.
- User content preservation: a user-written nested `index.md` is not removed by default.
- `--keep-nested`: generated nested `index.md`/`manifest.json` pairs are preserved when the flag is set.
- Missing directory: a nonexistent directory exits nonzero with “Directory not found” in the output.
- Empty directory: an empty directory exits zero, does not write `manifest.json`, and reports “Nothing to index”.

## Index generation and nested-artifact cleanup

`tests/test_index.py` covers the `knowledge_extractor.index` module directly. It tests generation, title extraction, hidden-file handling, and the generated-artifact detection used by cleanup.

Title extraction:

- `_extract_title` returns the first `# ` heading within the first 20 lines.
- When there is no heading, it falls back to the file stem.

Index generation:

- Documents are grouped by full relative parent path, with root-level files grouped under `"Root"`.
- Hidden directories (any path component starting with `.`) are excluded.
- The manifest records path, title, group, up to 20 headings, and word count.
- Paths and links use POSIX separators.
- An empty output directory returns `(0, 0)` and does not create a manifest.

Generated-artifact detection:

- `_is_generated_index` recognizes an extractor index by its leading `# Knowledge Index` signature.
- `_is_generated_manifest` recognizes an extractor manifest as a JSON array of objects containing at least `path`, `title`, and `group`. An empty array is still treated as generated.

Cleanup:

- `cleanup_nested_artifacts` removes generated `index.md`/`manifest.json` pairs in subdirectories but preserves the root pair.
- Generated nested artifacts across multiple nesting levels are removed.
- User content that does not look generated is preserved.
- Hidden-directory artifacts are preserved.
- A directory with only a root pair and no nested artifacts returns zero removed files.
- An empty generated manifest (`[]`) is still treated as generated and removed.
- Unlink failures are logged and skipped rather than raised, so one locked file does not stop cleanup of the rest.

## Pipeline translation

`tests/test_pipeline_translate.py` covers the translation step inside `knowledge_extractor.pipeline.process_file`. The tests stub the extractor and the AI client so they exercise the translation gating and output replacement, not the full end-to-end pipeline.

Setup helpers:

- `_make_file` creates a `DiscoveredFile` for a temp `.docx`.
- `_make_args` builds a `SimpleNamespace` with `temp`, `output`, `model`, `translate_from`, and `translate_model`.
- `_install_fake_extractor` stubs the `docx` extractor to return known markdown.
- `_fake_ai` builds a mock AI client whose `cleanup_content` and `translate_content` can be controlled per test.
- A fixture clears `pipeline._ai_clients` around each test.

Behaviors covered:

- Translation is invoked when `--translate-from` is set and replaces the output file with the translated markdown.
- The translation call receives the assembled markdown as the first positional argument and the source language as the second.
- When `--translate-from` is absent, `translate_content` is not called.
- When `translate_content` returns `None` (unavailable), the cleanup output is kept.

## AI client translation and chunking

`tests/test_translate_content.py` covers `AIClient.translate_content` and the static chunk helper `AIClient._split_into_chunks`. It uses a fake backend so tests control whether the client is present and what `_call` returns.

Client basics:

- `translate_content` returns `None` when there is no client.
- Trivial content is returned unchanged.

Single-pass translation:

- A document small enough for a single pass calls `_call` once.
- The prompt sent to `_call` includes the source language and the document content.

Chunked translation:

- Forcing a small `chunk_size` with multiple `##` sections results in multiple `_call` invocations.
- Chunked results are rejoined with `\n\n` between translated parts.

Chunk-failure resilience:

- A transient `AIProviderError` on a chunk does not crash the document; the translated chunks are kept and the failed chunk’s original text is retained.
- A `AIBadRequestError` on a chunk is handled the same way: previous successful translations are kept and the failing chunk is left as original text.

Chunk boundary safety:

- Oversized sections without `##` boundaries are split, but the splitter must not break inside a fenced code block, so every chunk has a balanced number of ```` ``` ```` markers.

Prompt coverage:

- `TRANSLATE_PROMPT` contains Mermaid-specific rules and shows the label-only translation pattern (for example, `A[Angemeldet]` becoming `A[Logged in]`).

## Smoke test

`tests/test_smoke.py` is a minimal harness check: it confirms the package imports and that `AIClient` is importable from `knowledge_extractor.ai`.

## What is not covered here

This strategy page describes the unit-test surface for the behaviors listed above. It does not attempt to enumerate every integration or end-to-end scenario; those are out of scope for this page.
