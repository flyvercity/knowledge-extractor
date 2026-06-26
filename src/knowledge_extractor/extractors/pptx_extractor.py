from pathlib import Path
from pptx import Presentation
from pptx.shapes.picture import Picture
from pptx.shapes.group import GroupShape
from .utils import get_img_dir


def extract_pptx(file_path: Path, temp_dir: Path) -> str:
    prs = Presentation(str(file_path))
    img_dir = get_img_dir(temp_dir, file_path)

    lines = []
    img_count = 0

    for slide_num, slide in enumerate(prs.slides, 1):
        lines.append(f"\n## Slide {slide_num}\n")
        for shape in _iter_shapes(slide.shapes):
            if isinstance(shape, Picture):
                try:
                    ext = _img_ext(shape.image.content_type)
                    img_path = img_dir / f"slide{slide_num}_img{img_count}{ext}"
                    img_path.write_bytes(shape.image.blob)
                    lines.append(f"\n![image]({img_path.resolve()})\n")
                    img_count += 1
                except (ValueError, AttributeError):
                    pass
            elif shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    text = para.text.strip()
                    if text:
                        lines.append(text)
            elif shape.has_table:
                lines.append(_table_to_md(shape.table))

        # Speaker notes
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                lines.append(f"\n> **Notes:** {notes}\n")

    return "\n".join(lines)


def _iter_shapes(shapes):
    for shape in shapes:
        if isinstance(shape, GroupShape):
            yield from _iter_shapes(shape.shapes)
        else:
            yield shape


def _table_to_md(table) -> str:
    rows = []
    for row in table.rows:
        cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
        rows.append(cells)
    if not rows:
        return ""
    header = "| " + " | ".join(rows[0]) + " |"
    sep = "| " + " | ".join("---" for _ in rows[0]) + " |"
    body = "\n".join("| " + " | ".join(r) + " |" for r in rows[1:])
    return f"\n{header}\n{sep}\n{body}\n"


def _img_ext(content_type: str) -> str:
    return {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif",
            "image/bmp": ".bmp", "image/tiff": ".tiff"}.get(content_type, ".png")
