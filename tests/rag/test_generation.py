"""Tests for the Claude bullet generator (T7).

No live API: the Anthropic client is replaced with a fake whose ``messages.create``
returns a canned ``Message``. The tests pin the prompt structure, the
hallucination-guard wording, and the response parsing.
"""

from typing import Any
from uuid import uuid4

import pytest

from jmi.rag.generation import (
    SYSTEM_PROMPT,
    Generator,
    _prompt_hash,
    format_user_message,
)
from jmi.rag.retrieval import ScoredChunk


def _scored(text: str = "[Title — Context]\nbody", score: float = 0.9) -> ScoredChunk:
    return ScoredChunk(
        chunk_id=uuid4(),
        achievement_id=uuid4(),
        chunk_index=0,
        chunk_text=text,
        score=score,
    )


class _FakeUsage:
    def __init__(self, inp: int = 100, out: int = 50) -> None:
        self.input_tokens = inp
        self.output_tokens = out


class _FakeTextBlock:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _FakeMessage:
    def __init__(self, text: str) -> None:
        self.content = [_FakeTextBlock(text)]
        self.usage = _FakeUsage()


class _FakeMessages:
    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _FakeMessage:
        self.calls.append(kwargs)
        return _FakeMessage(self.response_text)


class _FakeClient:
    def __init__(self, response_text: str = "- Bullet one. (chunks: 1)") -> None:
        self.messages = _FakeMessages(response_text)


def test_format_user_message_numbers_chunks_from_one() -> None:
    chunks = [_scored("first"), _scored("second")]
    msg = format_user_message("JD text", chunks)
    assert "JOB_DESCRIPTION:" in msg
    assert "ACHIEVEMENT_CHUNKS:" in msg
    assert "[CHUNK 1]" in msg
    assert "[CHUNK 2]" in msg
    assert "first" in msg
    assert "second" in msg


def test_format_user_message_includes_score_and_aid() -> None:
    c = _scored("body")
    msg = format_user_message("JD", [c])
    assert "score=0.900" in msg
    assert str(c.achievement_id) in msg


def test_format_user_message_with_no_chunks_says_so() -> None:
    msg = format_user_message("JD", [])
    assert "(no chunks retrieved)" in msg


def test_system_prompt_forbids_invention() -> None:
    # Pin the hallucination-guard wording — a future edit must be intentional.
    assert "Do not\n   invent metrics, employers, dates, technologies, or outcomes" in SYSTEM_PROMPT
    assert "OMIT it" in SYSTEM_PROMPT
    assert "trace to one or more chunks" in SYSTEM_PROMPT
    assert "citation" in SYSTEM_PROMPT.lower()


def test_system_prompt_format_constraints() -> None:
    assert "3 to 5 bullets" in SYSTEM_PROMPT
    assert 'starting with "- "' in SYSTEM_PROMPT
    assert "No preamble" in SYSTEM_PROMPT


def test_prompt_hash_stable_for_same_inputs() -> None:
    c = _scored()
    a = _prompt_hash("JD", [c])
    b = _prompt_hash("JD", [c])
    assert a == b


def test_prompt_hash_changes_with_jd() -> None:
    c = _scored()
    a = _prompt_hash("JD one", [c])
    b = _prompt_hash("JD two", [c])
    assert a != b


def test_prompt_hash_changes_with_chunk_set() -> None:
    a = _prompt_hash("JD", [_scored()])
    b = _prompt_hash("JD", [_scored(), _scored()])
    assert a != b


def test_generate_bullets_returns_parsed_text() -> None:
    client: Any = _FakeClient("- Did X (chunks: 1)\n- Did Y (chunks: 2)")
    gen = Generator(client=client, model="claude-test-model")
    result = gen.generate_bullets("JD", [_scored("a"), _scored("b")])
    assert result.bullets_markdown == "- Did X (chunks: 1)\n- Did Y (chunks: 2)"
    assert result.model == "claude-test-model"
    assert result.input_tokens == 100
    assert result.output_tokens == 50


def test_generate_bullets_passes_system_prompt_and_user_message() -> None:
    client: Any = _FakeClient()
    gen = Generator(client=client)
    chunks = [_scored("a"), _scored("b")]
    gen.generate_bullets("JD", chunks)
    call = client.messages.calls[0]
    assert call["system"] == SYSTEM_PROMPT
    user = call["messages"][0]["content"]
    assert "JOB_DESCRIPTION:" in user
    assert "[CHUNK 1]" in user
    assert "[CHUNK 2]" in user


def test_generate_bullets_carries_chunk_ids_for_audit() -> None:
    client: Any = _FakeClient()
    gen = Generator(client=client)
    chunks = [_scored(), _scored()]
    result = gen.generate_bullets("JD", chunks)
    assert result.chunk_ids_in_prompt == [str(c.chunk_id) for c in chunks]


def test_empty_jd_raises() -> None:
    client: Any = _FakeClient()
    gen = Generator(client=client)
    with pytest.raises(ValueError, match="jd is empty"):
        gen.generate_bullets("   ", [_scored()])


def test_empty_chunks_raises() -> None:
    client: Any = _FakeClient()
    gen = Generator(client=client)
    with pytest.raises(ValueError, match="chunks is empty"):
        gen.generate_bullets("JD", [])


def test_missing_api_key_raises_construction_error(monkeypatch: pytest.MonkeyPatch) -> None:
    # The Generator wants an explicit client OR a real api_key — emulate the
    # CI case where the key is unset.
    from jmi.config import Settings

    def _no_key() -> Settings:
        return Settings(database_url="postgresql+psycopg://t:t@h:5432/t")

    monkeypatch.setattr("jmi.rag.generation.get_settings", _no_key)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        Generator(client=None)
