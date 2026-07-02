# Markdown Linter Integration (pymarkdownlnt)

## Problem Statement

Generated markdown files from the knowledge extractor pipeline have structural formatting inconsistencies (trailing spaces, inconsistent list markers, heading spacing issues, etc.). We want to add an automated linting/fix step using `pymarkdownlnt` (Python port of markdownlint rules from DavidAnson/vscode-markdownlint) to clean up output files.

## Requirements

- Use `pymarkdownlnt` package with its `fix` mode to auto-correct fixable markdown issues
- Integrate as step 5.5 in the pipeline — after AI cleanup, before final write
- Use the same markdownlint rule set as vscode-markdownlint
- Disable rules that conflict with our content (long tables, LaTeX math, mermaid blocks)
- Log linting results (what was fixed, what remains)

## Background

- `pymarkdownlnt` provides a Python API: `PyMarkdownApi().fix_path(path)` that fixes files in place
- Fix mode supports 21 rules including: trailing spaces (MD009), hard tabs (MD010), heading increment (MD001), list styles (MD004/MD005/MD007), trailing newline (MD047), code block/fence style (MD046/MD048), etc.
- The API works on files (not in-memory strings), so fix must happen after writing the file
- Rules to disable for our content: MD013 (line length — tables are wide), MD033 (inline HTML if present), MD025 (single h1 — our docs may have multiple top-level headings from source sections)

## Proposed Solution

Add a `linter.py` module that wraps `pymarkdownlnt`'s Python API. Call it in the pipeline after the final markdown is written to disk. Include a `.pymarkdown.json` configuration file in the project to control which rules are enabled/disabled.

## Tasks

### Task 1: Add `pymarkdownlnt` dependency and create configuration file

- **Objective:** Add the package to `pyproject.toml` and create a `.pymarkdown.json` config file with appropriate rule settings for the project's output
- **Implementation guidance:**
  - Add `pymarkdownlnt` to `[project.dependencies]` in `pyproject.toml`
  - Create `.pymarkdown.json` at project root with disabled rules: MD013 (line-length), MD033 (no-inline-html), MD025 (single-title/single-h1), and MD024 (no-duplicate-heading) since extracted docs often have repeated section names
  - Enable the `tables` extension in config since output heavily uses GFM tables
- **Test:** Run `uv sync` to verify dependency resolves. Validate config JSON is well-formed.
- **Demo:** `pymarkdownlnt` installed and config file in place, can run `pymarkdown scan output/**/*.md` from CLI to see current lint issues.

### Task 2: Create `src/knowledge_extractor/linter.py` module

- **Objective:** Implement a `lint_file(path: Path) -> LintResult` function that applies pymarkdownlnt fix mode to a single markdown file and returns info about what was fixed
- **Implementation guidance:**
  - Import `PyMarkdownApi` and `PyMarkdownApiException`
  - Create a `LintResult` dataclass with fields: `file_path`, `fixed_count`, `remaining_failures` (list of unfixed rule violations)
  - In `lint_file()`:
    1. Instantiate `PyMarkdownApi()`
    2. Configure it: disable rules per project config, set log level to suppress noisy output
    3. First `scan_path(file_path)` to count initial issues
    4. Then `fix_path(file_path)` to auto-fix
    5. Optionally re-scan to count remaining issues
    6. Return `LintResult`
  - Handle `PyMarkdownApiException` gracefully (log warning, don't fail the pipeline)
  - Use the `.pymarkdown.json` config file via `configuration_file_path()` API method
- **Test:** Write a unit test that creates a temp markdown file with known lint issues (trailing spaces, multiple blank lines, bad heading spacing), runs `lint_file()`, and verifies the file is cleaned up.
- **Demo:** Can call `lint_file()` on a sample output file and see it get fixed.

### Task 3: Integrate linter into the pipeline

- **Objective:** Call `lint_file()` in `pipeline.py` as step 6 (after writing the final output file), and log results
- **Implementation guidance:**
  - In `process_file()`, after step 5 (write final output), add step 6:
    ```python
    # 6. Markdown lint fix
    t0 = time.time()
    lint_result = lint_file(out_path)
    log.info(f"  Lint: {time.time() - t0:.2f}s ({lint_result.fixed_count} fixed, {len(lint_result.remaining_failures)} remaining)")
    ```
  - The tracker mark (`tracker.mark_processed`) should move after the lint step
  - Import `lint_file` from `.linter`
- **Test:** Run the full pipeline on a small test document and verify the output markdown passes a clean scan (no fixable issues remaining).
- **Demo:** Full pipeline run shows lint step in logs, output files are cleaner than before.

### Task 4: Add linter summary to batch run output

- **Objective:** Aggregate lint statistics across all processed files and log a summary at the end
- **Implementation guidance:**
  - Track total fixes and remaining issues across all files in `_run()` in `cli.py`
  - After all files processed, log summary: "Lint: X total fixes applied across Y files, Z unfixed issues remaining"
  - This follows the same pattern as the existing AI usage summary
- **Test:** Run full batch, verify summary line appears in log output with correct counts.
- **Demo:** End-of-run log shows aggregate lint statistics.

### Task 5: Update documentation and verify on existing output

- **Objective:** Update README and AGENTS.md to reflect the new linting step, and verify it works on the existing 65 output files
- **Implementation guidance:**
  - Add linter to the architecture diagram in AGENTS.md (`linter.py` in the module list)
  - Add "Markdown linting" to the Features section in README.md
  - Add `pymarkdownlnt` to the Dependencies list in AGENTS.md
  - Run the linter on all existing output files to verify no regressions (content not mangled)
  - Verify LaTeX math (`$...$`, `$$...$$`) and mermaid blocks are not corrupted
- **Test:** Run scan on all output files after fix, confirm no unexpected content changes. Spot-check files with LaTeX formulas.
- **Demo:** Documentation updated, existing output files pass through linter without content corruption.
