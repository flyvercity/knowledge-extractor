"""Unit tests for index generation and nested-artifact cleanup."""

import json
from pathlib import Path

import pytest

from knowledge_extractor.index import (
    generate_index,
    cleanup_nested_artifacts,
    _extract_title,
    _is_hidden,
    _is_generated_index,
    _is_generated_manifest,
)

GENERATED_INDEX = "# Knowledge Index\n\n**1 documents extracted**\n\n## Root\n- [x](x.md)"
GENERATED_MANIFEST = json.dumps(
    [{"path": "x.md", "title": "X", "group": "Root", "headings": [], "word_count": 1}]
)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# --- _extract_title ---------------------------------------------------------


def test_extract_title_from_heading():
    assert _extract_title("# My Title\n\nbody", "stem") == "My Title"


def test_extract_title_falls_back_to_stem():
    assert _extract_title("no heading here", "stem") == "stem"


# --- generate_index: grouping + summary -------------------------------------


def test_generate_index_grouping_and_summary(tmp_path):
    _write(tmp_path / "root.md", "# Root Doc\nhello world")
    _write(tmp_path / "VaultA" / "a.md", "# A Doc\nalpha")
    _write(tmp_path / "VaultA" / "sub" / "b.md", "# B Doc\nbeta")
    _write(tmp_path / ".obsidian" / "note.md", "# Hidden\nshould be ignored")

    result = generate_index(tmp_path)
    assert result == (3, 3)

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    groups = {e["group"] for e in manifest}
    assert groups == {"Root", "VaultA", "VaultA/sub"}

    paths = {e["path"] for e in manifest}
    assert not any(".obsidian" in p for p in paths)
    assert "VaultA/sub/b.md" in paths  # POSIX separators

    index_text = (tmp_path / "index.md").read_text(encoding="utf-8")
    assert "## Root" in index_text
    assert "## VaultA" in index_text
    assert "## VaultA/sub" in index_text
    assert "(VaultA/sub/b.md)" in index_text  # POSIX link separators


def test_generate_index_empty_returns_zero_and_no_manifest(tmp_path):
    result = generate_index(tmp_path)
    assert result == (0, 0)
    assert not (tmp_path / "manifest.json").exists()


# --- _is_hidden -------------------------------------------------------------


def test_is_hidden_true_for_dotdir(tmp_path):
    p = tmp_path / ".obsidian" / "note.md"
    assert _is_hidden(p, tmp_path) is True


def test_is_hidden_false_for_normal(tmp_path):
    p = tmp_path / "VaultA" / "a.md"
    assert _is_hidden(p, tmp_path) is False


# --- cleanup_nested_artifacts -----------------------------------------------


def test_cleanup_removes_generated_nested_preserves_root(tmp_path):
    # Root pair (generated) — must be preserved by cleanup.
    _write(tmp_path / "index.md", GENERATED_INDEX)
    _write(tmp_path / "manifest.json", GENERATED_MANIFEST)
    # Nested generated artifacts — must be removed.
    _write(tmp_path / "VaultA" / "index.md", GENERATED_INDEX)
    _write(tmp_path / "VaultA" / "manifest.json", GENERATED_MANIFEST)
    _write(tmp_path / "VaultA" / "sub" / "index.md", GENERATED_INDEX)
    _write(tmp_path / "VaultA" / "sub" / "manifest.json", GENERATED_MANIFEST)

    removed = cleanup_nested_artifacts(tmp_path)
    assert removed == 4

    assert (tmp_path / "index.md").exists()
    assert (tmp_path / "manifest.json").exists()
    assert not (tmp_path / "VaultA" / "index.md").exists()
    assert not (tmp_path / "VaultA" / "manifest.json").exists()
    assert not (tmp_path / "VaultA" / "sub" / "index.md").exists()
    assert not (tmp_path / "VaultA" / "sub" / "manifest.json").exists()


def test_cleanup_preserves_user_content(tmp_path):
    user_index = _write(tmp_path / "VaultA" / "index.md", "# My Project Notes\n\ncontent")
    user_manifest = _write(tmp_path / "VaultA" / "manifest.json", json.dumps({"custom": True}))

    removed = cleanup_nested_artifacts(tmp_path)
    assert removed == 0
    assert user_index.exists()
    assert user_manifest.exists()


def test_cleanup_preserves_hidden_dir_artifacts(tmp_path):
    hidden = _write(tmp_path / ".obsidian" / "index.md", GENERATED_INDEX)

    removed = cleanup_nested_artifacts(tmp_path)
    assert removed == 0
    assert hidden.exists()


def test_cleanup_no_nested_returns_zero(tmp_path):
    _write(tmp_path / "index.md", GENERATED_INDEX)
    _write(tmp_path / "manifest.json", GENERATED_MANIFEST)
    assert cleanup_nested_artifacts(tmp_path) == 0


def test_cleanup_empty_manifest_is_generated(tmp_path):
    _write(tmp_path / "VaultA" / "manifest.json", "[]")
    assert _is_generated_manifest(tmp_path / "VaultA" / "manifest.json") is True
    removed = cleanup_nested_artifacts(tmp_path)
    assert removed == 1


def test_cleanup_resilient_to_oserror(tmp_path, monkeypatch):
    _write(tmp_path / "VaultA" / "index.md", GENERATED_INDEX)
    _write(tmp_path / "VaultB" / "index.md", GENERATED_INDEX)

    import pathlib

    original_unlink = pathlib.Path.unlink

    def flaky_unlink(self, *args, **kwargs):
        if self.parent.name == "VaultA":
            raise OSError("locked")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "unlink", flaky_unlink)

    removed = cleanup_nested_artifacts(tmp_path)
    # Only VaultB/index.md successfully removed; VaultA failure logged, not raised.
    assert removed == 1
    assert (tmp_path / "VaultA" / "index.md").exists()
    assert not (tmp_path / "VaultB" / "index.md").exists()
