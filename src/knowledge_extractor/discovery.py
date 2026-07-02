from dataclasses import dataclass
from pathlib import Path

SUPPORTED = {
    ".docx": "docx",
    ".pptx": "pptx",
    ".xlsx": "xlsx",
    ".pdf": "pdf",
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
}


SKIP_DIRS = {".git"}


@dataclass
class DiscoveredFile:
    path: Path
    relative_path: Path
    format_type: str


def discover_files(input_dir: Path) -> list[DiscoveredFile]:
    files = []
    for p in sorted(input_dir.rglob("*")):
        if any(part in SKIP_DIRS for part in p.relative_to(input_dir).parts):
            continue
        if p.is_file() and p.suffix.lower() in SUPPORTED:
            files.append(DiscoveredFile(
                path=p,
                relative_path=p.relative_to(input_dir),
                format_type=SUPPORTED[p.suffix.lower()],
            ))
    return files
