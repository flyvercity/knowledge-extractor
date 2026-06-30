"""Render PDF formula regions as cropped PNG images for AI vision."""

import logging
from pathlib import Path

import pymupdf

from . import FormulaRegion

log = logging.getLogger("knowledge_extractor")

# Padding around the formula bounding box (in points)
PADDING = 4
# DPI for rendering formula regions
RENDER_DPI = 200


def render_formula_regions(
    doc: pymupdf.Document,
    regions: list[FormulaRegion],
    temp_dir: Path,
) -> list[FormulaRegion]:
    """Render detected formula regions as PNG images.

    Updates each FormulaRegion's image_path field with the path to the
    rendered PNG file. Returns the same list with updated paths.
    """
    if not regions:
        return regions

    formulas_dir = temp_dir / "formulas"
    formulas_dir.mkdir(parents=True, exist_ok=True)

    for idx, region in enumerate(regions):
        page = doc[region.page_num - 1]  # page_num is 1-indexed
        img_path = formulas_dir / f"page{region.page_num}_formula{idx}.png"

        # Add padding to the bounding box
        x0, y0, x1, y1 = region.bbox
        clip = pymupdf.Rect(
            max(0, x0 - PADDING),
            max(0, y0 - PADDING),
            min(page.rect.width, x1 + PADDING),
            min(page.rect.height, y1 + PADDING),
        )

        # Render the clipped region at high DPI
        pix = page.get_pixmap(clip=clip, dpi=RENDER_DPI)
        pix.save(str(img_path))

        region.image_path = img_path
        log.debug(
            f"Rendered formula region: page {region.page_num}, "
            f"bbox={region.bbox}, saved to {img_path.name}"
        )

    return regions
