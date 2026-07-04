"""Formula detection and LaTeX conversion for DOCX, PPTX, and PDF documents."""

from dataclasses import dataclass, field
from pathlib import Path


OMML_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
FORMULA_MARKER_PATTERN = r"<<FORMULA:(\d+)>>"


@dataclass
class FormulaRef:
    """A detected formula from a DOCX or PPTX document."""

    omml_xml: str
    is_inline: bool
    context_text: str = ""

    def marker(self, index: int) -> str:
        return f"<<FORMULA:{index}>>"


@dataclass
class FormulaRegion:
    """A detected formula region in a PDF page."""

    page_num: int
    bbox: tuple[float, float, float, float]  # (x0, y0, x1, y1)
    is_inline: bool
    context_text: str = ""
    image_path: Path | None = None

    def marker(self, index: int) -> str:
        return f"<<FORMULA:{index}>>"


@dataclass
class ExtractionResult:
    """Result from an extractor: markdown content plus detected formulas."""

    markdown: str
    formulas: list[FormulaRef | FormulaRegion] = field(default_factory=list)
    is_scanned: bool = False
