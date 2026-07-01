import base64
import re
import time
import logging
import os
from pathlib import Path

from lxml import etree
from openrouter import OpenRouter

log = logging.getLogger("knowledge_extractor")


class AIProviderError(Exception):
    """Raised when the AI provider is configured but fails after all retries."""
    pass


def _clean_omml(xml_str: str) -> str:
    """Strip formatting noise from OMML XML to produce a concise math-only representation."""
    try:
        root = etree.fromstring(xml_str)
    except etree.XMLSyntaxError:
        return xml_str

    # Remove all w:rPr (run properties / font formatting) and m:ctrlPr elements
    # These contain font names, italic flags, etc. that don't affect math structure
    ns_w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    ns_m = "http://schemas.openxmlformats.org/officeDocument/2006/math"
    for tag in [f"{{{ns_w}}}rPr", f"{{{ns_m}}}ctrlPr", f"{{{ns_m}}}fPr"]:
        for elem in root.findall(f".//{tag}"):
            parent = elem.getparent()
            if parent is not None:
                parent.remove(elem)

    etree.cleanup_namespaces(root)
    return etree.tostring(root, encoding="unicode")

IMAGE_PROMPT = """Analyze this image from a technical document.
- If it's a diagram, flowchart, or architecture: convert to Mermaid syntax in a ```mermaid code block.
- If it's a chart or graph: describe the data, axes, and trends.
- If it's a photo or screenshot: provide a detailed textual description.
- If it's a logo or decorative element: respond with just "DECORATIVE".

Context from surrounding document:
{context}"""

FORMULA_IMAGE_PROMPT = """Convert this mathematical formula image to LaTeX notation.

Rules:
- Output ONLY the LaTeX expression, nothing else
- Do NOT include $ delimiters or \\begin{{equation}} wrappers
- Use standard LaTeX math commands (\\int, \\sum, \\frac, \\sqrt, etc.)
- For matrices use \\begin{{pmatrix}} or \\begin{{bmatrix}} as appropriate
- For Greek letters use standard commands (\\alpha, \\beta, \\gamma, etc.)
- Preserve subscripts and superscripts accurately
- If the image is unclear or not a formula, respond with "UNCLEAR"

Context from surrounding document:
{context}"""

FORMULA_OMML_PROMPT = """Convert this Office Math ML (OMML) XML to LaTeX notation.

Rules:
- Output ONLY the LaTeX expression, nothing else
- Do NOT include $ delimiters or \\begin{{equation}} wrappers
- Use standard LaTeX math commands (\\int, \\sum, \\frac, \\sqrt, etc.)
- For matrices use \\begin{{pmatrix}} or \\begin{{bmatrix}} as appropriate
- For Greek letters use standard commands (\\alpha, \\beta, \\gamma, etc.)
- Preserve subscripts and superscripts accurately
- If the XML is malformed or not a formula, respond with "UNCLEAR"

OMML XML:
{omml_xml}

Context from surrounding document:
{context}"""

CLEANUP_PROMPT = """Clean up this markdown extracted from a technical document.
- Remove non-essential content (redundant headers, boilerplate disclaimers, page numbers)
- Preserve ALL technical information, data, and diagrams
- Fix formatting issues
- Lines starting with "Figure:" are image descriptions — keep them exactly as-is, do NOT convert them to markdown image syntax like ![...](...) 
- Do NOT add any markdown image references (![...](...)) in the output
- Output clean markdown only, no explanations.

Document:
{content}"""


