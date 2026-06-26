from pathlib import Path
import pymupdf


def extract_pdf(file_path: Path, temp_dir: Path) -> str:
    doc = pymupdf.open(str(file_path))
    stem = file_path.stem
    img_dir = temp_dir / stem
    img_dir.mkdir(parents=True, exist_ok=True)

    lines = []
    img_count = 0

    for page_num, page in enumerate(doc, 1):
        lines.append(f"\n## Page {page_num}\n")
        text = page.get_text("text").strip()
        if text:
            lines.append(text)
        else:
            # Scanned page — render as image for AI OCR
            pix = page.get_pixmap(dpi=150)
            img_path = img_dir / f"page{page_num}.png"
            pix.save(str(img_path))
            lines.append(f"\n![image]({img_path})\n")
            img_count += 1
            continue

        # Extract embedded images
        for img_info in page.get_images(full=True):
            xref = img_info[0]
            base_image = doc.extract_image(xref)
            ext = base_image["ext"]
            img_path = img_dir / f"page{page_num}_img{img_count}.{ext}"
            img_path.write_bytes(base_image["image"])
            lines.append(f"\n![image]({img_path})\n")
            img_count += 1

    doc.close()
    return "\n".join(lines)
