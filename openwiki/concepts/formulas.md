---
type: concept
title: Formulas
description: How mathematical formulas are detected and represented across DOCX/PPTX OMML and PDF heuristic regions, and how they are converted to LaTeX via AI.
tags: [formulas, omml, latex, pdf, docx, pptx, extraction]
verified:
  - by: openwiki/0.6.1
    at: 2026-10-03T09:19:39.759Z
sources:
  - id: openwiki-source-6819e7dda80c789beeb9df42
    resource: repo://src/knowledge_extractor/ai.py
  - id: openwiki-source-28682b76ee4ab4bb1d63a32b
    resource: repo://src/knowledge_extractor/extractors/pdf_extractor.py
  - id: openwiki-source-8ec9b15e28bf938a767c5660
    resource: repo://src/knowledge_extractor/formulas/__init__.py
  - id: openwiki-source-956b72c8905b6a6a9f47fdda
    resource: repo://src/knowledge_extractor/formulas/docx_formulas.py
  - id: openwiki-source-0917d983c11f124f79a3e9e7
    resource: repo://src/knowledge_extractor/formulas/pdf_formulas.py
  - id: openwiki-source-a545b789b48362981ec80559
    resource: repo://src/knowledge_extractor/formulas/pptx_formulas.py
  - id: openwiki-source-0f888ee7a72310b9b85d4c30
    resource: repo://src/knowledge_extractor/formulas/renderer.py
  - id: openwiki-source-513342bd1eabc42db57c6c41
    resource: repo://src/knowledge_extractor/pipeline.py
generated: { by: "openwiki/0.6.1", at: "2026-10-03T09:19:39.759Z" }
---

# Formulas

The knowledge extraction pipeline detects and preserves mathematical formulas from DOCX, PPTX, and PDF source documents. Office formats carry formulas as Office Math Markup Language (OMML) elements, while PDF relies on heuristic detection of math-like glyphs and font names. After detection, formula positions are represented as lightweight markers in the extracted markdown, and downstream AI processing converts each marker into LaTeX notation.

## Data Model

Two formula abstractions exist, depending on source format:

- **FormulaRef** — used for DOCX and PPTX. It carries the raw OMML XML, an inline/display flag, and surrounding context text.
- **FormulaRegion** — used for PDF. It carries a page number, bounding box, inline/display flag, context text, and an optional rendered PNG path.

Both types share a common marker protocol: `FormulaRef.marker(index)` and `FormulaRegion.marker(index)` each return a string in the form `<<FORMULA:N>>`. The regex `FORMULA_MARKER_PATTERN = r"<<FORMULA:(\d+)>>"` is used by the pipeline to locate and replace those markers.

The unified container is `ExtractionResult`:

```python
@dataclass
class ExtractionResult:
    markdown: str
    formulas: list[FormulaRef | FormulaRegion] = field(default_factory=list)
    is_scanned: bool = False
```

Extractor tests and downstream code treat `formulas` as the authoritative formula payload for DOCX, PPTX, and text PDFs; XLSX and standalone image extraction return no formula metadata.

## OMML Detection (DOCX/PPTX)

Office formula detection targets the same OMML elements in both DOCX and PPTX, using namespace `OMML_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"`.

| Type | XML element | Meaning |
|------|-------------|---------|
| Display | `<m:oMathPara>` | Standalone formula paragraph/line |
| Inline | `<m:oMath>` (not inside `<m:oMathPara>`) | Formula embedded in text runs |

The DOCX detector iterates paragraphs, finds `oMathPara` and `oMath` elements, serializes each to XML, and records context from nearby paragraphs. The PPTX detector iterates slides and shapes, finds formula elements inside text frame bodies (`_txBody`), and prefixes context with slide number for traceability.

A key invariant in both detectors is parent-based deduplication: a bare `<m:oMath>` that is a child of `<m:oMathPara>` is treated as part of the display formula and skipped as a separate inline formula.

## PDF Heuristic Detection

PDF detection lives in `pdf_formulas.py` and uses PyMuPDF span-level text analysis rather than a structured math format.

### Detection heuristics

Detection combines three signals:

1. **Math font names** — the detector maintains a known set of math fonts (for example `symbol`, `cambria math`, `cmmi`, `cmsy`, `cmex`, `cmr`, `mt extra`, `xits math`, `stix`, `latin modern math`). A span whose font name contains one of these is treated as math.
2. **Unicode ranges** — several Unicode blocks are treated as math-related, including Greek letters, superscripts/subscripts, arrows, mathematical operators, supplemental math operators, misc math symbols, and mathematical alphanumeric symbols.
3. **Math character density** — a span is math if more than 30% of its characters are math-like, or if it is a short span (up to 2 characters) with any math characters.

### Region grouping

Detected math spans are sorted by vertical then horizontal position and merged into regions when they are vertically close (within about 1.5× line height) and horizontally close (within about 30% of page width). Regions narrower than 10 pixels are filtered out to reduce false positives.

### Inline vs display classification

`_classify_inline_display` decides mode from geometry:

- Display mode if formula width exceeds about 70% of the enclosing line width.
- Inline mode if formula width is under about 30% of page width.
- Otherwise it defaults to display.

