---
type: Operations
title: Output and Index
description: Per-document Markdown output contract, root index.md/manifest.json generation, nested artifact cleanup, and the joining-vaults reindex workflow in the knowledge extractor.
tags: [operations, output, indexing, manifest, reindex, vaults, markdown]
verified:
  - by: openwiki/0.6.1
    at: 2026-10-03T09:19:39.759Z
sources:
  - id: openwiki-source-23775c3de52f3ab95a13cb8b
    resource: repo://README.md
  - id: openwiki-source-5d7aee63f8f84a40d6294699
    resource: repo://src/knowledge_extractor/cli.py
  - id: openwiki-source-78ff1e85f34a0ebe28e4561b
    resource: repo://src/knowledge_extractor/index.py
generated: { by: "openwiki/0.6.1", at: "2026-10-03T09:19:39.759Z" }
---

# Output and Index

<!-- openwiki: broken internal link [../src/knowledge_extractor/pipeline.py] file "../src/knowledge_extractor/pipeline.py" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../src/knowledge_extractor/index.py] file "../src/knowledge_extractor/index.py" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
The knowledge extractor writes a per-document Markdown file into the output tree and, at the end of a successful extraction run or during a `reindex` pass, regenerates a root `index.md` plus `manifest.json` that covers every Markdown already on disk. The contract for both the output files and the index artifacts is defined in [src/knowledge_extractor/pipeline.py](../src/knowledge_extractor/pipeline.py) and [src/knowledge_extractor/index.py](../src/knowledge_extractor/index.py), and is surfaced through the `convert` and `reindex` commands in [src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py).

## Per-document Markdown output

<!-- openwiki: broken internal link [../src/knowledge_extractor/pipeline.py] file "../src/knowledge_extractor/pipeline.py" does not exist. Fix the href or restore the target, then delete this comment. -->
Each source document becomes one Markdown file under the output root, preserving the source-relative path but with a `.md` suffix. The per-file lifecycle in [src/knowledge_extractor/pipeline.py](../src/knowledge_extractor/pipeline.py) is:

<!-- openwiki: broken internal link [../src/knowledge_extractor/pipeline.py] file "../src/knowledge_extractor/pipeline.py" does not exist. Fix the href or restore the target, then delete this comment. -->
1. **Extract** — the format-specific extractor runs and either returns a `str` or an `ExtractionResult`; if it returns a string, the pipeline wraps it as `ExtractionResult(markdown=result, formulas=[])` ([src/knowledge_extractor/pipeline.py](../src/knowledge_extractor/pipeline.py)). The intermediate Markdown is saved to the temp directory before any AI post-processing.
<!-- openwiki: broken internal link [../src/knowledge_extractor/pipeline.py] file "../src/knowledge_extractor/pipeline.py" does not exist. Fix the href or restore the target, then delete this comment. -->
2. **Formulas** — formula markers (`<<FORMULA:n>>`) are replaced with LaTeX via AI; inline formulas are wrapped in `$...$`, display formulas in `$$\n...\n$$` ([src/knowledge_extractor/pipeline.py](../src/knowledge_extractor/pipeline.py)).
<!-- openwiki: broken internal link [../src/knowledge_extractor/pipeline.py] file "../src/knowledge_extractor/pipeline.py" does not exist. Fix the href or restore the target, then delete this comment. -->
3. **OCR** — scanned pages in PDFs are OCR'd before filtering so that the resulting text is available downstream ([src/knowledge_extractor/pipeline.py](../src/knowledge_extractor/pipeline.py)).
<!-- openwiki: broken internal link [../src/knowledge_extractor/pipeline.py] file "../src/knowledge_extractor/pipeline.py" does not exist. Fix the href or restore the target, then delete this comment. -->
4. **Heuristic filter** — title slides, logo-only sections, and repeated headers/footers are removed ([src/knowledge_extractor/pipeline.py](../src/knowledge_extractor/pipeline.py)).
<!-- openwiki: broken internal link [../src/knowledge_extractor/pipeline.py] file "../src/knowledge_extractor/pipeline.py" does not exist. Fix the href or restore the target, then delete this comment. -->
5. **AI image analysis** — image references are replaced with text descriptions or Mermaid diagrams when the AI returns them ([src/knowledge_extractor/pipeline.py](../src/knowledge_extractor/pipeline.py)).
<!-- openwiki: broken internal link [../src/knowledge_extractor/pipeline.py] file "../src/knowledge_extractor/pipeline.py" does not exist. Fix the href or restore the target, then delete this comment. -->
6. **AI cleanup** — skipped for scanned PDFs; the OCR output is used directly ([src/knowledge_extractor/pipeline.py](../src/knowledge_extractor/pipeline.py)).
<!-- openwiki: broken internal link [../src/knowledge_extractor/pipeline.py] file "../src/knowledge_extractor/pipeline.py" does not exist. Fix the href or restore the target, then delete this comment. -->
7. **AI translation (optional)** — when `--translate-from` is set, the assembled Markdown is translated into English after cleanup and before linting ([src/knowledge_extractor/pipeline.py](../src/knowledge_extractor/pipeline.py)).
<!-- openwiki: broken internal link [../src/knowledge_extractor/pipeline.py] file "../src/knowledge_extractor/pipeline.py" does not exist. Fix the href or restore the target, then delete this comment. -->
8. **Write final output** — the processed Markdown is written to the output directory ([src/knowledge_extractor/pipeline.py](../src/knowledge_extractor/pipeline.py)).
<!-- openwiki: broken internal link [../src/knowledge_extractor/pipeline.py] file "../src/knowledge_extractor/pipeline.py" does not exist. Fix the href or restore the target, then delete this comment. -->
9. **Markdown lint** — auto-fixes are applied via `lint_file()` ([src/knowledge_extractor/pipeline.py](../src/knowledge_extractor/pipeline.py)).

