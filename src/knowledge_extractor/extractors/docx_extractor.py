from pathlib import Path
from docx import Document
from docx.table import Table


def extract_docx(file_path: Path, temp_dir: Path) -> str:
    doc = Document(str(file_path))
    stem = file_path.stem
    img_dir = temp_dir / stem
    img_dir.mkdir(parents=True, exist_ok=True)

    # Extract images
    img_paths = []
    for i, rel in enumerate(doc.part.rels.values()):
        if "image" in rel.reltype and not rel.is_external:
            ext = Path(rel.target_ref).suffix
            img_path = img_dir / f"img_{i}{ext}"
            img_path.write_bytes(rel.target_part.blob)
            img_paths.append(img_path)

    lines = []
    img_idx = 0

    for element in doc.element.body:
        tag = element.tag.split("}")[-1]
        if tag == "p":
            para = None
            for p in doc.paragraphs:
                if p._element is element:
                    para = p
                    break
            if para is None:
                continue

            # Check for inline images
            if para._element.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing") or \
               para._element.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pict"):
                if img_idx < len(img_paths):
                    lines.append(f"\n![image]({img_paths[img_idx]})\n")
                    img_idx += 1

            text = para.text.strip()
            if not text:
                continue

            style = para.style.name if para.style else ""
            if "Heading 1" in style:
                lines.append(f"\n# {text}\n")
            elif "Heading 2" in style:
                lines.append(f"\n## {text}\n")
            elif "Heading 3" in style:
                lines.append(f"\n### {text}\n")
            else:
                lines.append(text)

        elif tag == "tbl":
            for table in doc.tables:
                if table._tbl is element:
                    lines.append(_table_to_md(table))
                    break

    # Append any remaining images not matched inline
    while img_idx < len(img_paths):
        lines.append(f"\n![image]({img_paths[img_idx]})\n")
        img_idx += 1

    return "\n".join(lines)


def _table_to_md(table: Table) -> str:
    rows = []
    for row in table.rows:
        cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
        rows.append(cells)
    if not rows:
        return ""
    # Deduplicate merged cells (python-docx repeats them)
    clean_rows = []
    for row in rows:
        seen = []
        prev = None
        for c in row:
            if c == prev:
                seen.append("")
            else:
                seen.append(c)
            prev = c
        clean_rows.append(seen)
    header = "| " + " | ".join(clean_rows[0]) + " |"
    sep = "| " + " | ".join("---" for _ in clean_rows[0]) + " |"
    body = "\n".join("| " + " | ".join(r) + " |" for r in clean_rows[1:])
    return f"\n{header}\n{sep}\n{body}\n"