## Formula Rendering (PDF)

For PDF formula regions, `renderer.py` creates cropped PNG images for downstream AI vision conversion.

Key behavior:

- Each region is rendered with a padding of 4 points and at 200 DPI.
- Output paths follow `temp_dir/formulas/<safe_name>/pageN_formulaM.png`.
- The `<safe_name>` scheme mirrors the image directory scheme: an MD5 prefix of the source path plus a truncated, space-normalized stem.
- Degenerate bounding boxes are skipped with a warning.
- Each `FormulaRegion.image_path` is updated so the pipeline can later read the image.

## Marker Insertion

Markers are inserted at extraction time, not during AI conversion.

- **DOCX**: paragraphs with display formulas can become a marker-only paragraph; inline formulas are placed by walking paragraph child elements and inserting markers at formula positions.
- **PPTX**: text frames are rebuilt with markers placed for display formulas on their own lines and inline markers appended to shape text.
- **PDF**: `_insert_formula_markers` estimates the target line from the formula’s vertical center relative to page height, then appends inline markers to the estimated line or inserts display markers on the following line.

The result is markdown where each detected formula is replaced by a stable `<<FORMULA:N>>` token while the rest of the document structure is preserved.

## LaTeX Conversion via AI

Formula conversion happens in the pipeline after extraction and before OCR, image analysis, cleanup, and optional translation.

`_process_formulas` scans markdown for `<<FORMULA:N>>` markers, processes them in reverse order so string positions stay valid, and replaces each marker with either LaTeX or a placeholder.

Conversion routing depends on formula type:

- **FormulaRef (DOCX/PPTX)** — `AIClient.convert_formula_to_latex` sends cleaned OMML XML to the model using the OMML prompt.
- **FormulaRegion (PDF)** — the same method sends the rendered PNG as a base64 image using the image formula prompt.

The AIClient applies the following conversion rules and normalizations:

- OMML XML is cleaned before sending by removing run/control/formula property elements that carry font and formatting noise without affecting math structure.
- The model prompt explicitly forbids surrounding `$` or equation wrappers.
- The response is de-fenced and de-dollarized: markdown code fences and wrapping `$` / `$$` are stripped.
- If the model returns `UNCLEAR`, conversion is treated as failed and the marker is replaced with a placeholder.
- If no AI client is configured, the placeholder is `[FORMULA: no API key]`; otherwise a failed conversion yields `[FORMULA: conversion failed]`.

Inline formulas are wrapped as `$latex$`; display formulas are wrapped as `$$\nlatex\n$$`.

## File Roles and Entry Points

- `formulas/__init__.py` — shared formula dataclasses, marker protocol, namespace constant, and marker regex.
- `formulas/docx_formulas.py` — DOCX OMML detector.
- `formulas/pptx_formulas.py` — PPTX OMML detector, including recursive shape iteration.
- `formulas/pdf_formulas.py` — PDF heuristic detector, region grouping, and inline/display classification.
- `formulas/renderer.py` — PDF formula region image rendering.
- `ai.py` — AI prompts and the `convert_formula_to_latex` entrypoint, including OMML cleaning and response normalization.
- `pipeline.py` — marker replacement orchestration (`_process_formulas`, `_convert_single_formula`) and placeholder policy.
- `extractors/docx_extractor.py` — DOCX extraction that calls into formula detection and marker construction.
- `extractors/pptx_extractor.py` — PPTX extraction with shape-level formula detection and marker construction.
- `extractors/pdf_extractor.py` — PDF extraction that runs detection, rendering, and marker insertion for text PDFs.

## Lifecycle and Invariants

1. Detection happens first and produces structured formula objects.
2. Extraction produces markdown with markers and returns formula objects alongside it.
3. PDF formula images are rendered before page text is assembled, so markers can reference a valid image path.
4. AI conversion consumes markers in markdown order using the parallel formula list from extraction.
5. Each marker index must remain within the extracted formulas list; out-of-range markers are skipped with a warning.

Important invariants:

- DOCX/PPTX formulas are represented as OMML XML, not as rendered pixels.
- PDF formulas require rendered images before AI conversion; a region without a renderable image is a conversion failure.
- Marker indices are stable only if extraction and formula processing share the same formula list ordering.
- Cleaned OMML is intentionally stripped of formatting-only elements; structural math elements are preserved.

## Failure Modes

- Missing or malformed OMML XML can still be passed to the AI; the OMML prompt allows the model to reply `UNCLEAR`, and the client treats that as a failed conversion.
- PDF formula regions with degenerate bounding boxes are skipped during rendering.
- Formula regions whose image path is missing or does not exist are converted as failures.
- If the AI client is unavailable, formulas are not dropped; they are replaced by explicit placeholders so downstream consumers can see that conversion was attempted but not completed.

## Extension Points

Formula behavior can be extended by:

- Adding new math fonts or Unicode heuristics in the PDF detector.
- Adjusting region grouping thresholds if formula segmentation is too coarse or too fragmented.
- Changing placeholder text or delimiter policy in the pipeline if downstream LaTeX rendering conventions change.
- Adding a new formula representation type by extending the marker protocol and conversion routing in the pipeline and AIClient.
