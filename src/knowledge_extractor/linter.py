"""Markdown linting via pymarkdownlnt fix mode."""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from pymarkdown.api import PyMarkdownApi, PyMarkdownApiException

log = logging.getLogger("knowledge_extractor")

# Path to the project-level pymarkdown config file
_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / ".pymarkdown.json"

# Maximum file size (in bytes) for full pymarkdownlnt processing.
# Larger files use the fast regex-based fixer instead.
_MAX_LINT_SIZE = 512 * 1024  # 512 KB


@dataclass
class LintResult:
    """Result of linting a single markdown file."""

    file_path: Path
    fixed_count: int = 0
    remaining_failures: list[str] = field(default_factory=list)
    fast_mode: bool = False


def lint_file(file_path: Path) -> LintResult:
    """Apply markdown lint fixes to a file.

    Files within the size limit use pymarkdownlnt (scan -> fix -> rescan).
    Larger files use a fast regex-based fixer for common issues.
    """
    file_size = file_path.stat().st_size
    if file_size > _MAX_LINT_SIZE:
        return _fast_lint_file(file_path)

    return _full_lint_file(file_path)


def _full_lint_file(file_path: Path) -> LintResult:
    """Full pymarkdownlnt fix pass."""
    result = LintResult(file_path=file_path)

    try:
        # Initial scan to count issues before fixing
        api = _make_api()
        scan_result = api.scan_path(str(file_path))
        initial_count = len(scan_result.scan_failures)

        if initial_count == 0:
            return result

        # Apply fixes
        fix_api = _make_api()
        fix_api.fix_path(str(file_path))

        # Re-scan to count remaining issues
        rescan_api = _make_api()
        rescan_result = rescan_api.scan_path(str(file_path))
        remaining = rescan_result.scan_failures

        result.fixed_count = initial_count - len(remaining)
        result.remaining_failures = [
            f"{f.rule_id}:{f.line_number}:{f.column_number} {f.rule_description}"
            for f in remaining
        ]

    except PyMarkdownApiException as e:
        log.warning(f"Lint failed for {file_path.name}: {e}")
    except Exception as e:
        log.warning(f"Lint unexpected error for {file_path.name}: {e}")

    return result


def _fast_lint_file(file_path: Path) -> LintResult:
    """Fast regex-based fixer for large files.

    Handles the most common markdown issues without full AST parsing:
    - MD009: Trailing whitespace
    - MD010: Hard tabs -> spaces
    - MD012: Multiple consecutive blank lines -> single blank line
    - MD018: No space after heading hash
    - MD022: Blank lines around headings
    """
    result = LintResult(file_path=file_path, fast_mode=True)

    try:
        text = file_path.read_text(encoding="utf-8")
        original = text

        # MD009: Trailing whitespace
        text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)

        # MD010: Hard tabs -> 4 spaces
        text = text.replace("\t", "    ")

        # MD012: Collapse multiple blank lines into one
        text = re.sub(r"\n{3,}", "\n\n", text)

        # MD018: No space after heading hash (e.g., "#Heading" -> "# Heading")
        text = re.sub(r"^(#{1,6})([^ #\n])", r"\1 \2", text, flags=re.MULTILINE)

        # MD022: Ensure blank line before headings (but not at start of file)
        text = re.sub(r"([^\n])\n(#{1,6} )", r"\1\n\n\2", text)

        # MD022: Ensure blank line after headings
        text = re.sub(r"^(#{1,6} .+)\n([^\n#])", r"\1\n\n\2", text, flags=re.MULTILINE)

        # Ensure file ends with single newline
        text = text.rstrip("\n") + "\n"

        if text != original:
            # Count approximate fixes (number of changed lines)
            orig_lines = original.splitlines()
            new_lines = text.splitlines()
            changed = sum(1 for a, b in zip(orig_lines, new_lines) if a != b)
            changed += abs(len(orig_lines) - len(new_lines))
            result.fixed_count = changed

            file_path.write_text(text, encoding="utf-8")

    except Exception as e:
        log.warning(f"Fast lint failed for {file_path.name}: {e}")

    return result


def _make_api() -> PyMarkdownApi:
    """Create a configured PyMarkdownApi instance."""
    api = PyMarkdownApi()
    api.log_error_and_above()

    if _CONFIG_PATH.exists():
        api.configuration_file_path(str(_CONFIG_PATH))

    return api
