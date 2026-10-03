---
type: architecture-component
title: Document Extractors
description: The document extractor subsystem converts DOCX, PPTX, PDF, XLSX, and image files into structured markdown with embedded image references and formula markers for the knowledge extraction pipeline.
tags: [extractors, docx, pptx, pdf, xlsx, image, ocr, formulas, omml, architecture]
verified:
  - by: openwiki/0.6.1
    at: 2026-10-03T09:19:39.759Z
sources:
  - id: openwiki-source-91e61d3cf9bd4a229fd61f11
    resource: repo://src/knowledge_extractor/extractors/docx_extractor.py
  - id: openwiki-source-3d612ef344356aac14a96c54
    resource: repo://src/knowledge_extractor/extractors/excel_extractor.py
  - id: openwiki-source-5ae2a9668cabb3d99fa9a1d6
    resource: repo://src/knowledge_extractor/extractors/image_extractor.py
  - id: openwiki-source-28682b76ee4ab4bb1d63a32b
    resource: repo://src/knowledge_extractor/extractors/pdf_extractor.py
  - id: openwiki-source-07fc4d25d8bec2776c1572dc
    resource: repo://src/knowledge_extractor/extractors/pptx_extractor.py
  - id: openwiki-source-8bf121937bfa6e6257d32a98
    resource: repo://src/knowledge_extractor/extractors/utils.py
  - id: openwiki-source-8ec9b15e28bf938a767c5660
    resource: repo://src/knowledge_extractor/formulas/__init__.py
  - id: openwiki-source-0917d983c11f124f79a3e9e7
    resource: repo://src/knowledge_extractor/formulas/pdf_formulas.py
  - id: openwiki-source-0f888ee7a72310b9b85d4c30
    resource: repo://src/knowledge_extractor/formulas/renderer.py
generated: { by: "openwiki/0.6.1", at: "2026-10-03T09:19:39.759Z" }
---

# Document Extractors

The document extractors are the core ingestion layer of the knowledge extraction pipeline. Each extractor converts a specific file format into a standardized `ExtractionResult` containing markdown text, image paths, and detected mathematical formulas. The extractors are located in `src/knowledge_extractor/extractors/` and share a common contract for integration with the pipeline.

## Architecture Overview

<!-- openwiki: mermaid parse failed and this diagram was converted to a text fence so it does not break rendering. Fix the diagram source and restore the mermaid fence. Parser error: Heuristic: an unescaped angle bracket inside a label breaks rendering; rephrase the label. -->
```text
flowchart TD
    Input["Input File"] --> Router["Extractor Router"]
    Router -->|DOCX| DOCX["docx_extractor.py"]
    Router -->|PPTX| PPTX["pptx_extractor.py"]
    Router -->|PDF| PDF["pdf_extractor.py"]
    Router -->|XLSX| XLSX["excel_extractor.py"]
    Router -->|Image| IMG["image_extractor.py"]
    
    subgraph "Common Utilities"
        Utils["utils.py<br/>get_img_dir()"]
    end
    
    subgraph "Formula Support"
        Formulas["formulas/<br/>FormulaRef, FormulaRegion"]
        PDF_Formulas["pdf_formulas.py<br/>detect_formulas()"]
        Renderer["renderer.py<br/>render_formula_regions()"]
    end
    
    DOCX --> Utils
    PPTX --> Utils
    PDF --> Formulas
    PDF --> PDF_Formulas
    PDF --> Renderer
    PPTX --> Formulas
```

## Extractor Contract

All extractors follow a consistent interface pattern, though the return types differ slightly based on format capabilities:

| Extractor | Entry Point | Return Type |
|-----------|-------------|-------------|
| DOCX | `extract_docx(file_path, temp_dir)` | `ExtractionResult` |
| PPTX | `extract_pptx(file_path, temp_dir)` | `ExtractionResult` |
| PDF | `extract_pdf(file_path, temp_dir)` | `ExtractionResult` |
| XLSX | `extract_xlsx(file_path, temp_dir)` | `str` (markdown only) |
| Image | `extract_image(file_path, temp_dir)` | `str` (markdown only) |

The `ExtractionResult` dataclass (defined in `src/knowledge_extractor/formulas/__init__.py`) wraps the extraction output:

