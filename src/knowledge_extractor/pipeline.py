import re
import time
import logging
from pathlib import Path

from .discovery import DiscoveredFile
from .tracker import ProgressTracker
from .filters import filter_content
from .ai import AIClient
from .formulas import ExtractionResult, FormulaRef, FormulaRegion, FORMULA_MARKER_PATTERN
from .extractors.docx_extractor import extract_docx
from .extractors.pptx_extractor import extract_pptx
from .extractors.excel_extractor import extract_xlsx
from .extractors.pdf_extractor import extract_pdf
from .extractors.image_extractor import extract_image

log = logging.getLogger("knowledge_extractor")

EXTRACTORS = {
    "docx": extract_docx,
    "pptx": extract_pptx,
    "xlsx": extract_xlsx,
    "pdf": extract_pdf,
    "image": extract_image,
}

FORMULA_PLACEHOLDER = "[FORMULA: conversion failed]"
FORMULA_NO_API_PLACEHOLDER = "[FORMULA: no API key]"

_ai_client: AIClient | None = None


def _get_ai(model: str) -> AIClient:
    global _ai_client
    if _ai_client is None:
        _ai_client = AIClient(model)
    return _ai_client


def process_file(file: DiscoveredFile, args, tracker: ProgressTracker, logger: logging.Logger):
    start = time.time()

    # 1. Extract
    t0 = time.time()
    extractor = EXTRACTORS[file.format_type]
    result = extractor(file.path, args.temp)

    # Normalize result: extractors return either str or ExtractionResult
    if isinstance(result, str):
        extraction = ExtractionResult(markdown=result, formulas=[])
    else:
        extraction = result

    intermediate_md = extraction.markdown
    log.info(f"  Extract: {time.time() - t0:.2f}s ({len(intermediate_md)} chars, {len(extraction.formulas)} formulas)")

    # Save intermediate
    inter_path = args.temp / file.relative_path.with_suffix(".md")
    inter_path.parent.mkdir(parents=True, exist_ok=True)
    inter_path.write_text(intermediate_md, encoding="utf-8")

    # 2. Process formulas (convert markers to LaTeX)
    t0 = time.time()
    ai = _get_ai(args.model)
    if extraction.formulas:
        intermediate_md = _process_formulas(intermediate_md, extraction.formulas, ai)
        log.info(f"  Formulas: {time.time() - t0:.2f}s ({len(extraction.formulas)} converted)")
    else:
        log.info(f"  Formulas: skipped (none detected)")

    # 3. Heuristic filter
    t0 = time.time()
    filtered_md = filter_content(intermediate_md, file.format_type)
    log.info(f"  Filter: {time.time() - t0:.2f}s ({len(intermediate_md) - len(filtered_md):+d} chars)")

    # 4. AI image analysis — replace image refs with text
    t0 = time.time()
    img_count = len(re.findall(r"!\[image\]\(.+?\)", filtered_md))
    if img_count:
        log.info(f"  AI images: processing {img_count} images...")
    final_md = _replace_images_with_ai(filtered_md, ai)
    log.info(f"  AI images: {time.time() - t0:.2f}s ({img_count} images done)")

    # 5. AI cleanup
    t0 = time.time()
    pre_cleanup_len = len(final_md)
    cleaned = ai.cleanup_content(final_md)
    if cleaned:
        final_md = cleaned
        log.info(f"  AI cleanup: {time.time() - t0:.2f}s ({pre_cleanup_len} → {len(final_md)} chars, {len(final_md) - pre_cleanup_len:+d})")
    else:
        log.info(f"  AI cleanup: {time.time() - t0:.2f}s (no change, AI unavailable or skipped)")

    # 6. Write final output
    out_path = args.output / file.relative_path.with_suffix(".md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(final_md, encoding="utf-8")

    # 7. Track
    tracker.mark_processed(file, out_path)
    elapsed = time.time() - start
    log.info(f"  Total: {elapsed:.1f}s")


def _process_formulas(
    markdown: str, formulas: list[FormulaRef | FormulaRegion], ai: AIClient
) -> str:
    """Replace formula markers with LaTeX notation (or placeholder if no AI)."""
    pattern = re.compile(FORMULA_MARKER_PATTERN)
    matches = list(pattern.finditer(markdown))
    if not matches:
        return markdown

    # Process in reverse order to preserve string positions
    result = markdown
    for match in reversed(matches):
        idx = int(match.group(1))
        if idx >= len(formulas):
            log.warning(f"Formula marker index {idx} out of range (have {len(formulas)})")
            continue

        formula = formulas[idx]
        latex = _convert_single_formula(formula, ai)

        if latex:
            # Wrap with appropriate delimiters
            if formula.is_inline:
                replacement = f"${latex}$"
            else:
                replacement = f"\n$$\n{latex}\n$$\n"
        else:
            if not ai.client:
                replacement = FORMULA_NO_API_PLACEHOLDER
            else:
                log.warning(f"Formula {idx} conversion returned None")
                replacement = FORMULA_PLACEHOLDER

        result = result[:match.start()] + replacement + result[match.end():]

    return result


def _convert_single_formula(
    formula: FormulaRef | FormulaRegion, ai: AIClient
) -> str | None:
    """Convert a single formula to LaTeX via AI."""
    if isinstance(formula, FormulaRef):
        # DOCX/PPTX: send OMML XML as text
        return ai.convert_formula_to_latex(
            omml_xml=formula.omml_xml,
            context=formula.context_text,
        )
    elif isinstance(formula, FormulaRegion):
        # PDF: send cropped image
        if formula.image_path and formula.image_path.exists():
            return ai.convert_formula_to_latex(
                image_path=formula.image_path,
                context=formula.context_text,
            )
        else:
            log.warning(f"Formula region on page {formula.page_num} has no image")
            return None
    return None


def _replace_images_with_ai(markdown: str, ai: AIClient) -> str:
    pattern = re.compile(r"!\[image\]\((.+?)\)")
    matches = list(pattern.finditer(markdown))
    if not matches:
        return markdown

    total = len(matches)
    t_start = time.time()
    result = markdown
    for i, match in enumerate(reversed(matches)):  # reverse to preserve positions
        if total > 5 and (i + 1) % max(1, total // 10) == 0:
            elapsed = time.time() - t_start
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            remaining = (total - i - 1) / rate if rate > 0 else 0
            log.info(f"    AI images: {i + 1}/{total} ({elapsed:.0f}s elapsed, ~{remaining:.0f}s remaining)")

        img_path = Path(match.group(1))
        if not img_path.exists():
            log.warning(f"Image not found: {img_path}")
            continue

        # Get surrounding text as context
        start = max(0, match.start() - 200)
        end = min(len(markdown), match.end() + 200)
        context = markdown[start:match.start()] + markdown[match.end():end]
        context = re.sub(r"!\[image\]\(.+?\)", "", context).strip()

        description = ai.describe_image(img_path, context)
        if description is None:
            continue  # Keep original if AI unavailable
        if description:
            desc_stripped = description.strip()
            if desc_stripped.startswith("```mermaid"):
                # Keep mermaid diagrams as-is
                replacement = f"\n{desc_stripped}\n"
            else:
                # Wrap textual descriptions with Figure: prefix
                replacement = f"\nFigure: {desc_stripped}\n"
        else:
            replacement = ""
        result = result[:match.start()] + replacement + result[match.end():]

    return result
