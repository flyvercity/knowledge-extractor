# Task 2 — Content-verified `cleanup_nested_artifacts` helper

Status: [ ]

Source spec: `docs/specs/reindex-command.md`
Target file: `src/knowledge_extractor/index.py`
Test file: `tests/test_index.py`

## Objective

Add a helper that removes **only verified extractor-generated** `index.md` / `manifest.json`
from subdirectories of the output root, preserving the root pair and any user content,
skipping hidden directories, returning a count, and tolerating locked files.

## Implementation guidance

Add to `src/knowledge_extractor/index.py` (reuse `_is_hidden` from Task 1):

```python
def _is_generated_index(path: Path) -> bool:
    try:
        with path.open(encoding="utf-8", errors="ignore") as fh:
            head = fh.read(256)
    except OSError:
        return False
    return head.lstrip().startswith("# Knowledge Index")

def _is_generated_manifest(path: Path) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, ValueError):
        return False
    if not isinstance(data, list):
        return False
    return all(isinstance(e, dict) and {"path", "title", "group"} <= set(e) for e in data)

def cleanup_nested_artifacts(output_dir: Path, logger=None) -> int:
    logger = logger or log
    root = output_dir.resolve()
    removed = 0
    checks = {"index.md": _is_generated_index, "manifest.json": _is_generated_manifest}
    for name, is_generated in checks.items():
        for path in output_dir.rglob(name):
            if path.resolve().parent == root:
                continue  # keep the root pair
            if _is_hidden(path, output_dir):
                continue  # never touch hidden dirs
            if not is_generated(path):
                logger.warning(f"Preserving user content (not a generated artifact): {path}")
                continue
            try:
                path.unlink()
                removed += 1
                logger.info(f"Removed nested artifact: {path}")
            except OSError as e:
                logger.warning(f"Could not remove {path}: {e}")
    return removed
```

An **empty** JSON array is a valid generated manifest (passes `all(...)` vacuously).

## Test requirements (`tests/test_index.py`)

- **Generated artifacts removed**: root `index.md` + `manifest.json` (generated-looking)
  plus generated nested copies under `VaultA/` and `VaultA/sub/`; call helper; assert
  nested generated files removed, root files preserved, return value equals count removed.
- **User-content preserved (E1/P1)**: nested `index.md` whose first line is
  `# My Project Notes`, and nested `manifest.json` containing `{"custom": true}` (an
  object, not a list); assert both preserved and not counted.
- **Hidden dir preserved (E3)**: `.obsidian/index.md` with the `# Knowledge Index`
  signature; assert preserved.
- **No nested artifacts** returns `0`.
- **Resilience (E5)**: monkeypatch `pathlib.Path.unlink` to raise `OSError` for a target
  file; assert the helper logs and continues without raising, and the returned count
  reflects only successfully removed files.

## Demo

```
uv run pytest tests/test_index.py -k cleanup
```

## Coordination notes

- **Shares `index.py` with Task 1.** Run after Task 1 (which introduces `_is_hidden`), or
  in the same agent. If done together, land both sets of helpers in one edit pass.