```python
@dataclass
class ExtractionResult:
    markdown: str
    formulas: list[FormulaRef | FormulaRegion] = field(default_factory=list)
    is_scanned: bool = False
```

- `markdown` — The extracted content as markdown text with image references and formula markers
- `formulas` — List of detected formula references (DOCX/PPTX) or regions (PDF)
- `is_scanned` — Flag indicating whether the PDF was treated as scanned (OCR mode)

## Image Directory Management

All extractors that produce images use the shared `get_img_dir()` utility from `utils.py`:

```python
def get_img_dir(temp_dir: Path, file_path: Path) -> Path:
    """Create a safe, unique image directory for a source file."""
    h = hashlib.md5(str(file_path).encode()).hexdigest()[:8]
    safe_name = file_path.stem[:40].replace(" ", "_") + f"_{h}"
    img_dir = temp_dir / "images" / safe_name
    img_dir.mkdir(parents=True, exist_ok=True)
    return img_dir
```

This creates a per-file subdirectory under `temp_dir/images/` using a hash of the file path and a truncated filename stem, ensuring:
- Unique directories for each source file
- Safe filenames that avoid path traversal issues
- Predictable structure for downstream image processing

## DOCX Extraction (`docx_extractor.py`)

The DOCX extractor uses python-docx to parse Word documents and produce markdown with heading structure, tables, inline images, and formula markers.

### Processing Flow

