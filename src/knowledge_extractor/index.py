import json
import logging
import re
from pathlib import Path

log = logging.getLogger("knowledge_extractor")


def _is_hidden(path: Path, output_dir: Path) -> bool:
    """True if any parent component of path (relative to output_dir) starts with '.'.

    Only parent components are considered (``rel.parts[:-1]``) so that the file's own
    name is not treated as a hidden component.
    """
    rel = path.relative_to(output_dir)
    return any(part.startswith(".") for part in rel.parts[:-1])


def generate_index(output_dir: Path, input_dir: Path | None = None, logger: logging.Logger | None = None) -> tuple[int, int]:
    """Regenerate the root ``index.md`` and ``manifest.json`` for ``output_dir``.

    ``input_dir`` is **deprecated and ignored** — it is retained only for positional
    compatibility with the historical ``convert`` call site
    (``generate_index(args.output, args.input, log)``). New callers should omit it.

    Each Markdown file is read exactly once and reused for title, headings, and word
    count. Documents are grouped by their full relative parent path (POSIX-style, joined
    with ``/``); files directly in the output root are grouped under ``"Root"``. Files
    inside hidden directories (any path component starting with ``.``) are excluded.

    Returns ``(doc_count, group_count)``; returns ``(0, 0)`` and logs a warning when
    there is nothing to index.
    """
    logger = logger or log

    md_files = [
        f
        for f in sorted(output_dir.rglob("*.md"))
        if f.name != "index.md" and f.is_file() and not _is_hidden(f, output_dir)
    ]

    if not md_files:
        logger.warning("No output files to index")
        return (0, 0)

    # Group by full relative parent path
    groups: dict[str, list[tuple[Path, str]]] = {}
    manifest_entries = []

    for f in md_files:
        rel = f.relative_to(output_dir)
        group = "/".join(rel.parts[:-1]) if len(rel.parts) > 1 else "Root"

        content = f.read_text(encoding="utf-8", errors="ignore")
        title = _extract_title(content, f.stem)
        headings = re.findall(r"^#{1,3}\s+(.+)$", content, re.MULTILINE)

        groups.setdefault(group, []).append((rel, title))
        manifest_entries.append({
            "path": rel.as_posix(),
            "title": title,
            "group": group,
            "headings": headings[:20],
            "word_count": len(content.split()),
        })

    # Markdown index
    lines = ["# Knowledge Index\n", f"**{len(md_files)} documents extracted**\n"]
    for group, entries in sorted(groups.items()):
        lines.append(f"\n## {group}\n")
        for rel_path, title in entries:
            lines.append(f"- [{title}]({rel_path.as_posix()})")

    index_path = output_dir / "index.md"
    index_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Index generated: {index_path} ({len(md_files)} entries)")

    # JSON manifest
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_entries, indent=2), encoding="utf-8")
    logger.info(f"Manifest generated: {manifest_path}")

    return (len(md_files), len(groups))


def _extract_title(content: str, stem: str) -> str:
    """Return the first ``# `` heading in ``content`` (first 20 lines), else ``stem``."""
    for line in content.splitlines()[:20]:
        if line.startswith("# "):
            return line[2:].strip()
    return stem


def _is_generated_index(path: Path) -> bool:
    """True if ``path`` looks like an extractor-generated ``index.md``.

    Verified by the leading ``# Knowledge Index`` signature.
    """
    try:
        with path.open(encoding="utf-8", errors="ignore") as fh:
            head = fh.read(256)
    except OSError:
        return False
    return head.lstrip().startswith("# Knowledge Index")


def _is_generated_manifest(path: Path) -> bool:
    """True if ``path`` looks like an extractor-generated ``manifest.json``.

    It must parse as a JSON array whose entries are dicts carrying at least the
    ``path``/``title``/``group`` keys. An empty array is a valid generated artifact.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, ValueError):
        return False
    if not isinstance(data, list):
        return False
    return all(
        isinstance(e, dict) and {"path", "title", "group"} <= set(e)
        for e in data
    )


def cleanup_nested_artifacts(output_dir: Path, logger: logging.Logger | None = None) -> int:
    """Delete VERIFIED generated ``index.md`` / ``manifest.json`` in SUBDIRECTORIES.

    The root-level pair is left untouched (it is regenerated afterward). A nested file is
    deleted only if it passes :func:`_is_generated_index` / :func:`_is_generated_manifest`;
    otherwise it is treated as user content, preserved, and logged at warning level.
    Hidden directories are skipped entirely. Individual unlink failures (locked/read-only
    files) are logged and skipped. Returns the number of files removed.
    """
    logger = logger or log
    root = output_dir.resolve()
    removed = 0
    checks = {"index.md": _is_generated_index, "manifest.json": _is_generated_manifest}
    for name, is_generated in checks.items():
        for path in output_dir.rglob(name):
            if path.resolve().parent == root:
                continue  # keep the root pair
            if _is_hidden(path, output_dir):
                continue  # never touch files inside hidden dirs
            if not is_generated(path):
                logger.warning(f"Preserving user content (not a generated artifact): {path}")
                continue
            try:
                path.unlink()
                removed += 1
                logger.info(f"Removed nested artifact: {path}")
            except OSError as e:
                logger.warning(f"Could not remove {path}: {e}")
    return removed
