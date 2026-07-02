"""Markdown linting via pymarkdownlnt fix mode."""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from pymarkdown.api import PyMarkdownApi, PyMarkdownApiException

log = logging.getLogger("knowledge_extractor")

# Path to the project-level pymarkdown config file
_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / ".pymarkdown.json"


@dataclass
class LintResult:
    """Result of linting a single markdown file."""

    file_path: Path
    fixed_count: int = 0
    remaining_failures: list[str] = field(default_factory=list)


def lint_file(file_path: Path) -> LintResult:
    """Apply pymarkdownlnt fix mode to a markdown file.

    Scans the file for issues, applies auto-fixes, then re-scans to report
    remaining unfixable issues. Returns a LintResult with statistics.
    """
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


def _make_api() -> PyMarkdownApi:
    """Create a configured PyMarkdownApi instance."""
    api = PyMarkdownApi()
    api.log_error_and_above()

    if _CONFIG_PATH.exists():
        api.configuration_file_path(str(_CONFIG_PATH))

    return api
