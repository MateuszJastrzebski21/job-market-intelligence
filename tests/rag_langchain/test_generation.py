"""Tests for the LCEL generation chain.

Live API calls are skipped — the chain is replaced with a fake Runnable that
records its input. The real chain is exercised in the smoke check (T11), where
operator owns the local file output.
"""

from typing import Any

from langchain_core.runnables import Runnable

from jmi.rag_langchain import generation
from jmi.rag_langchain.generation import (
    DEFAULT_MODEL,
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    format_achievements,
    generate_bullets,
)
from jmi.rag_langchain.retrieval import ScoredChunk


def _make_chunk(text: str = "body", section: str = "impact", score: float = 0.8) -> ScoredChunk:
    return ScoredChunk(
        chunk_id="11111111-1111-1111-1111-111111111111",
        achievement_id="22222222-2222-2222-2222-222222222222",
        chunk_index=0,
        section=section,
        chunk_text=text,
        score=score,
    )


class _CapturingChain(Runnable[Any, str]):
    """Records its last input and returns a canned bullet block."""

    def __init__(self, response: str = "- bullet 1\n- bullet 2\n- bullet 3") -> None:
        self.response = response
        self.last_input: Any = None

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> str:
        self.last_input = input
        return self.response


def test_system_prompt_mentions_grounding_and_citation() -> None:
    assert "Do not invent" in SYSTEM_PROMPT
    assert "cite the source achievement" in SYSTEM_PROMPT


def test_user_template_carries_jd_and_achievements_slots() -> None:
    assert "{job_description}" in USER_PROMPT_TEMPLATE
    assert "{achievements}" in USER_PROMPT_TEMPLATE
    assert "{k}" in USER_PROMPT_TEMPLATE


def test_default_model_is_opus_4_7() -> None:
    # Dossier §6 + orchestrator default: claude-opus-4-7.
    assert DEFAULT_MODEL == "claude-opus-4-7"


def test_format_achievements_lists_each_chunk() -> None:
    chunks = [
        _make_chunk("impact body", section="impact", score=0.92),
        _make_chunk("lessons body", section="lessons", score=0.71),
    ]
    text = format_achievements(chunks)
    assert "Achievement 1" in text
    assert "Achievement 2" in text
    assert "impact body" in text
    assert "lessons body" in text
    assert "section=impact" in text
    assert "score=0.920" in text


def test_format_achievements_handles_empty_list() -> None:
    assert format_achievements([]) == ""


def test_generate_bullets_passes_inputs_to_chain() -> None:
    fake = _CapturingChain(response="- one\n- two")
    chunks = [_make_chunk("body A")]
    out = generate_bullets("the JD body", chunks, chain=fake)
    assert out == "- one\n- two"
    assert fake.last_input["job_description"] == "the JD body"
    assert "body A" in fake.last_input["achievements"]
    assert fake.last_input["k"] == 1


def test_generate_bullets_returns_string(monkeypatch: Any) -> None:
    fake = _CapturingChain(response="bullets")

    # Even if a caller forgets to pass chain=, generate_bullets must keep type str.
    def _fake_build_chain(model_name: str = DEFAULT_MODEL, max_tokens: int = 800) -> Runnable:
        return fake

    monkeypatch.setattr(generation, "build_chain", _fake_build_chain)
    out = generate_bullets("jd", [_make_chunk()])
    assert isinstance(out, str)
    assert out == "bullets"
