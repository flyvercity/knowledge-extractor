import base64
import time
import logging
import os
from pathlib import Path

from openrouter import OpenRouter

log = logging.getLogger("knowledge_extractor")

IMAGE_PROMPT = """Analyze this image from a technical document.
- If it's a diagram, flowchart, or architecture: convert to Mermaid syntax in a ```mermaid code block.
- If it's a chart or graph: describe the data, axes, and trends.
- If it's a photo or screenshot: provide a detailed textual description.
- If it's a logo or decorative element: respond with just "DECORATIVE".

Context from surrounding document:
{context}"""

CLEANUP_PROMPT = """Clean up this markdown extracted from a technical document.
- Remove non-essential content (redundant headers, boilerplate disclaimers, page numbers)
- Preserve ALL technical information, data, and diagrams
- Fix formatting issues
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

    def cleanup_content(self, markdown: str) -> str | None:
        if not self.client:
            return None
        if len(markdown.strip()) < 100:
            return markdown
        # Truncate to avoid token limits
        content = markdown[:15000]
        log.debug(f"AI cleanup: {len(content)} chars")
        return self._call([
            {"role": "user", "content": CLEANUP_PROMPT.format(content=content)}
        ])

    def _call(self, messages: list, retries: int = 3) -> str | None:
        for attempt in range(retries):
            try:
                response = self.client.chat.send(model=self.model, messages=messages)
                self.calls += 1
                result = response.choices[0].message.content
                log.debug(f"AI response: {len(result)} chars")
                return result
            except Exception as e:
                log.warning(f"AI call failed (attempt {attempt + 1}): {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
        return None
