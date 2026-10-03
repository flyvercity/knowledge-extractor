# Task 3 — `reindex` CLI command

Status: [x]

Source spec: `docs/specs/reindex-command.md`
Target file: `src/knowledge_extractor/cli.py`
Test file: `tests/test_cli_reindex.py`

## Objective

Expose `reindex` as a Click subcommand that validates the directory, optionally cleans
verified nested artifacts, regenerates the root index/manifest, and echoes a summary.

## Depends on

- **Task 1** (`generate_index` returns `(doc_count, group_count)`).
- **Task 2** (`cleanup_nested_artifacts`).

Do this task **after** Tasks 1 & 2 are implemented.

## Implementation guidance

In `src/knowledge_extractor/cli.py`:

- Import the helper: `from .index import generate_index, cleanup_nested_artifacts`.
- Add the command:

```python
@cli.command()
@click.option("--output", type=click.Path(path_type=Path), default=Path("./output"),
              show_default=True, help="Output directory (vault) to reindex")
@click.option("--keep-nested", is_flag=True,
              help="Keep nested index.md/manifest.json in subdirectories (default: remove generated ones)")
def reindex(output, keep_nested):
    """Rebuild the root index.md/manifest.json covering all subdirectories.

    Useful after joining multiple vaults into one output directory. Pure
    regeneration — no extraction, no AI, no linting.
    """
    args = SimpleNamespace(output=output, keep_nested=keep_nested)
    _reindex(args)


def _reindex(args):
    output = args.output.resolve()
    if not output.exists():
        click.echo(f"Directory not found: {output}")
        sys.exit(1)

    log = setup_logging(args.output)
    log.info(f"Reindexing: {output}")

    if not args.keep_nested:
        removed = cleanup_nested_artifacts(args.output, log)
        if removed:
            click.echo(f"Removed {removed} nested index/manifest file(s)")

    doc_count, group_count = generate_index(args.output, None, log)
    if doc_count:
        click.echo(f"Reindexed {output} "
                   f"({doc_count} document(s) across {group_count} group(s))")
    else:
        click.echo(f"Nothing to index in {output}")
```

No AI client, no `discover_files`, no `--input`.

## Test requirements (`tests/test_cli_reindex.py`)

Use `click.testing.CliRunner().invoke(cli.cli, ["reindex", "--output", str(dir), ...])`:

- **Happy path**: temp dir with root + nested `*.md` and **generated** nested
  `index.md`/`manifest.json`; invoke `reindex --output <dir>`; assert exit 0, root
  `index.md`/`manifest.json` exist, manifest contains all docs with correct `group`
  values, generated nested artifacts removed, and stdout contains the summary line with
  document and group counts.
- **User-content preserved**: nested `index.md` without the `# Knowledge Index` signature
  survives a default run.
- **--keep-nested**: all nested artifacts preserved.
- **Missing dir**: non-zero exit code.
- **Empty dir**: exit 0, no `manifest.json` written, "Nothing to index" message.

## Demo

```
uv run knowledge-extractor reindex --output ./output
uv run knowledge-extractor reindex --output ./output --keep-nested
```