Because the final write happens in step 8, subsequent pipeline stages (linting, AI usage summary, index generation) operate on the final Markdown, not the intermediate temp artifact.

<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
The `convert` command is incremental: after discovery it computes `pending = [f for f in files if not output_path(f).exists()]` and only processes files whose output Markdown does not yet exist ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)). When `--translate-from` is set and some outputs already exist, the CLI logs a warning because pre-existing outputs are **not** re-translated; deleting the output file/directory or running `clear` is the way to force re-translation ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)). `--dry-run` previews the same split without processing ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)).

## Output structure

A completed extraction produces:

<!-- openwiki: broken internal link [../src/knowledge_extractor/index.py] file "../src/knowledge_extractor/index.py" does not exist. Fix the href or restore the target, then delete this comment. -->
- `output/index.md` — flat index grouped by the original folder structure ([src/knowledge_extractor/index.py](../src/knowledge_extractor/index.py)).
<!-- openwiki: broken internal link [../src/knowledge_extractor/index.py] file "../src/knowledge_extractor/index.py" does not exist. Fix the href or restore the target, then delete this comment. -->
- `output/**/*.md` — one Markdown file per source document ([src/knowledge_extractor/index.py](../src/knowledge_extractor/index.py)).
<!-- openwiki: broken internal link [../src/knowledge_extractor/index.py] file "../src/knowledge_extractor/index.py" does not exist. Fix the href or restore the target, then delete this comment. -->
- `output/manifest.json` — JSON array of entries carrying `path`, `title`, `group`, `headings`, and `word_count` ([src/knowledge_extractor/index.py](../src/knowledge_extractor/index.py)).
<!-- openwiki: broken internal link [../src/knowledge_extractor/logging_setup.py] file "../src/knowledge_extractor/logging_setup.py" does not exist. Fix the href or restore the target, then delete this comment. -->
- `output/extraction.log` — console output is mirrored to this log file ([src/knowledge_extractor/logging_setup.py](../src/knowledge_extractor/logging_setup.py)).

<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
The log includes startup information, per-format file counts, pending vs already-processed counts, per-file progress and stage timings, per-model AI usage summaries, lint summary, and a final summary; the process exits with code 1 if any file failed ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)).

## Root index generation

<!-- openwiki: broken internal link [../src/knowledge_extractor/index.py] file "../src/knowledge_extractor/index.py" does not exist. Fix the href or restore the target, then delete this comment. -->
Index generation is implemented in [src/knowledge_extractor/index.py](../src/knowledge_extractor/index.py) by `generate_index(output_dir, ...)`, which:

<!-- openwiki: broken internal link [../src/knowledge_extractor/index.py] file "../src/knowledge_extractor/index.py" does not exist. Fix the href or restore the target, then delete this comment. -->
- collects non-hidden `*.md` files under `output_dir`, excluding the root `index.md` itself ([src/knowledge_extractor/index.py](../src/knowledge_extractor/index.py));
<!-- openwiki: broken internal link [../src/knowledge_extractor/index.py] file "../src/knowledge_extractor/index.py" does not exist. Fix the href or restore the target, then delete this comment. -->
- groups documents by their full relative parent path (POSIX-style, joined with `/`); files directly in the output root are grouped under `"Root"` ([src/knowledge_extractor/index.py](../src/knowledge_extractor/index.py));
<!-- openwiki: broken internal link [../src/knowledge_extractor/index.py] file "../src/knowledge_extractor/index.py" does not exist. Fix the href or restore the target, then delete this comment. -->
- reads each Markdown file exactly once and extracts `title` (first `# ` heading in the first 20 lines, else the file stem), up to 20 level-1–3 headings, and word count ([src/knowledge_extractor/index.py](../src/knowledge_extractor/index.py));
<!-- openwiki: broken internal link [../src/knowledge_extractor/index.py] file "../src/knowledge_extractor/index.py" does not exist. Fix the href or restore the target, then delete this comment. -->
- writes `index.md` with a `# Knowledge Index` header and grouped links, and writes `manifest.json` as a JSON array of per-document metadata ([src/knowledge_extractor/index.py](../src/knowledge_extractor/index.py));
<!-- openwiki: broken internal link [../src/knowledge_extractor/index.py] file "../src/knowledge_extractor/index.py" does not exist. Fix the href or restore the target, then delete this comment. -->
- returns `(doc_count, group_count)` and logs a warning when there is nothing to index ([src/knowledge_extractor/index.py](../src/knowledge_extractor/index.py)).

