"""Unit tests for pipeline translation step 5b (process_file)."""

import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import knowledge_extractor.pipeline as pipeline
from knowledge_extractor.discovery import DiscoveredFile
from knowledge_extractor.formulas import ExtractionResult


log = logging.getLogger("test")


@pytest.fixture(autouse=True)
def _reset_clients():
    """Ensure the module-level client cache is clean around each test."""
    pipeline._ai_clients.clear()
    yield
    pipeline._ai_clients.clear()


def _make_file(tmp_path: Path) -> DiscoveredFile:
    src = tmp_path / "doc.docx"
    src.write_text("dummy", encoding="utf-8")
    return DiscoveredFile(path=src, relative_path=Path("doc.docx"), format_type="docx")


def _make_args(tmp_path: Path, translate_from=None, translate_model=None):
    return SimpleNamespace(
        temp=tmp_path / "temp",
        output=tmp_path / "out",
        model="main/model",
        translate_from=translate_from,
        translate_model=translate_model,
    )


def _install_fake_extractor(monkeypatch, markdown: str):
    monkeypatch.setitem(
        pipeline.EXTRACTORS,
        "docx",
        lambda path, temp: ExtractionResult(markdown=markdown, formulas=[]),
    )


def _fake_ai(cleanup_return=None, translate_return=None):
    ai = MagicMock()
    ai.client = object()
    # cleanup_content returns the same content unchanged unless overridden
    ai.cleanup_content.side_effect = lambda md: cleanup_return if cleanup_return is not None else md
    ai.translate_content.return_value = translate_return
    return ai


def test_translation_invoked_and_replaces_output(tmp_path, monkeypatch):
    source_md = "# Titel\n\n" + ("Deutscher Text. " * 30)
    _install_fake_extractor(monkeypatch, source_md)

    ai = _fake_ai(translate_return="# Title\n\nTranslated English text.")
    monkeypatch.setattr(pipeline, "_get_ai", lambda model: ai)
    monkeypatch.setattr(pipeline, "lint_file", lambda p: SimpleNamespace(fixed_count=0, remaining_failures=[], fast_mode=False))

    args = _make_args(tmp_path, translate_from="German")
    file = _make_file(tmp_path)

    pipeline.process_file(file, args, log)

    ai.translate_content.assert_called_once()
    # First positional arg is the assembled markdown, second is the source language.
    call_args = ai.translate_content.call_args
    assert call_args.args[1] == "German"

    out_file = args.output / "doc.md"
    assert out_file.exists()
    assert out_file.read_text(encoding="utf-8") == "# Title\n\nTranslated English text."


def test_no_translation_when_flag_absent(tmp_path, monkeypatch):
    source_md = "# Titel\n\n" + ("Deutscher Text. " * 30)
    _install_fake_extractor(monkeypatch, source_md)

    ai = _fake_ai()
    monkeypatch.setattr(pipeline, "_get_ai", lambda model: ai)
    monkeypatch.setattr(pipeline, "lint_file", lambda p: SimpleNamespace(fixed_count=0, remaining_failures=[], fast_mode=False))

    args = _make_args(tmp_path, translate_from=None)
    file = _make_file(tmp_path)

    pipeline.process_file(file, args, log)

    ai.translate_content.assert_not_called()


def test_translation_none_keeps_cleanup_output(tmp_path, monkeypatch):
    """If translate_content returns None (unavailable), the cleanup output is kept."""
    source_md = "# Titel\n\n" + ("Deutscher Text. " * 30)
    _install_fake_extractor(monkeypatch, source_md)

    ai = _fake_ai(cleanup_return="CLEANED", translate_return=None)
    monkeypatch.setattr(pipeline, "_get_ai", lambda model: ai)
    monkeypatch.setattr(pipeline, "lint_file", lambda p: SimpleNamespace(fixed_count=0, remaining_failures=[], fast_mode=False))

    args = _make_args(tmp_path, translate_from="German")
    file = _make_file(tmp_path)

    pipeline.process_file(file, args, log)

    out_file = args.output / "doc.md"
    assert out_file.read_text(encoding="utf-8") == "CLEANED"
