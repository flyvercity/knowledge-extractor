from pathlib import Path
import pymupdf
from .utils import get_img_dir
from ..formulas import FormulaRegion, ExtractionResult
from ..formulas.pdf_formulas import detect_formulas as detect_pdf_formulas
from ..formulas.renderer import render_formula_regions


def extract_pdf(file_path: Path, temp_dir: Path) -> ExtractionResult:
    doc = pymupdf.open(str(file_path))
    img_dir = get_img_dir(temp_dir, file_path)

    # First pass: detect formula regions across all pages
    formula_regions = detect_pdf_formulas(doc)
    # Render formula regions as images
    render_formula_regions(doc, formula_regions, temp_dir)

    # Build a lookup: page_num -> list of (region_index, FormulaRegion)
    page_formulas: dict[int, list[tuple[int, FormulaRegion]]] = {}
    for idx, region in enumerate(formula_regions):
        page_formulas.setdefault(region.page_num, []).append((idx, region))

    lines = []
    img_count = 0

    for page_num, page in enumerate(doc, 1):
        lines.append(f"\n## Page {page_num}\n")
        text = page.get_text("text").strip()

        if not text:
            # Scanned page — render as image for AI OCR
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

        # Extract embedded images
        for img_info in page.get_images(full=True):
            xref = img_info[0]
            base_image = doc.extract_image(xref)
            ext = base_image["ext"]
            img_path = img_dir / f"page{page_num}_img{img_count}.{ext}"
            img_path.write_bytes(base_image["image"])
            lines.append(f"\n![image]({img_path.resolve()})\n")
            img_count += 1

    doc.close()
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
