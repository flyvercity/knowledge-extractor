# Task 1 — Full-parent-path grouping + single-pass read in `generate_index`

Status: [x]

Source spec: `docs/specs/reindex-command.md`
Target file: `src/knowledge_extractor/index.py`
Test file: `tests/test_index.py`

## Objective

Refactor `generate_index` so it:
- groups documents by **full relative parent path** joined with `/` (root files → `"Root"`);
- accepts a **deprecated/ignored** `input_dir` (keyword-optional, default `None`);
- reads each Markdown file's content **exactly once** (finding E2);
- **skips hidden directories** (any path component starting with `.`) (finding E3);
- returns a summary `(doc_count, group_count)` and `(0, 0)` when nothing to index (findings P2).

## Implementation guidance

In `src/knowledge_extractor/index.py`:

1. Change the signature to
   `generate_index(output_dir, input_dir=None, logger=None) -> tuple[int, int]`.
   Add `logger = logger or log` at the top. Document in the docstring that `input_dir` is
   **deprecated and ignored** (finding E4).

2. Refactor `_extract_title` to accept pre-read content:
   ```python
   def _extract_title(content: str, stem: str) -> str:
       for line in content.splitlines()[:20]:
           if line.startswith("# "):
               return line[2:].strip()
       return stem
   ```

3. Add the hidden-dir helper:
   ```python
   def _is_hidden(path: Path, output_dir: Path) -> bool:
       rel = path.relative_to(output_dir)
       return any(part.startswith(".") for part in rel.parts[:-1])
   ```

4. In the main loop:
   - list files: `[f for f in sorted(output_dir.rglob("*.md")) if f.name != "index.md" and not _is_hidden(f, output_dir)]`;
   - read `content = f.read_text(encoding="utf-8", errors="ignore")` **once**, reuse for
     `title = _extract_title(content, f.stem)`, `headings = re.findall(r"^#{1,3}\s+(.+)$", content, re.MULTILINE)[:20]`, and `word_count = len(content.split())`;
   - grouping:
     ```python
     rel = f.relative_to(output_dir)
     group = "/".join(rel.parts[:-1]) if len(rel.parts) > 1 else "Root"
     ```
   - when `md_files` is empty, log a warning and `return (0, 0)`;
   - at the end, `return (len(md_files), len(groups))`.

Do **not** change the manifest entry shape (`path`, `title`, `group`, `headings`,
`word_count`) or the index link rendering (`- [title](rel.as_posix())`).

## Test requirements (`tests/test_index.py`)

- Build a `tmp_path` output dir with: `root.md`, `VaultA/a.md`, `VaultA/sub/b.md`, and a
  hidden-dir file `.obsidian/note.md`, each starting with a `# Title` line.
- Call `generate_index(tmp_path)` and assert:
  - return value is `(3, 3)` (the `.obsidian` file is excluded);
  - parsed `manifest.json` has entries with `group` values `"Root"`, `"VaultA"`,
    `"VaultA/sub"`, and does NOT contain the `.obsidian` file;
  - `index.md` contains `## Root`, `## VaultA`, `## VaultA/sub`;
  - links use POSIX separators (`/`).
- Empty-dir case: `generate_index(empty_dir)` returns `(0, 0)` and writes no
  `manifest.json`.

## Demo

```
uv run pytest tests/test_index.py -k "grouping or summary"
```

## Coordination notes

- **Shares `index.py` with Task 2.** Do Task 1 and Task 2 in the **same agent/sequence**
  (Task 1 first) to avoid merge conflicts, or coordinate carefully. Both add
  module-level helpers.