1. **Image Extraction**: Iterates through document relationships, extracts all non-external image parts to the image directory
2. **Paragraph Processing**: Walks the document body element-by-element, matching paragraphs to their text content
3. **Heading Detection**: Applies markdown heading syntax based on paragraph style ("Heading 1", "Heading 2", "Heading 3")
4. **Inline Images**: Detects drawing/pict elements in paragraphs and embeds corresponding images
5. **Formula Detection**: Scans for OMML formula elements (see [Formula Detection](#formula-detection))
6. **Table Conversion**: Converts Word tables to markdown table syntax

### Key Behaviors

- **Text Extraction**: Uses paragraph `.text` property for simple cases; builds text from run elements when formulas are present to preserve marker positioning
- **Table Deduplication**: Handles merged cells by deduplicating repeated cell content in row iteration
- **Image Ordering**: Matches inline images to extracted image files by index order; appends any unmatched images at the end

### Output Format

```markdown
# Heading 1 Text

Paragraph text with ![image](path/to/image.png) inline.

| Col1 | Col2 |
|------|------|
| A    | B    |

<<FORMULA:0>>
```

## PPTX Extraction (`pptx_extractor.py`)

The PPTX extractor uses python-pptx to parse PowerPoint presentations, producing per-slide markdown with images, text, tables, speaker notes, and formula markers.

### Processing Flow

1. **Slide Iteration**: Processes each slide with a "Slide N" header
2. **Shape Iteration**: Uses recursive `_iter_shapes()` to handle grouped shapes
3. **Picture Extraction**: Extracts images from picture shapes with content-type-based file extensions
4. **Text Frame Processing**: Extracts text from shapes with text frames, detecting formulas (see [Formula Detection](#formula-detection))
5. **Table Conversion**: Converts PowerPoint tables to markdown
6. **Speaker Notes**: Appends speaker notes as blockquote with "Notes:" prefix

### Shape Handling

| Shape Type | Behavior |
|------------|----------|
| `Picture` | Extract image blob, write to img_dir, emit markdown image reference |
| Text Frame | Extract text, detect OMML formulas, build text with markers |
| Table | Convert to markdown table |
| GroupShape | Recursively iterate child shapes |

### Image Extension Mapping

```python
def _img_ext(content_type: str) -> str:
    return {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif",
            "image/bmp": ".bmp", "image/tiff": ".tiff"}.get(content_type, ".png")
```

### Output Format

```markdown
## Slide 1

Slide title text

![image](path/to/slide1_img0.png)

<<FORMULA:0>>

> **Notes:** Speaker notes text
```

## PDF Extraction (`pdf_extractor.py`)

The PDF extractor uses PyMuPDF (fitz) to handle both text-based and scanned PDFs, with formula region detection and rendering for text PDFs.

### Scanned PDF Detection

The extractor performs a quick scan to determine if a PDF is scanned:

```python
SCANNED_THRESHOLD = 0.8  # 80% of pages must have no extractable text

# Quick scan loop with early exit optimization:
for i in range(total_pages):
    page = doc.load_page(i)
    if not page.get_text("text").strip():
        empty_pages += 1
    remaining = total_pages - (i + 1)
    # Early exit: if even all remaining pages were empty, we still wouldn't hit threshold
    if (empty_pages + remaining) / total_pages < SCANNED_THRESHOLD:
        break
scanned_ratio = empty_pages / total_pages
is_scanned = scanned_ratio >= SCANNED_THRESHOLD
```

**Early Exit Optimization**: The scan stops early when it becomes mathematically impossible to reach the 80% threshold, avoiding unnecessary page loads.

### Text PDF Processing (`_extract_text_pdf`)

For text-based PDFs, the extraction follows this pipeline:

1. **Formula Detection**: Calls `detect_pdf_formulas(doc)` to find all formula regions across all pages
2. **Formula Rendering**: Calls `render_formula_regions()` to crop and save formula regions as PNG images
3. **Page Processing**:
   - For each page, extract text via `page.get_text("text")`
   - Pages with no text are rendered as images (fallback for mixed documents)
   - Insert formula markers into text using `_insert_formula_markers()`
   - Extract embedded images (deduplicated by xref, filtered by minimum size 50x50 pixels)

### Formula Marker Insertion

```python
def _insert_formula_markers(page, text, formulas):
    """Insert formula markers into page text based on vertical position."""
    # Estimate line position from formula bbox vertical center
    y_center = (region.bbox[1] + region.bbox[3]) / 2
    line_idx = int((y_center / page_height) * total_lines)
    
    # Display formulas get their own line; inline formulas appended to end of line
    if is_inline:
        text_lines[line_idx] = text_lines[line_idx] + f" {marker}"
    else:
        text_lines.insert(line_idx + 1, marker)
```

### Scanned PDF Processing (`_extract_scanned_pdf`)

For scanned PDFs, the extractor:

1. **Text Fallback**: Still checks for selectable text on each page (e.g., digitally-created TOC pages)
2. **OCR Preparation**: Renders each text-less page as a PNG at 200 DPI
3. **OCR Tagging**: Uses `![ocr](path)` marker instead of `![image](path)` to signal the pipeline to use OCR-specific prompts rather than generic image description prompts

```python
# Special marker for OCR pipeline routing
lines.append(f"\n![ocr]({img_path.resolve()})\n")
```

### Output Format

```markdown
## Page 1

Text content from page 1.

<<FORMULA:0>>
<<FORMULA:1>>

![image](path/to/page1_img0.png)

## Page 2

![ocr](path/to/page2.png)  # Scanned page
```

## XLSX Extraction (`excel_extractor.py`)

The XLSX extractor uses openpyxl to convert Excel spreadsheets to markdown tables, one per sheet.

### Processing Flow

1. **Load Workbook**: Opens with `read_only=True, data_only=True` for efficient reading of computed values
2. **Sheet Iteration**: Creates a markdown header for each sheet name
3. **Row Collection**: Iterates rows, collecting non-empty rows
4. **Column Normalization**: Pads rows to match the maximum column count
5. **Markdown Table Generation**: Produces header row, separator, and body rows

### Key Behaviors

- **Data-Only Mode**: `data_only=True` returns cached computed values rather than formula strings
- **Empty Row Skipping**: Rows where all cells are `None` are omitted
- **Column Alignment**: Shorter rows are padded with empty strings to maintain table structure

### Output Format

```markdown
## Sheet1

| Col1 | Col2 | Col3 |
|------|------|------|
| A    | B    | C    |
| D    | E    | F    |

## Sheet2

| Header1 | Header2 |
|---------|---------|
| Value   | Value   |
```

## Image Extraction (`image_extractor.py`)

The image extractor handles standalone image files by copying them to the image directory and returning a markdown image reference.

### Processing

```python
def extract_image(file_path: Path, temp_dir: Path) -> str:
    img_dir = get_img_dir(temp_dir, file_path)
    dest = img_dir / file_path.name
    shutil.copy2(file_path, dest)
    return f"![image]({dest.resolve()})\n"
```

- Uses `shutil.copy2()` to preserve file metadata
- Returns a simple markdown image reference with absolute path

## Formula Detection

The system detects mathematical formulas differently depending on the source format.

### OMML Formula Detection (DOCX/PPTX)

For Office documents, formulas are stored in Office Math Markup Language (OMML) format. The detectors distinguish between:

| Type | XML Element | Behavior |
|------|-------------|----------|
| Display Formula | `<m:oMathPara>` | Standalone paragraph/line containing only the formula |
| Inline Formula | `<m:oMath>` (not inside `<m:oMathPara>`) | Formula embedded within text runs |

**DOCX Detection** (`_detect_para_formulas` in `docx_extractor.py`):
- Searches paragraph element for `oMathPara` and `oMath` elements
- Serializes each formula to XML string for later LaTeX conversion
- Records context text (first 200 characters of paragraph)

**PPTX Detection** (`_detect_shape_formulas` in `pptx_extractor.py`):
- Searches text frame element (`_txBody`) for formula elements
- Includes slide number in context text for traceability
- Distinguishes display vs. inline by checking parent element tag

### PDF Formula Detection (`pdf_formulas.py`)

For PDFs, formula detection uses heuristic analysis since there is no standardized formula markup:

**Detection Heuristics**:

1. **Math Font Detection**: Checks span font names against known math font list:
   ```python
   MATH_FONTS = {
       "symbol", "cambria math", "cmmi", "cmsy", "cmex", "cmr",
       "mt extra", "math", "euclid", "asana math", "xits math",
       "stix", "latin modern math", "libertinus math",
   }
   ```

2. **Unicode Range Analysis**: Checks for characters in mathematical Unicode ranges:
   - Greek letters (U+0391-U+03C9)
   - Superscripts/subscripts (U+2070-U+209F)
   - Arrows (U+2190-U+21FF)
   - Mathematical operators (U+2200-U+22FF)
   - Supplemental math operators (U+2A00-U+2AFF)
   - Mathematical alphanumeric symbols (U+1D400-U+1D7FF)

3. **Math Character Density**: Classifies a span as math if >30% of characters are math-like, or if it's a short span (≤2 characters) with any math characters

**Region Grouping** (`_group_spans_into_regions`):
- Sorts math spans by vertical then horizontal position
- Groups spans within 1.5x line height vertically and 30% page width horizontally
- Filters out regions narrower than 10 pixels (false positive reduction)

**Inline vs. Display Classification** (`_classify_inline_display`):
- Display mode: formula width >70% of line width
- Inline mode: formula width <30% of page width
- Default: display mode for ambiguous cases

### Formula Rendering (`renderer.py`)

Detected PDF formula regions are rendered as cropped PNG images for AI vision processing:

```python
PADDING = 4       # Points of padding around bbox
RENDER_DPI = 200  # Rendering resolution
```

- Adds padding to bounding box to capture complete formula
- Skips degenerate regions (zero/negative dimensions)
- Saves to `temp_dir/formulas/<safe_name>/pageN_formulaM.png`
- Updates `FormulaRegion.image_path` for downstream processing

## Return Types and Data Flow

The extractors produce two categories of return types:

**Rich Extraction** (DOCX, PPTX, PDF):
- Returns `ExtractionResult` with both markdown and formula metadata
- Formulas are passed to downstream AI processing for LaTeX conversion
- Image paths are embedded in markdown for document reconstruction

**Simple Extraction** (XLSX, Image):
- Returns plain markdown string
- No formula detection capability
- Images are referenced but not analyzed

## Configuration and Dependencies

| Extractor | External Dependency | Purpose |
|-----------|---------------------|---------|
| DOCX | python-docx | Document parsing, OMML access |
| PPTX | python-pptx | Presentation parsing, shape iteration |
| PDF | PyMuPDF (pymupdf) | PDF rendering, text extraction, image extraction |
| XLSX | openpyxl | Spreadsheet reading |
| All (images) | Standard library | shutil, pathlib |

All extractors receive:
- `file_path: Path` — Absolute path to the source file
- `temp_dir: Path` — Base directory for extracted artifacts (images, formula renders)

The temp directory structure follows:
```
temp_dir/
├── images/
│   └── <safe_name>/      # Per-file image directory
│       ├── img_0.png
│       └── page1_img0.png
└── formulas/             # PDF formula renders only
    └── <safe_name>/
        ├── page1_formula0.png
        └── page2_formula1.png
```
