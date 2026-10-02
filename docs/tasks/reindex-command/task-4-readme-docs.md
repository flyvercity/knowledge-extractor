# Task 4 — README documentation

Status: [ ]

Source spec: `docs/specs/reindex-command.md`
Target file: `README.md`

## Objective

Document the `reindex` command, its flags, and the vault-join use case.

## Independence

This task touches only `README.md` and can run **in parallel** with Tasks 1–3.

## Implementation guidance

In `README.md`:

- Add `reindex` to the "Other subcommands" sentence (currently lists `convert`, `clear`,
  `lint`).
- Add a usage snippet near the other `uv run` examples:
  ```bash
  # Rebuild a single root index/manifest across all subfolders (e.g. after joining vaults)
  uv run knowledge-extractor reindex --output ./output
  uv run knowledge-extractor reindex --output ./output --keep-nested
  ```
- Add a short subsection explaining:
  - the **vault-join** scenario: copy per-document subfolders from multiple vaults into one
    output dir, then `reindex` to get one unified `index.md` + `manifest.json` without a
    full, expensive re-run;
  - that **verified** generated nested `index.md`/`manifest.json` are removed by default,
    while user-content `index.md` files (not starting with `# Knowledge Index`) are
    **preserved**; `--keep-nested` opts out of removal entirely;
  - `--output` default is `./output`;
  - **vault-join guidance (finding P3)**: place each joined vault under a **distinct parent
    folder** (e.g. `combined/VaultA/`, `combined/VaultB/`) so documents with identical
    relative paths don't silently overwrite each other on the filesystem before `reindex`
    runs.

## Verification

N/A (docs). Read the rendered section to confirm `reindex`, `--keep-nested`, and the
rationale are present.
