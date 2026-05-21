"""``FakeAnthropic`` client + canned response builders for testing.

The Anthropic SDK is mocked at the class level (constructor injection into
generators/agents) rather than via HTTP-layer interception (``respx``). This
matches the existing test idiom in ``tests/cli/test_rag_query.py`` and gives
us assertion access to the actual call kwargs (``tools=``, ``cache_control``,
``output_format``, ``max_uses``).

Two queues: one for ``messages.create`` calls (Call 1 of research, returning
multi-block ``Message`` objects with tool_use payloads), one for
``messages.parse`` calls (returning ``Message``-like objects with
``parsed_output``). Each tool call pops from its queue in FIFO order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    # When the server invoked web_search, populate ``server_tool_use``:
    # {"web_search_requests": int}. Otherwise leave None to mimic non-tool calls.
    server_tool_use: dict[str, int] | None = None


@dataclass
class FakeTextBlock:
    text: str = ""
    type: str = "text"


@dataclass
class FakeServerToolUseBlock:
    name: str = "web_search"
    input: dict[str, Any] = field(default_factory=dict)
    id: str = "toolu_fake"
    type: str = "server_tool_use"


@dataclass
class FakeWebSearchResultItem:
    title: str = ""
    url: str = ""
    encrypted_content: str = ""
    page_age: str | None = None
    type: str = "web_search_result"


@dataclass
class FakeWebSearchToolResultBlock:
    # ``content`` is EITHER a list of FakeWebSearchResultItem (success)
    # OR a dict like {"type": "web_search_tool_result_error", "error_code": "..."}.
    content: list[FakeWebSearchResultItem] | dict[str, str] = field(default_factory=list)
    tool_use_id: str = "toolu_fake"
    type: str = "web_search_tool_result"


@dataclass
class FakeMessage:
    """Mimics ``anthropic.types.Message`` for ``messages.create()`` returns."""

    content: list[Any] = field(default_factory=list)
    usage: FakeUsage = field(default_factory=FakeUsage)
    stop_reason: str = "end_turn"
    model: str = "claude-opus-4-7"
    id: str = "msg_fake"
    role: str = "assistant"
    type: str = "message"


@dataclass
class FakeParsedMessage:
    """Mimics ``messages.parse()`` returns: a Message with ``parsed_output``."""

    parsed_output: Any = None
    usage: FakeUsage = field(default_factory=FakeUsage)
    stop_reason: str = "end_turn"
    model: str = "claude-sonnet-4-6"
    id: str = "msg_fake_parse"
    role: str = "assistant"
    type: str = "message"
    content: list[Any] = field(default_factory=list)


class _FakeMessagesEndpoint:
    def __init__(
        self,
        create_responses: list[FakeMessage],
        parse_responses: list[FakeParsedMessage],
    ) -> None:
        self._create_queue: list[FakeMessage] = list(create_responses)
        self._parse_queue: list[FakeParsedMessage] = list(parse_responses)
        self.recorded_create_calls: list[dict[str, Any]] = []
        self.recorded_parse_calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> FakeMessage:
        self.recorded_create_calls.append(kwargs)
        if not self._create_queue:
            raise RuntimeError(
                "FakeAnthropic.messages.create called more times than queued; "
                "add more responses via FakeAnthropic(create_responses=[...])."
            )
        return self._create_queue.pop(0)

    def parse(self, **kwargs: Any) -> FakeParsedMessage:
        self.recorded_parse_calls.append(kwargs)
        if not self._parse_queue:
            raise RuntimeError(
                "FakeAnthropic.messages.parse called more times than queued; "
                "add more responses via FakeAnthropic(parse_responses=[...])."
            )
        return self._parse_queue.pop(0)


class FakeAnthropic:
    """Drop-in replacement for ``anthropic.Anthropic`` in tests."""

    def __init__(
        self,
        *,
        create_responses: list[FakeMessage] | None = None,
        parse_responses: list[FakeParsedMessage] | None = None,
    ) -> None:
        self.messages = _FakeMessagesEndpoint(
            create_responses or [],
            parse_responses or [],
        )


def build_web_search_message(
    *,
    queries: list[str],
    results: list[FakeWebSearchResultItem],
    final_text: str,
    input_tokens: int = 5000,
    output_tokens: int = 1000,
    web_search_requests: int = 1,
    model: str = "claude-opus-4-7",
) -> FakeMessage:
    """Construct a ``FakeMessage`` with interleaved tool_use + tool_result + text.

    One ``server_tool_use`` + one ``web_search_tool_result`` per query, then a
    single final ``text`` block. Mirrors the real Anthropic response shape
    when ``web_search`` is invoked.
    """
    content: list[Any] = []
    for i, q in enumerate(queries):
        content.append(FakeTextBlock(text=f"Searching for: {q}"))
        content.append(FakeServerToolUseBlock(input={"query": q}, id=f"toolu_{i}"))
        content.append(
            FakeWebSearchToolResultBlock(tool_use_id=f"toolu_{i}", content=list(results))
        )
    content.append(FakeTextBlock(text=final_text))
    return FakeMessage(
        content=content,
        usage=FakeUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            server_tool_use={"web_search_requests": web_search_requests},
        ),
        model=model,
    )


def build_max_uses_exceeded_message(
    *,
    input_tokens: int = 800,
    output_tokens: int = 80,
    model: str = "claude-opus-4-7",
) -> FakeMessage:
    """Construct a response whose tool_result block signals ``max_uses_exceeded``."""
    return FakeMessage(
        content=[
            FakeTextBlock(text="Starting search."),
            FakeServerToolUseBlock(input={"query": "test"}),
            FakeWebSearchToolResultBlock(
                content={
                    "type": "web_search_tool_result_error",
                    "error_code": "max_uses_exceeded",
                },
            ),
        ],
        usage=FakeUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            server_tool_use={"web_search_requests": 1},
        ),
        model=model,
    )


def build_parsed_message(
    output: Any,
    *,
    input_tokens: int = 1500,
    output_tokens: int = 500,
    cache_read_input_tokens: int = 0,
    cache_creation_input_tokens: int = 0,
    model: str = "claude-sonnet-4-6",
) -> FakeParsedMessage:
    """Construct a ``messages.parse()`` return with the supplied ``parsed_output``."""
    return FakeParsedMessage(
        parsed_output=output,
        usage=FakeUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_input_tokens=cache_read_input_tokens,
            cache_creation_input_tokens=cache_creation_input_tokens,
        ),
        model=model,
    )
