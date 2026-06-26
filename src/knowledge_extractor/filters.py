import re
import logging

log = logging.getLogger("knowledge_extractor")


def filter_content(markdown: str, format_type: str) -> str:
    sections = re.split(r"(^## .+$)", markdown, flags=re.MULTILINE)
    filtered = []
    removed = []

    i = 0
    while i < len(sections):
        # Check if this is a section header
        if re.match(r"^## ", sections[i]):
            header = sections[i]
            body = sections[i + 1] if i + 1 < len(sections) else ""

            # Skip title slides (first slide with <20 words, mostly images)
            if format_type == "pptx" and "Slide 1" in header:
                words = len(re.findall(r"\w+", re.sub(r"!\[image\]\(.+?\)", "", body)))
                if words < 20:
                    removed.append(header.strip())
                    i += 2
                    continue

            # Skip sections that are only images with no text
            text_only = re.sub(r"!\[image\]\(.+?\)", "", body).strip()
            if not text_only and "![image]" in body:
                removed.append(header.strip())
                i += 2
                continue

            filtered.append(header)
            filtered.append(body)
            i += 2
        else:
            filtered.append(sections[i])
            i += 1

    result = "".join(filtered)

    # Remove repeated header/footer lines (same line appearing 3+ times)
    lines = result.split("\n")
    line_counts = {}
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("!"):
            line_counts[stripped] = line_counts.get(stripped, 0) + 1
    repeated = {l for l, c in line_counts.items() if c >= 3 and len(l) < 100}
    if repeated:
        lines = [l for l in lines if l.strip() not in repeated]
        for r in repeated:
            removed.append(f"repeated: {r[:50]}")

    if removed:
        log.debug(f"Filter removed: {removed}")

    return "\n".join(lines)
