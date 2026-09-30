import shutil
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import click
from dotenv import load_dotenv

from .logging_setup import setup_logging
from .discovery import discover_files
from .pipeline import process_file, get_ai_client, get_ai_clients
from .linter import lint_file, LintResult
from .index import generate_index
from .ai import AIProviderError, AIBadRequestError

load_dotenv()

DEFAULT_MODEL = "openai/gpt-6-luna"
DEFAULT_TRANSLATE_MODEL = "mistralai/mistral-large-2512"


def _sanitize_translate_from(value: str) -> str | None:
    """Sanitize the --translate-from value before it is formatted into an LLM prompt.

    Strips surrounding whitespace and rejects newlines/control characters to avoid
    prompt-injection via the flag value (spec finding P3). Returns the cleaned string,
    or None if the value is empty/invalid after sanitization.
    """
    if value is None:
        return None
    # Reject any control characters, including newlines/tabs/carriage returns.
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        return None
    cleaned = value.strip()
    return cleaned or None


class _DefaultGroup(click.Group):
    """A Group that falls back to a default subcommand.

    Preserves the historical UX where invoking the tool with no subcommand
    (e.g. ``main.py --input ./in``) runs the extraction pipeline. If the first
    argument is not a known subcommand or a group-level help flag, the
    ``default_command`` is invoked with the original arguments.
    """

    def __init__(self, *args, default_command=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_command = default_command

    def parse_args(self, ctx, args):
        if self.default_command and args:
            first = args[0]
            is_known_command = first in self.commands
            is_group_help = first in ("-h", "--help")
            # Anything that isn't a known subcommand or the group help flag is
            # forwarded to the default command (e.g. `--input ./in`).
            if not is_known_command and not is_group_help:
                args = [self.default_command, *args]
        return super().parse_args(ctx, args)


@click.group(
    cls=_DefaultGroup,
    default_command="convert",
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=False,
)
def cli():
    """Extract knowledge from document file trees."""


@cli.command()
@click.option("--input", "input_", type=click.Path(path_type=Path), required=True, help="Input directory")
@click.option("--output", type=click.Path(path_type=Path), default=Path("./output"), show_default=True, help="Output directory")
@click.option("--temp", type=click.Path(path_type=Path), default=Path("./temp"), show_default=True, help="Intermediate data directory")
@click.option("--model", default=DEFAULT_MODEL, show_default=True, help="OpenRouter model")
@click.option(
    "--translate-from",
    default=None,
    help="Translate output into English from this source language (e.g. German, de). If unset, no translation.",
)
@click.option(
    "--translate-model",
    default=DEFAULT_TRANSLATE_MODEL,
    show_default=True,
    help="Model used for translation (falls back to --model if unset)",
)
@click.option("--dry-run", is_flag=True, help="List which files would be processed and skipped, then exit")
def convert(input_, output, temp, model, translate_from, translate_model, dry_run):
    """Extract knowledge from the input directory (default command)."""
    if translate_from is not None:
        sanitized = _sanitize_translate_from(translate_from)
        if sanitized is None:
            raise click.BadParameter(
                "must be a non-empty string without newlines or control characters",
                param_hint="--translate-from",
            )
        translate_from = sanitized

    args = SimpleNamespace(
        input=input_,
        output=output,
        temp=temp,
        model=model,
        translate_from=translate_from,
        translate_model=translate_model,
        dry_run=dry_run,
    )
    _run(args)


@cli.command()
@click.option("--output", type=click.Path(path_type=Path), default=Path("./output"), show_default=True, help="Output directory")
@click.option("--temp", type=click.Path(path_type=Path), default=Path("./temp"), show_default=True, help="Intermediate data directory")
@click.option("--all", "all_", is_flag=True, help="Also remove output directory")
def clear(output, temp, all_):
    """Remove temp directory (or all with --all)."""
    args = SimpleNamespace(output=output, temp=temp, all=all_)
    _clear(args)


@cli.command()
@click.argument("directory", type=click.Path(path_type=Path))
def lint(directory):
    """Re-lint all markdown files in a directory."""
    args = SimpleNamespace(directory=directory)
    _lint(args)


def main():
    cli()


def convert_main():
    """Entry point for the ``convert`` script: run the extraction command directly.

    Enables ``uv run convert <options>`` (e.g. ``uv run convert --input ./in``)
    without needing to type the subcommand.
    """
    convert()


def _clear(args):
    dirs = [(args.temp, "temp")]
    if getattr(args, "all", False):
        dirs.append((args.output, "output"))

    existing = [(p, name) for p, name in dirs if p.exists()]
    if not existing:
        click.echo("Nothing to clear.")
        return

    click.echo("This will remove:")
    for p, name in existing:
        click.echo(f"  {p.resolve()}")
    if not click.confirm("Proceed?", default=False):
        click.echo("Cancelled.")
        return
    for p, _ in existing:
        shutil.rmtree(p, ignore_errors=True)
        if p.exists():
            click.echo(f"  Partially removed {p} (some files locked)")
        else:
            click.echo(f"  Removed {p}")


def _lint(args):
    """Re-lint all markdown files in the given directory."""
    directory = args.directory.resolve()
    if not directory.exists():
        click.echo(f"Directory not found: {directory}")
        sys.exit(1)

    files = sorted(directory.rglob("*.md"))
    if not files:
        click.echo(f"No markdown files found in {directory}")
        return

    click.echo(f"Linting {len(files)} markdown files in {directory}")
    start = time.time()
    total_fixed = 0
    total_remaining = 0
    files_with_fixes = 0

    for i, f in enumerate(files, 1):
        rel = f.relative_to(directory)
        click.echo(f"  [{i}/{len(files)}] {rel} ... ", nl=False)
        t0 = time.time()
        result = lint_file(f)
        elapsed_file = time.time() - t0
        mode = " [fast]" if result.fast_mode else ""
        if result.fixed_count > 0:
            files_with_fixes += 1
            click.echo(f"{result.fixed_count} fixed, {len(result.remaining_failures)} remaining ({elapsed_file:.1f}s){mode}")
        else:
            click.echo(f"clean ({elapsed_file:.1f}s){mode}")
        total_fixed += result.fixed_count
        total_remaining += len(result.remaining_failures)

    elapsed = time.time() - start
    click.echo(f"\nDone in {elapsed:.1f}s — {total_fixed} fixes applied across {files_with_fixes} files, {total_remaining} unfixed issues remaining")


def _run(args):
    args.output.mkdir(parents=True, exist_ok=True)
    args.temp.mkdir(parents=True, exist_ok=True)

    log = setup_logging(args.output)
    log.info("Knowledge Extractor starting")
    log.info(f"Input: {args.input.resolve()}")
    log.info(f"Output: {args.output.resolve()}")
    log.info(f"Temp: {args.temp.resolve()}")
    log.info(f"Model: {args.model}")
    if getattr(args, "translate_from", None):
        translate_model = args.translate_model or args.model
        log.info(f"Translate: from {args.translate_from} to English (model: {translate_model})")

    files = discover_files(args.input)
    log.info(f"Discovered {len(files)} supported files")
    by_type = {}
    for f in files:
        by_type.setdefault(f.format_type, []).append(f)
    for fmt, items in sorted(by_type.items()):
        log.info(f"  {fmt}: {len(items)} files")

    def output_path(f):
        return args.output / f.relative_path.with_suffix(".md")

    pending = [f for f in files if not output_path(f).exists()]
    log.info(f"Pending: {len(pending)} files ({len(files) - len(pending)} already processed)")

    skipped_count = len(files) - len(pending)
    if getattr(args, "translate_from", None) and skipped_count > 0 and not getattr(args, "dry_run", False):
        log.warning(
            f"--translate-from is set but {skipped_count} file(s) will be skipped because their "
            f"output already exists; existing outputs are NOT re-translated. Delete the output "
            f"file(s)/dir or run 'clear' to translate them."
        )

    if getattr(args, "dry_run", False):
        skipped = [f for f in files if output_path(f).exists()]
        log.info("Dry run — no files will be processed")
        log.info(f"Would process ({len(pending)}):")
        for f in pending:
            log.info(f"  + {f.relative_path}")
        log.info(f"Would skip ({len(skipped)}, output exists):")
        for f in skipped:
            log.info(f"  - {f.relative_path}")
        return

    start = time.time()
    processed = failed = 0
    total_lint_fixes = 0
    total_lint_remaining = 0
    for i, file in enumerate(pending, 1):
        log.info(f"[{i}/{len(pending)}] Processing: {file.relative_path}")
        try:
            lint_result = process_file(file, args, log)
            processed += 1
            if lint_result:
                total_lint_fixes += lint_result.fixed_count
                total_lint_remaining += len(lint_result.remaining_failures)
        except AIProviderError as e:
            failed += 1
            log.error(f"AI provider unavailable: {e}")
            log.error("Aborting — AI provider is configured but not responding")
            break
        except Exception as e:
            failed += 1
            log.error(f"Failed: {file.relative_path} - {e}", exc_info=True)

    generate_index(args.output, args.input, log)

    # Log AI usage summary (one per distinct model, e.g. main + translation)
    for ai_client in get_ai_clients():
        if ai_client and ai_client.calls > 0:
            ai_client.log_usage_summary()

    # Log lint summary
    if total_lint_fixes > 0 or total_lint_remaining > 0:
        log.info(f"Lint: {total_lint_fixes} fixes applied across {processed} files, {total_lint_remaining} unfixed issues remaining")

    elapsed = time.time() - start
    log.info(f"Done in {elapsed:.1f}s — processed: {processed}, skipped: {len(files) - len(pending)}, failed: {failed}")

    if failed:
        sys.exit(1)
