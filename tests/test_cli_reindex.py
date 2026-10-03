"""Unit tests for the `reindex` CLI command."""

import json
from pathlib import Path

from click.testing import CliRunner

import knowledge_extractor.cli as cli

GENERATED_INDEX = "# Knowledge Index\n\n**1 documents extracted**\n\n## Root\n- [x](x.md)"
GENERATED_MANIFEST = json.dumps(
    [{"path": "x.md", "title": "X", "group": "Root", "headings": [], "word_count": 1}]
)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_reindex_happy_path(tmp_path):
    _write(tmp_path / "root.md", "# Root Doc\nhello")
    _write(tmp_path / "VaultA" / "a.md", "# A Doc\nalpha")
    _write(tmp_path / "VaultA" / "sub" / "b.md", "# B Doc\nbeta")
    # Generated nested artifacts — should be removed by default.
    _write(tmp_path / "VaultA" / "index.md", GENERATED_INDEX)
    _write(tmp_path / "VaultA" / "manifest.json", GENERATED_MANIFEST)

    result = CliRunner().invoke(cli.cli, ["reindex", str(tmp_path)], catch_exceptions=False)
    assert result.exit_code == 0

    assert (tmp_path / "index.md").exists()
    assert (tmp_path / "manifest.json").exists()
    assert not (tmp_path / "VaultA" / "index.md").exists()
    assert not (tmp_path / "VaultA" / "manifest.json").exists()

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    groups = {e["group"] for e in manifest}
    assert groups == {"Root", "VaultA", "VaultA/sub"}

    assert "3 document(s) across 3 group(s)" in result.output


def test_reindex_preserves_user_content(tmp_path):
    _write(tmp_path / "root.md", "# Root Doc\nhello")
    user_index = _write(tmp_path / "VaultA" / "index.md", "# My Project Notes\n\ncontent")

    result = CliRunner().invoke(cli.cli, ["reindex", str(tmp_path)], catch_exceptions=False)
    assert result.exit_code == 0
    assert user_index.exists()


def test_reindex_keep_nested_preserves_artifacts(tmp_path):
    _write(tmp_path / "root.md", "# Root Doc\nhello")
    nested_index = _write(tmp_path / "VaultA" / "index.md", GENERATED_INDEX)
    nested_manifest = _write(tmp_path / "VaultA" / "manifest.json", GENERATED_MANIFEST)

    result = CliRunner().invoke(
        cli.cli, ["reindex", str(tmp_path), "--keep-nested"], catch_exceptions=False
    )
    assert result.exit_code == 0
    assert nested_index.exists()
    assert nested_manifest.exists()


def test_reindex_missing_dir_nonzero_exit(tmp_path):
    missing = tmp_path / "does_not_exist"
    result = CliRunner().invoke(cli.cli, ["reindex", str(missing)])
    assert result.exit_code != 0
    assert "Directory not found" in result.output


def test_reindex_empty_dir(tmp_path):
    result = CliRunner().invoke(cli.cli, ["reindex", str(tmp_path)], catch_exceptions=False)
    assert result.exit_code == 0
    assert not (tmp_path / "manifest.json").exists()
    assert "Nothing to index" in result.output
