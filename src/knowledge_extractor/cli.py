import argparse
import shutil
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

from .logging_setup import setup_logging
from .discovery import discover_files
from .tracker import ProgressTracker
from .pipeline import process_file
from .index import generate_index
from .ai import AIProviderError

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Extract knowledge from document file trees")
    sub = parser.add_subparsers(dest="command")

    # Default run command (no subcommand needed)
    parser.add_argument("--input", type=Path, help="Input directory")
    parser.add_argument("--output", type=Path, default=Path("./output"), help="Output directory")
    parser.add_argument("--temp", type=Path, default=Path("./temp"), help="Intermediate data directory")
    parser.add_argument("--model", default="google/gemini-3.1-flash-lite", help="OpenRouter model")

    # Clear subcommand
    clear_parser = sub.add_parser("clear", help="Remove output and temp directories")
    clear_parser.add_argument("--output", type=Path, default=Path("./output"), help="Output directory")
    clear_parser.add_argument("--temp", type=Path, default=Path("./temp"), help="Intermediate data directory")

    args = parser.parse_args()

    if args.command == "clear":
        _clear(args)
        return

    if not args.input:
        parser.error("--input is required")

    _run(args)


def _clear(args):
    dirs = [(args.temp, "temp"), (args.output, "output")]
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
    for i, file in enumerate(pending, 1):
        log.info(f"[{i}/{len(pending)}] Processing: {file.relative_path}")
        try:
            process_file(file, args, tracker, log)
            processed += 1
        except AIProviderError as e:
            failed += 1
            log.error(f"AI provider unavailable: {e}")
            log.error("Aborting — AI provider is configured but not responding")
            break
        except Exception as e:
            failed += 1
            log.error(f"Failed: {file.relative_path} - {e}", exc_info=True)

    generate_index(args.output, args.input, log)

    elapsed = time.time() - start
    log.info(f"Done in {elapsed:.1f}s — processed: {processed}, skipped: {len(files) - len(pending)}, failed: {failed}")

    if failed:
        sys.exit(1)
