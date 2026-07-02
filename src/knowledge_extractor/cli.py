import argparse
import shutil
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

from .logging_setup import setup_logging
from .discovery import discover_files
from .tracker import ProgressTracker
from .pipeline import process_file, get_ai_client
from .linter import lint_file, LintResult
from .index import generate_index
from .ai import AIProviderError, AIBadRequestError

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Extract knowledge from document file trees")
    sub = parser.add_subparsers(dest="command")

    # Default run command (no subcommand needed)
    parser.add_argument("--input", type=Path, help="Input directory")
    parser.add_argument("--output", type=Path, default=Path("./output"), help="Output directory")
    parser.add_argument("--temp", type=Path, default=Path("./temp"), help="Intermediate data directory")
    parser.add_argument("--model", default="mistralai/mistral-small-2603", help="OpenRouter model")

    # Clear subcommand
    clear_parser = sub.add_parser("clear", help="Remove temp directory (or all with --all)")
    clear_parser.add_argument("--output", type=Path, default=Path("./output"), help="Output directory")
    clear_parser.add_argument("--temp", type=Path, default=Path("./temp"), help="Intermediate data directory")
    clear_parser.add_argument("--all", action="store_true", help="Also remove output directory")

    # Lint subcommand
    lint_parser = sub.add_parser("lint", help="Re-lint all markdown files in a directory")
    lint_parser.add_argument("directory", type=Path, help="Directory containing markdown files to lint")

    args = parser.parse_args()

    if args.command == "clear":
        _clear(args)
        return

    if args.command == "lint":
        _lint(args)
        return

    if not args.input:
        parser.error("--input is required")

    _run(args)


def _clear(args):
    dirs = [(args.temp, "temp")]
    if getattr(args, "all", False):
        dirs.append((args.output, "output"))

    existing = [(p, name) for p, name in dirs if p.exists()]
    if not existing:
        print("Nothing to clear.")
        return

    print("This will remove:")
    for p, name in existing:
        print(f"  {p.resolve()}")
    answer = input("Proceed? [y/N] ").strip().lower()
    if answer != "y":
        print("Cancelled.")
        return
    for p, _ in existing:
        shutil.rmtree(p, ignore_errors=True)
        if p.exists():
            print(f"  Partially removed {p} (some files locked)")
        else:
            print(f"  Removed {p}")


def _lint(args):
    """Re-lint all markdown files in the given directory."""
    directory = args.directory.resolve()
    if not directory.exists():
        print(f"Directory not found: {directory}")
        sys.exit(1)

    files = sorted(directory.rglob("*.md"))
    if not files:
        print(f"No markdown files found in {directory}")
        return

    print(f"Linting {len(files)} markdown files in {directory}")
    start = time.time()
    total_fixed = 0
    total_remaining = 0
    files_with_fixes = 0

    for i, f in enumerate(files, 1):
        rel = f.relative_to(directory)
        print(f"  [{i}/{len(files)}] {rel} ... ", end="", flush=True)
        t0 = time.time()
        result = lint_file(f)
        elapsed_file = time.time() - t0
        mode = " [fast]" if result.fast_mode else ""
        if result.fixed_count > 0:
            files_with_fixes += 1
            print(f"{result.fixed_count} fixed, {len(result.remaining_failures)} remaining ({elapsed_file:.1f}s){mode}")
        else:
            print(f"clean ({elapsed_file:.1f}s){mode}")
        total_fixed += result.fixed_count
        total_remaining += len(result.remaining_failures)

    elapsed = time.time() - start
    print(f"\nDone in {elapsed:.1f}s — {total_fixed} fixes applied across {files_with_fixes} files, {total_remaining} unfixed issues remaining")


def _run(args):
    args.output.mkdir(parents=True, exist_ok=True)
    args.temp.mkdir(parents=True, exist_ok=True)

    log = setup_logging(args.output)
    log.info("Knowledge Extractor starting")
    log.info(f"Input: {args.input.resolve()}")
    log.info(f"Output: {args.output.resolve()}")
    log.info(f"Temp: {args.temp.resolve()}")
    log.info(f"Model: {args.model}")

    files = discover_files(args.input)
    log.info(f"Discovered {len(files)} supported files")
    by_type = {}
    for f in files:
        by_type.setdefault(f.format_type, []).append(f)
    for fmt, items in sorted(by_type.items()):
        log.info(f"  {fmt}: {len(items)} files")

    tracker = ProgressTracker(args.temp / "progress.json")
    pending = tracker.get_pending(files)
    log.info(f"Pending: {len(pending)} files ({len(files) - len(pending)} already processed)")

    start = time.time()
    processed = failed = 0
    total_lint_fixes = 0
    total_lint_remaining = 0
    for i, file in enumerate(pending, 1):
        log.info(f"[{i}/{len(pending)}] Processing: {file.relative_path}")
        try:
            lint_result = process_file(file, args, tracker, log)
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

    # Log AI usage summary
    ai_client = get_ai_client()
    if ai_client and ai_client.calls > 0:
        ai_client.log_usage_summary()

    # Log lint summary
    if total_lint_fixes > 0 or total_lint_remaining > 0:
        log.info(f"Lint: {total_lint_fixes} fixes applied across {processed} files, {total_lint_remaining} unfixed issues remaining")

    elapsed = time.time() - start
    log.info(f"Done in {elapsed:.1f}s — processed: {processed}, skipped: {len(files) - len(pending)}, failed: {failed}")

    if failed:
        sys.exit(1)
