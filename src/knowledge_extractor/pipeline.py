import re
import time
import logging
from pathlib import Path

from .discovery import DiscoveredFile
from .tracker import ProgressTracker
from .filters import filter_content
from .ai import AIClient
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

_ai_client: AIClient | None = None


def _get_ai(model: str) -> AIClient:
    global _ai_client
    if _ai_client is None:
        _ai_client = AIClient(model)
    return _ai_client


def process_file(file: DiscoveredFile, args, tracker: ProgressTracker, logger: logging.Logger):
    start = time.time()

    # 1. Extract
    extractor = EXTRACTORS[file.format_type]
    intermediate_md = extractor(file.path, args.temp)

    # Save intermediate
    inter_path = args.temp / file.relative_path.with_suffix(".md")
    inter_path.parent.mkdir(parents=True, exist_ok=True)
    inter_path.write_text(intermediate_md, encoding="utf-8")
    log.debug(f"Intermediate saved: {inter_path}")

    # 2. Heuristic filter
    filtered_md = filter_content(intermediate_md, file.format_type)

    # 3. AI image analysis — replace image refs with text
    ai = _get_ai(args.model)
    final_md = _replace_images_with_ai(filtered_md, ai)

    # 4. AI cleanup
    cleaned = ai.cleanup_content(final_md)
    if cleaned:
        final_md = cleaned

    # 5. Write final output
    out_path = args.output / file.relative_path.with_suffix(".md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(final_md, encoding="utf-8")

    # 6. Track
    tracker.mark_processed(file, out_path)
    elapsed = time.time() - start
    log.info(f"  Done in {elapsed:.1f}s (AI calls: {ai.calls})")


def _replace_images_with_ai(markdown: str, ai: AIClient) -> str:
    pattern = re.compile(r"!\[image\]\((.+?)\)")
    matches = list(pattern.finditer(markdown))
    if not matches:
        return markdown

    result = markdown
    for match in reversed(matches):  # reverse to preserve positions
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
        replacement = f"\n{description}\n" if description else ""
        result = result[:match.start()] + replacement + result[match.end():]

    return result
