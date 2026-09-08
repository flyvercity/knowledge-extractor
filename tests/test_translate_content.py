"""Unit tests for AIClient.translate_content and _split_into_chunks hardening."""

from unittest.mock import patch

import pytest

from knowledge_extractor.ai import (
    AIClient,
    AIProviderError,
    AIBadRequestError,
    TRANSLATE_PROMPT,
)


def _client_with_fake_backend():
    """Build an AIClient without an API key, then give it a truthy fake client."""
    c = AIClient("test/model")
    c.client = object()  # truthy so translate_content proceeds past the None guard
    return c


def test_translate_returns_none_without_client():
    c = AIClient("test/model")
    c.client = None
    assert c.translate_content("some German text " * 20, "German") is None


def test_translate_returns_input_when_trivially_short():
    c = _client_with_fake_backend()
    short = "kurz"
    assert c.translate_content(short, "German") == short


def test_translate_single_pass_calls_once_with_language():
    c = _client_with_fake_backend()
    markdown = "# Titel\n\n" + ("Dies ist ein deutscher Absatz. " * 20)
    with patch.object(c, "_call", return_value="TRANSLATED") as mock_call:
        result = c.translate_content(markdown, "German", chunk_size=50000)

    assert result == "TRANSLATED"
    mock_call.assert_called_once()
    # The prompt sent to _call must include the source language and content.
    sent_messages = mock_call.call_args.args[0]
    sent_prompt = sent_messages[0]["content"]
    assert "German" in sent_prompt
    assert "Titel" in sent_prompt


def test_translate_chunked_translates_and_rejoins():
    c = _client_with_fake_backend()
    # Two ## sections, each big enough that a small chunk_size forces chunking.
    section_a = "## Abschnitt A\n\n" + ("Text A. " * 50)
    section_b = "## Abschnitt B\n\n" + ("Text B. " * 50)
    markdown = section_a + "\n" + section_b

    with patch.object(c, "_call", side_effect=["OUT_A", "OUT_B"]) as mock_call:
        result = c.translate_content(markdown, "German", chunk_size=500)

    assert mock_call.call_count == 2
    assert result == "OUT_A\n\nOUT_B"


def test_translate_chunk_provider_error_keeps_original():
    """A transient AIProviderError on a chunk must not crash; original text is kept."""
    c = _client_with_fake_backend()
    section_a = "## Abschnitt A\n\n" + ("Text A. " * 50)
    section_b = "## Abschnitt B\n\n" + ("Text B. " * 50)
    markdown = section_a + "\n" + section_b

    with patch.object(
        c, "_call", side_effect=["OUT_A", AIProviderError("500 boom")]
    ):
        result = c.translate_content(markdown, "German", chunk_size=500)

    # First chunk translated; second chunk failed -> original chunk retained.
    assert "OUT_A" in result
    assert "Text B." in result


def test_translate_chunk_bad_request_keeps_original():
    c = _client_with_fake_backend()
    section_a = "## Abschnitt A\n\n" + ("Text A. " * 50)
    section_b = "## Abschnitt B\n\n" + ("Text B. " * 50)
    markdown = section_a + "\n" + section_b

    with patch.object(
        c, "_call", side_effect=[AIBadRequestError("400"), "OUT_B"]
    ):
        result = c.translate_content(markdown, "German", chunk_size=500)

    assert "Text A." in result
    assert "OUT_B" in result


def test_split_does_not_break_inside_code_fence():
    """The oversized-section fallback must not split inside a ``` fence."""
    fence = "```mermaid\n" + "graph LR\nA[Node] --> B[Other]\n" * 20 + "```"
    # One big section (no ## boundaries) larger than max_size to force line fallback.
    oversized = "Intro paragraph.\n\n" + fence + "\n\nOutro paragraph."
    max_size = 100

    chunks = AIClient._split_into_chunks(oversized, max_size)

    # No chunk may contain an unbalanced number of ``` fences (which would mean a
    # fenced block was split across a boundary).
    for chunk in chunks:
        assert chunk.count("```") % 2 == 0, f"Fence split across chunk: {chunk!r}"


def test_translate_prompt_has_mermaid_rules():
    """The prompt template documents Mermaid label-only translation (finding P2)."""
    assert "Mermaid" in TRANSLATE_PROMPT
    assert "A[Angemeldet]" in TRANSLATE_PROMPT
    assert "A[Logged in]" in TRANSLATE_PROMPT