<!-- openwiki: broken internal link [../src/knowledge_extractor/index.py] file "../src/knowledge_extractor/index.py" does not exist. Fix the href or restore the target, then delete this comment. -->
The `input_dir` parameter of `generate_index` is deprecated and ignored; it is retained only for positional compatibility with the historical `convert` call site `generate_index(args.output, args.input, log)` ([src/knowledge_extractor/index.py](../src/knowledge_extractor/index.py)).

<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
Index generation is called at the end of a successful `convert` run ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)) and is the sole operation of `reindex`, which rebuilds the root pair purely from Markdown already on disk — no extraction, no AI, no linting ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)).

## Nested artifact cleanup

<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../src/knowledge_extractor/index.py] file "../src/knowledge_extractor/index.py" does not exist. Fix the href or restore the target, then delete this comment. -->
`reindex` can remove nested `index.md`/`manifest.json` files found in subdirectories, but only when they are verified extractor-generated artifacts ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py), [src/knowledge_extractor/index.py](../src/knowledge_extractor/index.py)):

<!-- openwiki: broken internal link [../src/knowledge_extractor/index.py] file "../src/knowledge_extractor/index.py" does not exist. Fix the href or restore the target, then delete this comment. -->
- a nested `index.md` must start with `# Knowledge Index` ([src/knowledge_extractor/index.py](../src/knowledge_extractor/index.py));
<!-- openwiki: broken internal link [../src/knowledge_extractor/index.py] file "../src/knowledge_extractor/index.py" does not exist. Fix the href or restore the target, then delete this comment. -->
- a nested `manifest.json` must parse as a JSON array of entries carrying at least `path`, `title`, and `group` ([src/knowledge_extractor/index.py](../src/knowledge_extractor/index.py)).

<!-- openwiki: broken internal link [../src/knowledge_extractor/index.py] file "../src/knowledge_extractor/index.py" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../src/knowledge_extractor/index.py] file "../src/knowledge_extractor/index.py" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../src/knowledge_extractor/index.py] file "../src/knowledge_extractor/index.py" does not exist. Fix the href or restore the target, then delete this comment. -->
User-content `index.md` files (for example Obsidian folder notes, Hugo/Docusaurus/MkDocs index pages) are preserved and logged at warning level ([src/knowledge_extractor/index.py](../src/knowledge_extractor/index.py)). Hidden directories (any path component starting with `.`) are neither indexed nor removed ([src/knowledge_extractor/index.py](../src/knowledge_extractor/index.py)). The root-level pair is always regenerated and is never considered for removal ([src/knowledge_extractor/index.py](../src/knowledge_extractor/index.py)).

<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
`--keep-nested` opts out of removal entirely, leaving all nested artifacts in place ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py)). This is the primary operational lever when combining vaults that were extracted separately.

## Joining vaults and reindex

<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../README.md] file "../README.md" does not exist. Fix the href or restore the target, then delete this comment. -->
After joining multiple vaults, the typical workflow is to copy the per-document subfolders of several output directories into one combined directory and then run `reindex` to produce a single unified `index.md` and `manifest.json` covering every subfolder ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py), [README.md](../README.md)).

<!-- openwiki: broken internal link [../README.md] file "../README.md" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../src/knowledge_extractor/cli.py] file "../src/knowledge_extractor/cli.py" does not exist. Fix the href or restore the target, then delete this comment. -->
<!-- openwiki: broken internal link [../src/knowledge_extractor/index.py] file "../src/knowledge_extractor/index.py" does not exist. Fix the href or restore the target, then delete this comment. -->
The important operational caution is collision avoidance: place each joined vault under a **distinct parent folder** inside the combined directory (for example `combined/VaultA/`, `combined/VaultB/`). Documents with identical relative paths would otherwise silently overwrite each other on the filesystem before `reindex` runs ([README.md](../README.md)). Once the files are in place, `reindex` does not need the original input directories — it regenerates the root index/manifest purely from the Markdown that exists in the combined output tree ([src/knowledge_extractor/cli.py](../src/knowledge_extractor/cli.py), [src/knowledge_extractor/index.py](../src/knowledge_extractor/index.py)).

## Related pages

- [CLI Reference](../operations/cli-reference.md) — the `convert`, `clear`, `lint`, and `reindex` commands, flag defaults, incremental processing, and dry-run behavior.
- [Configuration](../operations/configuration.md) — runtime environment variables, model selection, translation configuration, and logging setup.
- [Architecture Overview](../architecture/overview.md) — entrypoints, file discovery, per-format extractors, AI-assisted post-processing, linting, and index generation.
