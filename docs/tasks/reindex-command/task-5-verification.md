# Task 5 — Full verification pass

Status: [x]

Source spec: `docs/specs/reindex-command.md`

## Objective

Ensure the entire test suite passes and the `reindex` command works end-to-end.

## Depends on

Tasks 1, 2, 3 (and ideally 4). Run **last**.

## Implementation guidance

- Run the whole suite: `uv run pytest`.
- Confirm help text: `uv run knowledge-extractor reindex -h`.
- Confirm the existing `convert` path still calls `generate_index` successfully — the
  positional call `generate_index(args.output, args.input, log)` in `_run` must remain
  valid (now returns a `(doc_count, group_count)` tuple that `_run` may ignore).
- Fix any failures before completing.

## Test requirements

- `uv run pytest` is green (existing tests + new `tests/test_index.py` and
  `tests/test_cli_reindex.py`).

## Demo

```
uv run pytest
uv run knowledge-extractor reindex -h
```
