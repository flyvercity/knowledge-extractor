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


class AIBadRequestError(Exception):
    """Raised when the AI provider returns a 400 bad request (non-retryable)."""
    pass


# HTTP status codes that should not be retried
_NO_RETRY_STATUSES = {400, 401, 403, 404}


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

OCR_PROMPT = """Extract ALL text from this scanned document page as clean Markdown.

Rules:
- Output the text exactly as it appears on the page
- Preserve paragraph structure with blank lines between paragraphs
- Preserve headings, bullet points, and numbered lists using markdown formatting
- Preserve tables using markdown table syntax
- Mathematical formulas: convert to LaTeX notation. Inline formulas wrap with $...$, display/block formulas wrap with $$...$$
- Diagrams, flowcharts, or architecture figures: convert to Mermaid syntax in a ```mermaid code block
- Charts or graphs: describe the data, axes, and trends in a "Figure:" paragraph
- Photos or screenshots: describe briefly in a "Figure:" paragraph
- Logos or decorative elements: skip entirely
- Do NOT add any commentary or explanations — only the extracted content
- If the page is blank or contains no readable text, respond with "BLANK_PAGE"

Output the extracted content in clean Markdown:"""

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


TRANSLATE_PROMPT = """Translate this Markdown document from {source_language} into English.

Rules:
- Translate ALL natural-language text into English: prose, headings, table cell text,
  list items, and "Figure:" image descriptions.
- Preserve the Markdown structure exactly: heading levels, list markers, table layout,
  blank lines, and link/URL targets.
- Do NOT translate or alter fenced code blocks (```...```) other than human-language
  comments; leave code, identifiers, and syntax intact.
- LaTeX math: keep the delimiters ($...$ and $$...$$) and the mathematical expressions
  exactly as-is. Do not translate variable names or commands.
- URLs and link targets must remain unchanged (you may translate visible link text).
- Mermaid diagrams (```mermaid blocks): translate ONLY the human-readable label text that
  appears inside brackets or quotes. Never modify node identifiers, arrows, or structural
  keywords. Keywords such as `graph`, `flowchart`, `subgraph`, `end`, and edges like
  `-->`, `---`, `-.->` must stay verbatim.
  Example: `A[Angemeldet]` becomes `A[Logged in]` — the node id `A` and the brackets stay,
  only the label text is translated. `graph LR` stays `graph LR`.
- Output ONLY the translated Markdown, with no commentary, preamble, or explanation.

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
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost = 0.0

    def ocr_page(self, image_path: Path) -> str | None:
        """OCR a scanned page image, extracting text content."""
        if not self.client:
            return None
        data = base64.b64encode(image_path.read_bytes()).decode()
        ext = image_path.suffix.lower().lstrip(".")
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                "gif": "image/gif", "bmp": "image/bmp", "tiff": "image/tiff"}.get(ext, "image/png")

        try:
            response = self._call([
                {"role": "user", "content": [
                    {"type": "text", "text": OCR_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}},
                ]}
            ])
        except AIBadRequestError as e:
            log.warning(f"AI: OCR failed for {image_path.name} — unprocessable: {e}")
            return None

        if response and response.strip().upper() == "BLANK_PAGE":
            return ""
        return response

    def describe_image(self, image_path: Path, context: str = "") -> str | None:
        if not self.client:
            return None
        data = base64.b64encode(image_path.read_bytes()).decode()
        ext = image_path.suffix.lower().lstrip(".")
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                "gif": "image/gif", "bmp": "image/bmp", "tiff": "image/tiff"}.get(ext, "image/png")

        prompt = IMAGE_PROMPT.format(context=context[:500] if context else "No context available")
        log.debug(f"AI describe_image: {image_path.name}, context={context[:80]}...")

        try:
            response = self._call([
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}},
                ]}
            ])
        except AIBadRequestError as e:
            log.warning(f"AI: skipping image {image_path.name} — unprocessable: {e}")
            return None

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

        try:
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
        except AIBadRequestError as e:
            src = image_path.name if image_path else "OMML"
            log.warning(f"AI: skipping formula ({src}) — unprocessable: {e}")
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

    def cleanup_content(self, markdown: str, chunk_size: int = 10000) -> str | None:
        if not self.client:
            return None
        if len(markdown.strip()) < 100:
            return markdown

        # Small documents: single pass
        if len(markdown) <= chunk_size:
            prompt = CLEANUP_PROMPT.format(content=markdown)
            try:
                response = self._call([
                    {"role": "user", "content": prompt}
                ])
            except AIBadRequestError as e:
                log.warning(f"AI: content cleanup failed — unprocessable: {e}")
                return None
            return response

        # Large documents: split on section boundaries to preserve structure
        chunks = self._split_into_chunks(markdown, chunk_size)
        log.info(f"    AI cleanup: {len(markdown)} chars split into {len(chunks)} chunks")

        cleaned_parts = []
        t_start = time.time()
        for i, chunk in enumerate(chunks):
            log.info(f"    AI cleanup chunk {i + 1}/{len(chunks)}: {len(chunk)} chars...")
            t_chunk = time.time()
            try:
                cleaned = self._call([
                    {"role": "user", "content": CLEANUP_PROMPT.format(content=chunk)}
                ])
            except AIBadRequestError as e:
                log.warning(f"AI: cleanup chunk {i + 1} failed — unprocessable: {e}")
                cleaned_parts.append(chunk)
                continue
            elapsed_chunk = time.time() - t_chunk
            log.info(f"    AI cleanup chunk {i + 1}/{len(chunks)}: done in {elapsed_chunk:.1f}s, {len(cleaned)} chars returned")
            cleaned_parts.append(cleaned)

        total_elapsed = time.time() - t_start
        total_chars = sum(len(p) for p in cleaned_parts)
        log.info(f"    AI cleanup: all {len(chunks)} chunks done in {total_elapsed:.1f}s, {total_chars} chars total")

        return "\n\n".join(cleaned_parts)

    def translate_content(
        self, markdown: str, source_language: str, chunk_size: int = 50000
    ) -> str | None:
        """Translate assembled Markdown from source_language into English.

        Mirrors cleanup_content: returns None if no client; single-pass under the
        threshold; otherwise chunked via _split_into_chunks. Both AIBadRequestError
        and AIProviderError are caught per chunk so a transient/provider error never
        crashes the document — the original chunk text is retained and a warning logged.
        """
        if not self.client:
            return None
        if len(markdown.strip()) < 100:
            return markdown

        # Small documents: single pass
        if len(markdown) <= chunk_size:
            prompt = TRANSLATE_PROMPT.format(
                source_language=source_language, content=markdown
            )
            try:
                response = self._call([{"role": "user", "content": prompt}])
            except (AIBadRequestError, AIProviderError) as e:
                log.warning(f"AI: translation failed — {e}")
                return None
            return response

        # Large documents: split on section boundaries to preserve structure
        chunks = self._split_into_chunks(markdown, chunk_size)
        log.info(
            f"    AI translate: {len(markdown)} chars split into {len(chunks)} chunks"
        )

        translated_parts = []
        t_start = time.time()
        for i, chunk in enumerate(chunks):
            log.info(
                f"    AI translate chunk {i + 1}/{len(chunks)}: {len(chunk)} chars..."
            )
            t_chunk = time.time()
            try:
                translated = self._call([
                    {"role": "user", "content": TRANSLATE_PROMPT.format(
                        source_language=source_language, content=chunk
                    )}
                ])
            except (AIBadRequestError, AIProviderError) as e:
                log.warning(
                    f"AI: translation chunk {i + 1} failed — {e}; keeping original text"
                )
                translated_parts.append(chunk)
                continue
            elapsed_chunk = time.time() - t_chunk
            log.info(
                f"    AI translate chunk {i + 1}/{len(chunks)}: done in "
                f"{elapsed_chunk:.1f}s, {len(translated)} chars returned"
            )
            translated_parts.append(translated)

        total_elapsed = time.time() - t_start
        total_chars = sum(len(p) for p in translated_parts)
        log.info(
            f"    AI translate: all {len(chunks)} chunks done in {total_elapsed:.1f}s, "
            f"{total_chars} chars total"
        )

        return "\n\n".join(translated_parts)

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
                # Split oversized chunk at paragraph boundaries, but never split inside
                # a fenced code block (``` ... ```) — that would corrupt code/mermaid.
                lines = chunk.split("\n")
                part = ""
                in_fence = False
                for line in lines:
                    is_fence_delim = line.lstrip().startswith("```")
                    # Only break at a boundary when we are NOT inside a code fence and
                    # the current line is not itself a fence delimiter (so an opening or
                    # closing ``` stays attached to its block).
                    if (
                        not in_fence
                        and not is_fence_delim
                        and len(part) + len(line) + 1 > max_size
                        and part
                    ):
                        final_chunks.append(part)
                        part = line + "\n"
                    else:
                        part += line + "\n"
                    if is_fence_delim:
                        in_fence = not in_fence
                if part:
                    final_chunks.append(part)

        return final_chunks

    def log_usage_summary(self):
        """Log a summary of total AI usage and cost."""
        total_tokens = self.total_prompt_tokens + self.total_completion_tokens
        log.info(
            f"AI usage [{self.model}]: {self.calls} calls, "
            f"{total_tokens:,} tokens ({self.total_prompt_tokens:,} prompt + "
            f"{self.total_completion_tokens:,} completion), "
            f"cost: ${self.total_cost:.4f}"
        )

    def _call(self, messages: list, retries: int = 5) -> str:
        last_error = None
        # Compute request metadata for diagnostics
        payload_chars = sum(
            len(str(m.get("content", ""))) if isinstance(m, dict) else 0
            for m in messages
        )
        has_image = any(
            isinstance(m.get("content"), list) and
            any(c.get("type") == "image_url" for c in m["content"] if isinstance(c, dict))
            for m in messages if isinstance(m, dict)
        )
        req_type = "vision" if has_image else "text"

        for attempt in range(retries):
            try:
                response = self.client.chat.send(model=self.model, messages=messages)
                self.calls += 1
                result = response.choices[0].message.content

                # Track usage/cost
                if response.usage:
                    prompt_tok = response.usage.prompt_tokens or 0
                    compl_tok = response.usage.completion_tokens or 0
                    raw_cost = getattr(response.usage, 'cost', None)
                    cost = float(raw_cost) if isinstance(raw_cost, (int, float)) else 0.0
                    self.total_prompt_tokens += prompt_tok
                    self.total_completion_tokens += compl_tok
                    self.total_cost += cost
                    log.debug(
                        f"AI response: {len(result)} chars, "
                        f"tokens={prompt_tok}+{compl_tok}, cost=${cost:.6f}"
                    )
                else:
                    log.debug(f"AI response: {len(result)} chars (no usage data)")

                return result
            except Exception as e:
                last_error = e
                error_type = type(e).__name__
                status = getattr(e, 'status_code', None)
                message = getattr(e, 'message', str(e))
                body = getattr(e, 'body', None)

                diag_parts = [
                    f"type={error_type}",
                    f"status={status}" if status else None,
                    f"message={message}",
                    f"model={self.model}",
                    f"req={req_type}",
                    f"payload={payload_chars} chars",
                    f"call_num={self.calls + 1}",
                ]
                diag = ", ".join(p for p in diag_parts if p)

                # Non-retryable: bad input or auth — no point retrying
                if status in _NO_RETRY_STATUSES:
                    log.error(f"AI call failed (non-retryable, status={status}): [{diag}]")
                    if body:
                        log.error(f"AI error response body: {body}")
                    if status == 400:
                        raise AIBadRequestError(
                            f"AI provider rejected request (400, {req_type}, {payload_chars} chars): {message}"
                        ) from e
                    raise AIProviderError(
                        f"AI provider error (status={status}): {message}"
                    ) from e

                if attempt < retries - 1:
                    delay = 2 ** (attempt + 1)  # 2, 4, 8, 16s
                    log.warning(f"AI call failed (attempt {attempt + 1}/{retries}): [{diag}] — retrying in {delay}s")
                    time.sleep(delay)
                else:
                    log.error(f"AI call failed (attempt {attempt + 1}/{retries}): [{diag}]")
                    if body:
                        log.error(f"AI error response body: {body}")

        raise AIProviderError(
            f"AI provider failed after {retries} retries ({req_type}, {payload_chars} chars, "
            f"status={getattr(last_error, 'status_code', 'unknown')}): {last_error}"
        )
