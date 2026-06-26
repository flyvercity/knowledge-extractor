import argparse
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from .logging_setup import setup_logging
from .discovery import discover_files
from .tracker import ProgressTracker
from .pipeline import process_file
from .index import generate_index


def main():
    parser = argparse.ArgumentParser(description="Extract knowledge from document file trees")
    parser.add_argument("--input", required=True, type=Path, help="Input directory")
    parser.add_argument("--output", type=Path, default=Path("./output"), help="Output directory")
    parser.add_argument("--temp", type=Path, default=Path("./temp"), help="Intermediate data directory")
    parser.add_argument("--model", default="google/gemini-2.5-flash", help="OpenRouter model")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    args.temp.mkdir(parents=True, exist_ok=True)

    log = setup_logging(args.output)
    log.info(f"Knowledge Extractor starting")
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
        except Exception as e:
            failed += 1
            log.error(f"Failed: {file.relative_path} - {e}", exc_info=True)

    generate_index(args.output, args.input, log)

    elapsed = time.time() - start
    log.info(f"Done in {elapsed:.1f}s — processed: {processed}, skipped: {len(files) - len(pending)}, failed: {failed}")
