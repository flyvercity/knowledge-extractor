import logging
from pathlib import Path

log = logging.getLogger("knowledge_extractor")


def generate_index(output_dir: Path, input_dir: Path, logger: logging.Logger):
    md_files = sorted(output_dir.rglob("*.md"))
    md_files = [f for f in md_files if f.name != "index.md"]

    if not md_files:
        logger.warning("No output files to index")
        return

    # Group by top-level folder
    groups: dict[str, list[tuple[Path, str]]] = {}
    for f in md_files:
        rel = f.relative_to(output_dir)
        group = rel.parts[0] if len(rel.parts) > 1 else "Root"
        title = _extract_title(f)
        groups.setdefault(group, []).append((rel, title))

    lines = [f"# Knowledge Index\n", f"**{len(md_files)} documents extracted**\n"]

    for group, entries in sorted(groups.items()):
        lines.append(f"\n## {group}\n")
        for rel_path, title in entries:
            lines.append(f"- [{title}]({rel_path.as_posix()})")

    index_path = output_dir / "index.md"
    index_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Index generated: {index_path} ({len(md_files)} entries)")


def _extract_title(md_file: Path) -> str:
    try:
        for line in md_file.read_text(encoding="utf-8").splitlines()[:20]:
            if line.startswith("# "):
                return line[2:].strip()
    except Exception:
        pass
    return md_file.stem
