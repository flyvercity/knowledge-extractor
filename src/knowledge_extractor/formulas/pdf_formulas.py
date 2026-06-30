"""Detect mathematical formula regions in PDF pages using heuristic analysis."""

import logging
import re
from pathlib import Path

import pymupdf

from . import FormulaRegion

log = logging.getLogger("knowledge_extractor")

# Font names commonly used for mathematical notation
MATH_FONTS = {
    "symbol", "cambria math", "cmmi", "cmsy", "cmex", "cmr",
    "mt extra", "math", "euclid", "asana math", "xits math",
    "stix", "latin modern math", "libertinus math",
}

# Unicode ranges that indicate mathematical content
# Mathematical Operators (U+2200-U+22FF)
# Supplemental Math Operators (U+2A00-U+2AFF)
# Greek letters (U+0391-U+03C9)
# Superscripts/subscripts (U+2070-U+209F)
# Misc Math Symbols A/B (U+27C0-U+27EF, U+2980-U+29FF)
_MATH_CHAR_RANGES = [
    (0x0391, 0x03C9),  # Greek letters
    (0x2070, 0x209F),  # Superscripts and subscripts
    (0x2190, 0x21FF),  # Arrows
    (0x2200, 0x22FF),  # Mathematical operators
    (0x2300, 0x23FF),  # Misc technical (includes some math)
    (0x27C0, 0x27EF),  # Misc math symbols A
    (0x2980, 0x29FF),  # Misc math symbols B
    (0x2A00, 0x2AFF),  # Supplemental math operators
    (0x1D400, 0x1D7FF),  # Mathematical alphanumeric symbols
]

# Single characters that strongly suggest math context
MATH_CHARS = set("∫∑∏√∂∇∞±∓×÷≈≠≤≥≡∈∉⊂⊃∪∩∧∨¬∀∃∅αβγδεζηθικλμνξπρστυφχψω")


def detect_formulas(doc: pymupdf.Document) -> list[FormulaRegion]:
    """Detect math formula regions across all pages of a PDF document.

    Uses heuristic analysis of font names and character content to identify
    spans that are likely mathematical formulas, then groups them into regions.
    """
    all_regions = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        regions = _detect_page_formulas(page, page_num + 1)
        all_regions.extend(regions)

    log.debug(f"PDF formula detection: found {len(all_regions)} formula regions")
    return all_regions


def _detect_page_formulas(page: pymupdf.Page, page_num: int) -> list[FormulaRegion]:
    """Detect formula regions on a single PDF page."""
    page_dict = page.get_text("dict")
    page_width = page_dict["width"]

    math_spans = []

    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:  # text blocks only
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if _is_math_span(span):
                    math_spans.append({
                        "bbox": span["bbox"],
                        "text": span["text"],
                        "font": span["font"],
                        "line_bbox": line["bbox"],
                    })

    if not math_spans:
        return []

    # Group adjacent math spans into formula regions
    regions = _group_spans_into_regions(math_spans, page_width)

    # Build FormulaRegion objects
    result = []
    for region in regions:
        bbox = region["bbox"]
        is_inline = _classify_inline_display(bbox, region["line_bbox"], page_width)
        context = _get_page_context(page, bbox)
        result.append(FormulaRegion(
            page_num=page_num,
            bbox=(bbox[0], bbox[1], bbox[2], bbox[3]),
            is_inline=is_inline,
            context_text=context,
        ))

    return result


def _is_math_span(span: dict) -> bool:
    """Determine if a text span is likely mathematical content."""
    font_name = span.get("font", "").lower()
    text = span.get("text", "")

    # Check font name against known math fonts
    for math_font in MATH_FONTS:
        if math_font in font_name:
            return True

    # Check for high concentration of math characters
    if not text:
        return False

    math_char_count = 0
    for ch in text:
        if ch in MATH_CHARS:
            math_char_count += 1
        elif _is_in_math_range(ord(ch)):
            math_char_count += 1

    # If more than 30% of characters are math-like, consider it math
    if len(text) > 0 and math_char_count / len(text) > 0.3:
        return True

    # Single math character spans (common in PDFs where each symbol is separate)
    if len(text.strip()) <= 2 and math_char_count > 0:
        return True

    return False


def _is_in_math_range(code_point: int) -> bool:
    """Check if a Unicode code point falls in a math-related range."""
    for start, end in _MATH_CHAR_RANGES:
        if start <= code_point <= end:
            return True
    return False


def _group_spans_into_regions(
    math_spans: list[dict], page_width: float
) -> list[dict]:
    """Group nearby math spans into contiguous formula regions."""
    if not math_spans:
        return []

    # Sort by vertical position then horizontal
    math_spans.sort(key=lambda s: (s["bbox"][1], s["bbox"][0]))

    regions = []
    current = {
        "bbox": list(math_spans[0]["bbox"]),
        "line_bbox": list(math_spans[0]["line_bbox"]),
        "spans": [math_spans[0]],
    }

    for span in math_spans[1:]:
        sb = span["bbox"]
        cb = current["bbox"]

        # Check if this span is close to the current region
        # Vertical proximity: within 1.5x line height
        line_height = cb[3] - cb[1]
        vertical_gap = sb[1] - cb[3]
        horizontal_gap = sb[0] - cb[2]

        # Same line or adjacent line
        if vertical_gap < line_height * 1.5 and horizontal_gap < page_width * 0.3:
            # Merge into current region
            current["bbox"][0] = min(current["bbox"][0], sb[0])
            current["bbox"][1] = min(current["bbox"][1], sb[1])
            current["bbox"][2] = max(current["bbox"][2], sb[2])
            current["bbox"][3] = max(current["bbox"][3], sb[3])
            current["line_bbox"][0] = min(current["line_bbox"][0], span["line_bbox"][0])
            current["line_bbox"][1] = min(current["line_bbox"][1], span["line_bbox"][1])
            current["line_bbox"][2] = max(current["line_bbox"][2], span["line_bbox"][2])
            current["line_bbox"][3] = max(current["line_bbox"][3], span["line_bbox"][3])
            current["spans"].append(span)
        else:
            # Start a new region
            regions.append(current)
            current = {
                "bbox": list(sb),
                "line_bbox": list(span["line_bbox"]),
                "spans": [span],
            }

    regions.append(current)

    # Filter out very small regions (likely false positives)
    min_width = 10  # pixels
    regions = [r for r in regions if (r["bbox"][2] - r["bbox"][0]) > min_width]

    return regions


def _classify_inline_display(
    bbox: list, line_bbox: list, page_width: float
) -> bool:
    """Determine if a formula region is inline or display.

    Display formulas typically:
    - Span a significant portion of the line width
    - Are on their own line (formula width ≈ line content width)

    Returns True if inline, False if display.
    """
    formula_width = bbox[2] - bbox[0]
    line_width = line_bbox[2] - line_bbox[0]

    # If formula takes up most of the line content, it's display mode
    if line_width > 0 and formula_width / line_width > 0.7:
        return False  # display

    # If formula is narrow relative to page, likely inline
    if formula_width / page_width < 0.3:
        return True  # inline

    return False  # default to display for ambiguous cases


def _get_page_context(page: pymupdf.Page, bbox: tuple) -> str:
    """Get text surrounding the formula region as context."""
    # Expand bbox vertically to capture surrounding text
    x0, y0, x1, y1 = bbox
    height = y1 - y0
    expanded = pymupdf.Rect(0, max(0, y0 - height * 2), page.rect.width, y1 + height * 2)
    text = page.get_text("text", clip=expanded).strip()
    return text[:300]