class AIClient:
    def __init__(self, model: str):
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            log.warning("OPENROUTER_API_KEY not set — AI steps will be skipped")
        self.client = OpenRouter(api_key=api_key) if api_key else None
        self.model = model
        self.calls = 0

    def describe_image(self, image_path: Path, context: str = "") -> str | None:
        if not self.client:
            return None
        data = base64.b64encode(image_path.read_bytes()).decode()
        ext = image_path.suffix.lower().lstrip(".")
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                "gif": "image/gif", "bmp": "image/bmp", "tiff": "image/tiff"}.get(ext, "image/png")

        prompt = IMAGE_PROMPT.format(context=context[:500] if context else "No context available")
        log.debug(f"AI describe_image: {image_path.name}, context={context[:80]}...")

        response = self._call([
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}},
            ]}
        ])
        if response and response.strip().upper() == "DECORATIVE":
            log.debug(f"AI: image {image_path.name} classified as decorative")
            return ""
        return response

    def convert_formula_to_latex(
        self, *, image_path: "Path | None" = None, omml_xml: str | None = None,
        context: str = ""
    ) -> str | None:
        """Convert a formula to LaTeX using AI vision.

        Provide either image_path (for PDF formula regions) or omml_xml
        (for DOCX/PPTX OMML elements). Returns the LaTeX string or None.
        """
        if not self.client:
            return None

        if image_path is not None:
            # Image-based conversion (PDF formulas)
            data = base64.b64encode(image_path.read_bytes()).decode()
            ext = image_path.suffix.lower().lstrip(".")
            mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                    "gif": "image/gif"}.get(ext, "image/png")

            prompt = FORMULA_IMAGE_PROMPT.format(context=context[:300] if context else "")
            response = self._call([
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}},
                ]}
            ])
        elif omml_xml is not None:
            # Text-based conversion (DOCX/PPTX OMML)
            clean_xml = _clean_omml(omml_xml)
            prompt = FORMULA_OMML_PROMPT.format(
                omml_xml=clean_xml[:3000],
                context=context[:300] if context else "",
            )
            response = self._call([
                {"role": "user", "content": prompt}
            ])
        else:
            log.warning("convert_formula_to_latex called without image or OMML")
            return None

        if response and response.strip().upper() == "UNCLEAR":
            log.debug("AI: formula classified as unclear")
            return None

        # Clean up response: strip code fences, dollar signs, whitespace
        if response:
            response = response.strip()
            # Remove markdown code fences if present
            if response.startswith("```"):
                lines = response.split("\n")
                response = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
            # Remove wrapping $ or $$
            response = response.strip().strip("$").strip()

        return response

    def cleanup_content(self, markdown: str) -> str | None:
        if not self.client:
            return None
        if len(markdown.strip()) < 100:
            return markdown

        # Process in chunks to avoid token limits without losing content
        chunk_size = 12000
        if len(markdown) <= chunk_size:
            log.info(f"    AI cleanup: {len(markdown)} chars (single chunk)")
            result = self._call([
                {"role": "user", "content": CLEANUP_PROMPT.format(content=markdown)}
            ])
            log.info(f"    AI cleanup: done, {len(result)} chars returned")
            return result

        # Split on section boundaries (## headers) to preserve structure
        chunks = self._split_into_chunks(markdown, chunk_size)
        log.info(f"    AI cleanup: {len(markdown)} chars split into {len(chunks)} chunks")

        cleaned_parts = []
        t_start = time.time()
        for i, chunk in enumerate(chunks):
            log.info(f"    AI cleanup chunk {i + 1}/{len(chunks)}: {len(chunk)} chars...")
            t_chunk = time.time()
            cleaned = self._call([
                {"role": "user", "content": CLEANUP_PROMPT.format(content=chunk)}
            ])
            elapsed_chunk = time.time() - t_chunk
            log.info(f"    AI cleanup chunk {i + 1}/{len(chunks)}: done in {elapsed_chunk:.1f}s, {len(cleaned)} chars returned")
            cleaned_parts.append(cleaned)

        total_elapsed = time.time() - t_start
        total_chars = sum(len(p) for p in cleaned_parts)
        log.info(f"    AI cleanup: all {len(chunks)} chunks done in {total_elapsed:.1f}s, {total_chars} chars total")

        return "\n\n".join(cleaned_parts)

        return "\n\n".join(cleaned_parts)

    @staticmethod
    def _split_into_chunks(text: str, max_size: int) -> list[str]:
        """Split markdown into chunks at section boundaries (## headers)."""
        # Split at ## headers while keeping the header with its section
        sections = re.split(r'(?=^## )', text, flags=re.MULTILINE)
        sections = [s for s in sections if s.strip()]

        chunks: list[str] = []
        current = ""
        for section in sections:
            if len(current) + len(section) > max_size and current:
                chunks.append(current)
                current = section
            else:
                current += section
        if current:
            chunks.append(current)

        # If no ## headers found or sections are too large, fall back to line-based split
        final_chunks: list[str] = []
        for chunk in chunks:
            if len(chunk) <= max_size:
                final_chunks.append(chunk)
            else:
                # Split oversized chunk at paragraph boundaries
                lines = chunk.split("\n")
                part = ""
                for line in lines:
                    if len(part) + len(line) + 1 > max_size and part:
                        final_chunks.append(part)
                        part = line + "\n"
                    else:
                        part += line + "\n"
                if part:
                    final_chunks.append(part)

        return final_chunks

    def _call(self, messages: list, retries: int = 3) -> str:
        last_error = None
        for attempt in range(retries):
            try:
                response = self.client.chat.send(model=self.model, messages=messages)
                self.calls += 1
                result = response.choices[0].message.content
                log.debug(f"AI response: {len(result)} chars")
                return result
            except Exception as e:
                last_error = e
                log.warning(f"AI call failed (attempt {attempt + 1}/{retries}): {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
        raise AIProviderError(
            f"AI provider failed after {retries} retries: {last_error}"
        )
