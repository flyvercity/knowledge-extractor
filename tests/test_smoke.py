"""Smoke test: confirm the package imports and the test harness runs."""


def test_ai_client_importable():
    from knowledge_extractor.ai import AIClient

    assert AIClient is not None
