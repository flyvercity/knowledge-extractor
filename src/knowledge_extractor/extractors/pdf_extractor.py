from pathlib import Path
import logging
import pymupdf
from .utils import get_img_dir
from ..formulas import FormulaRegion, ExtractionResult
from ..formulas.pdf_formulas import detect_formulas as detect_pdf_formulas
from ..formulas.renderer import render_formula_regions

log = logging.getLogger("knowledge_extractor")

# If this fraction (or more) of pages have no extractable text, treat as scanned PDF
SCANNED_THRESHOLD = 0.8


def extract_pdf(file_path: Path, temp_dir: Path) -> ExtractionResult:
    doc = pymupdf.open(str(file_path))
    img_dir = get_img_dir(temp_dir, file_path)

    total_pages = len(doc)
    if total_pages == 0:
        doc.close()
        return ExtractionResult(markdown="", formulas=[])

    # Quick scan: count pages without extractable text
    empty_pages = sum(1 for page in doc if not page.get_text("text").strip())
    scanned_ratio = empty_pages / total_pages
    is_scanned = scanned_ratio >= SCANNED_THRESHOLD

    if is_scanned:
        log.info(
            f"  PDF detected as scanned ({empty_pages}/{total_pages} pages "
            f"have no text, ratio={scanned_ratio:.0%}). Will use OCR."
        )
        result = _extract_scanned_pdf(doc, img_dir)
    else:
        result = _extract_text_pdf(doc, img_dir, temp_dir, file_path)

    doc.close()
    return result


def _extract_scanned_pdf(doc: pymupdf.Document, img_dir: Path) -> ExtractionResult:
    """Extract a scanned PDF by rendering pages as images for OCR.

    Instead of using the generic image description prompt (designed for
    diagrams/charts), we mark these images with a special OCR tag so the
    pipeline can use an OCR-specific prompt.
    """
    lines = []
    img_dir.mkdir(parents=True, exist_ok=True)

    for page_num, page in enumerate(doc, 1):
        # Even in scanned PDFs, some pages might have selectable text
        # (e.g. a digitally-created TOC page). Use that text directly.
        text = page.get_text("text").strip()
        if text:
            lines.append(f"\n## Page {page_num}\n")
            lines.append(text)
            continue

        # Render page as image for OCR
        pix = page.get_pixmap(dpi=200)
        img_path = img_dir / f"page{page_num}.png"
        pix.save(str(img_path))
        # Use a special marker that the pipeline will recognize as needing OCR
        lines.append(f"\n## Page {page_num}\n")
        lines.append(f"\n![ocr]({img_path.resolve()})\n")

    return ExtractionResult(
        markdown="\n".join(lines),
        formulas=[],
        is_scanned=True,
    )


def _extract_text_pdf(
    doc: pymupdf.Document, img_dir: Path, temp_dir: Path, file_path: Path
) -> ExtractionResult:
    """Extract a text-based PDF (the original logic)."""
    # First pass: detect formula regions across all pages
    formula_regions = detect_pdf_formulas(doc)
    # Render formula regions as images
    render_formula_regions(doc, formula_regions, temp_dir, source_file=file_path)

    # Build a lookup: page_num -> list of (region_index, FormulaRegion)
    page_formulas: dict[int, list[tuple[int, FormulaRegion]]] = {}
    for idx, region in enumerate(formula_regions):
        page_formulas.setdefault(region.page_num, []).append((idx, region))

    lines = []
    img_count = 0
    seen_xrefs: set[int] = set()

    for page_num, page in enumerate(doc, 1):
        lines.append(f"\n## Page {page_num}\n")
        text = page.get_text("text").strip()

        if not text:
            # Scanned page in an otherwise text-based PDF — render as image
            pix = page.get_pixmap(dpi=150)
            img_path = img_dir / f"page{page_num}.png"
            pix.save(str(img_path))
            lines.append(f"\n![image]({img_path.resolve()})\n")
            img_count += 1
            continue

        # Insert formula markers into the text for this page
        if page_num in page_formulas:
            text = _insert_formula_markers(page, text, page_formulas[page_num])

        lines.append(text)

        # Extract embedded images (deduplicate by xref, skip tiny images)
        for img_info in page.get_images(full=True):
            xref = img_info[0]
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)
            base_image = doc.extract_image(xref)
            # Skip tiny images (icons, bullets, decorative elements)
            if base_image["width"] < 50 or base_image["height"] < 50:
                continue
            ext = base_image["ext"]
            img_path = img_dir / f"page{page_num}_img{img_count}.{ext}"
            img_path.write_bytes(base_image["image"])
            lines.append(f"\n![image]({img_path.resolve()})\n")
            img_count += 1

    return ExtractionResult(
        markdown="\n".join(lines),
        formulas=formula_regions,
    )


def _insert_formula_markers(
    page: pymupdf.Page, text: str, formulas: list[tuple[int, FormulaRegion]]
) -> str:
    """Insert formula markers into the page text.

    For each detected formula region, find the approximate text position
    and insert a marker. Display formulas get their own line; inline
    formulas are inserted at the approximate position.
    """
    if not formulas:
        return text

    text_lines = text.split("\n")
    page_height = page.rect.height
    total_lines = len(text_lines)

    # For each formula, estimate which line it corresponds to based on
    # vertical position (y-coordinate relative to page height)
    insertions: list[tuple[int, str, bool]] = []  # (line_idx, marker, is_inline)

    for global_idx, region in formulas:
        # Estimate line position from vertical center of formula bbox
        y_center = (region.bbox[1] + region.bbox[3]) / 2
        line_idx = int((y_center / page_height) * total_lines)
        line_idx = max(0, min(total_lines - 1, line_idx))
        marker = region.marker(global_idx)
        insertions.append((line_idx, marker, region.is_inline))

    # Sort insertions by line index (reversed for safe insertion)
    insertions.sort(key=lambda x: x[0], reverse=True)

    for line_idx, marker, is_inline in insertions:
        if is_inline:
            # Insert marker at the end of the line
            text_lines[line_idx] = text_lines[line_idx] + f" {marker}"
        else:
            # Insert marker on its own line after the current line
            text_lines.insert(line_idx + 1, marker)

    return "\n".join(text_lines)
