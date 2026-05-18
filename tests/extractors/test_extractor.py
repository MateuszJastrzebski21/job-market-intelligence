from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import anthropic
from pydantic import ValidationError
from structlog.testing import capture_logs

from jmi.extractors import AnthropicExtractor
from jmi.extractors.schema import JobExtractSchema
from jmi.models.job import JobExtract, JobPosting


class _FakeMessages:
    def __init__(self, response_factory) -> None:
        self._response_factory = response_factory
        self.calls: list[dict] = []

    def parse(self, **kwargs) -> object:
        self.calls.append(kwargs)
        return self._response_factory(kwargs)


class _FakeClient:
    def __init__(self, response_factory) -> None:
        self.messages = _FakeMessages(response_factory)


def _make_posting(source_job_id: str = "w-1") -> JobPosting:
    return JobPosting(
        source="huggingface",
        source_job_id=source_job_id,
        url="https://apply.workable.com/j/ABC",
        title="Senior Cloud ML Engineer",
        company_name="Hugging Face",
        location_raw="Paris, France",
        description_html="<p>A job</p>",
        description_text="Senior ML Engineer role. 5+ years Python and PyTorch. Remote EMEA.",
        scraped_at=datetime.now(tz=UTC),
    )


def _make_response(
    schema_instance: JobExtractSchema,
    *,
    model: str = "claude-opus-4-7",
    input_tokens: int = 4500,
    output_tokens: int = 200,
    cache_read: int = 0,
    cache_creation: int = 0,
    stop_reason: str = "end_turn",
) -> SimpleNamespace:
    raw = {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": model,
        "stop_reason": stop_reason,
        "content": [{"type": "text", "text": schema_instance.model_dump_json()}],
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_input_tokens": cache_read,
            "cache_creation_input_tokens": cache_creation,
        },
    }
    response = SimpleNamespace(parsed_output=schema_instance, stop_reason=stop_reason)
    response.model_dump = lambda **_kwargs: raw
    return response


class _InMemoryPostingRepo:
    def __init__(self, postings: list[JobPosting]) -> None:
        self._postings = postings

    def list(self, limit: int = 100, offset: int = 0) -> list[JobPosting]:
        return list(self._postings[:limit])


class _InMemoryExtractRepo:
    def __init__(self, existing: dict[tuple[UUID, str], JobExtract] | None = None) -> None:
        self._existing = existing or {}
        self.added: list[JobExtract] = []

    def get_by_posting_and_model(self, posting_id: UUID, model_name: str) -> JobExtract | None:
        return self._existing.get((posting_id, model_name))

    def add(self, extract: JobExtract) -> JobExtract:
        self.added.append(extract)
        return extract


def test_extracts_one_posting_and_stamps_metadata() -> None:
    posting = _make_posting()
    parsed = JobExtractSchema(
        seniority="senior",
        tech_stack=["Python", "PyTorch"],
        remote_policy="remote",
        years_experience_min=5,
        employment_type="full_time",
    )
    client = _FakeClient(lambda _kwargs: _make_response(parsed))

    extractor = AnthropicExtractor(client=client, model="claude-opus-4-7")  # type: ignore[arg-type]
    extract = extractor.extract_one(posting)

    assert extract.job_posting_id == posting.id
    assert extract.model_name == "claude-opus-4-7"
    assert extract.seniority == "senior"
    assert extract.tech_stack == ["Python", "PyTorch"]
    assert extract.remote_policy == "remote"
    assert extract.raw_llm_response["model"] == "claude-opus-4-7"
    assert extract.raw_llm_response["usage"]["input_tokens"] == 4500


def test_skips_when_already_extracted_for_model() -> None:
    posting = _make_posting()
    existing = JobExtract(
        job_posting_id=posting.id,
        model_name="claude-opus-4-7",
        extracted_at=datetime.now(tz=UTC),
    )

    parsed = JobExtractSchema(seniority="senior")
    client = _FakeClient(lambda _kwargs: _make_response(parsed))
    extractor = AnthropicExtractor(client=client, model="claude-opus-4-7")  # type: ignore[arg-type]

    posting_repo = _InMemoryPostingRepo([posting])
    extract_repo = _InMemoryExtractRepo({(posting.id, "claude-opus-4-7"): existing})

    stats = extractor.run(posting_repo, extract_repo)  # type: ignore[arg-type]

    assert stats.skipped == 1
    assert stats.inserted == 0
    assert client.messages.calls == []  # no API call
    assert extract_repo.added == []


def test_inserts_when_existing_extract_is_for_different_model() -> None:
    posting = _make_posting()
    existing_for_haiku = JobExtract(
        job_posting_id=posting.id,
        model_name="claude-haiku-4-5",
        extracted_at=datetime.now(tz=UTC),
    )
    parsed = JobExtractSchema(seniority="senior")
    client = _FakeClient(lambda _kwargs: _make_response(parsed))
    extractor = AnthropicExtractor(client=client, model="claude-opus-4-7")  # type: ignore[arg-type]

    posting_repo = _InMemoryPostingRepo([posting])
    extract_repo = _InMemoryExtractRepo({(posting.id, "claude-haiku-4-5"): existing_for_haiku})

    stats = extractor.run(posting_repo, extract_repo)  # type: ignore[arg-type]

    assert stats.inserted == 1
    assert stats.skipped == 0
    assert len(client.messages.calls) == 1


def test_pydantic_validation_error_skips_job_not_fatal() -> None:
    p1, p2, p3 = (_make_posting(f"w-{i}") for i in range(3))
    good = JobExtractSchema(seniority="mid")

    call_counter = {"n": 0}

    def response_factory(_kwargs):
        call_counter["n"] += 1
        if call_counter["n"] == 2:
            raise ValidationError.from_exception_data("JobExtractSchema", [])
        return _make_response(good)

    client = _FakeClient(response_factory)
    extractor = AnthropicExtractor(client=client, model="claude-opus-4-7")  # type: ignore[arg-type]

    stats = extractor.run(_InMemoryPostingRepo([p1, p2, p3]), _InMemoryExtractRepo())  # type: ignore[arg-type]

    assert stats.inserted == 2
    assert stats.invalid == 1
    assert stats.failed_api_calls == 0


def test_anthropic_api_error_skips_job_not_fatal() -> None:
    p1, p2 = _make_posting("w-1"), _make_posting("w-2")
    good = JobExtractSchema(seniority="mid")

    call_counter = {"n": 0}

    def response_factory(_kwargs):
        call_counter["n"] += 1
        if call_counter["n"] == 1:
            raise anthropic.APIConnectionError(request=SimpleNamespace())  # type: ignore[arg-type]
        return _make_response(good)

    client = _FakeClient(response_factory)
    extractor = AnthropicExtractor(client=client, model="claude-opus-4-7")  # type: ignore[arg-type]

    stats = extractor.run(_InMemoryPostingRepo([p1, p2]), _InMemoryExtractRepo())  # type: ignore[arg-type]

    assert stats.inserted == 1
    assert stats.failed_api_calls == 1
    assert stats.invalid == 0


def test_model_override_flows_through_to_api_call() -> None:
    posting = _make_posting()
    parsed = JobExtractSchema(seniority="senior")
    client = _FakeClient(lambda _kwargs: _make_response(parsed, model="claude-haiku-4-5"))

    extractor = AnthropicExtractor(client=client, model="claude-haiku-4-5")  # type: ignore[arg-type]
    extract = extractor.extract_one(posting)

    assert extract.model_name == "claude-haiku-4-5"
    assert client.messages.calls[0]["model"] == "claude-haiku-4-5"


def test_system_prompt_includes_cache_control() -> None:
    posting = _make_posting()
    parsed = JobExtractSchema(seniority="mid")
    client = _FakeClient(lambda _kwargs: _make_response(parsed))

    extractor = AnthropicExtractor(client=client)  # type: ignore[arg-type]
    extractor.extract_one(posting)

    call = client.messages.calls[0]
    assert isinstance(call["system"], list)
    system_block = call["system"][0]
    assert system_block["type"] == "text"
    assert system_block["cache_control"] == {"type": "ephemeral"}
    assert len(system_block["text"]) > 10000  # system prompt is substantial


def test_run_skips_postings_with_empty_description() -> None:
    """Postings with description_text=None (typical for HITL-ingested rows
    awaiting detail fetch) are skipped before any Anthropic call."""
    p_empty = JobPosting(
        source="huggingface",
        source_job_id="empty-desc-001",
        url="https://example.test/jobs/001",
        title="Listing-only row",
        company_name="Acme",
        scraped_at=datetime.now(tz=UTC),
    )
    parsed = JobExtractSchema(seniority="senior")
    client = _FakeClient(lambda _k: _make_response(parsed))
    extractor = AnthropicExtractor(client=client, model="claude-opus-4-7")  # type: ignore[arg-type]

    stats = extractor.run(_InMemoryPostingRepo([p_empty]), _InMemoryExtractRepo())  # type: ignore[arg-type]

    assert stats.skipped == 1
    assert stats.inserted == 0
    assert client.messages.calls == []


def test_stats_accumulate_tokens_and_cache_hits() -> None:
    p1, p2 = _make_posting("w-1"), _make_posting("w-2")
    parsed = JobExtractSchema(seniority="mid")

    call_counter = {"n": 0}

    def response_factory(_kwargs):
        call_counter["n"] += 1
        if call_counter["n"] == 1:
            return _make_response(parsed, input_tokens=5000, cache_creation=4500, cache_read=0)
        return _make_response(parsed, input_tokens=500, cache_read=4500, cache_creation=0)

    client = _FakeClient(response_factory)
    extractor = AnthropicExtractor(client=client, model="claude-opus-4-7")  # type: ignore[arg-type]

    stats = extractor.run(_InMemoryPostingRepo([p1, p2]), _InMemoryExtractRepo())  # type: ignore[arg-type]

    assert stats.inserted == 2
    assert stats.cached_hits == 1
    assert stats.total_cache_creation_tokens == 4500
    assert stats.total_cache_read_tokens == 4500


def test_refusal_skipped() -> None:
    """A response whose stop_reason indicates a refusal is logged as
    'extract.refused', counted, and skipped — no JobExtract is persisted."""
    posting = _make_posting()
    parsed = JobExtractSchema(seniority="senior")
    client = _FakeClient(lambda _k: _make_response(parsed, stop_reason="refusal"))
    extractor = AnthropicExtractor(client=client, model="claude-opus-4-7")  # type: ignore[arg-type]

    extract_repo = _InMemoryExtractRepo()
    with capture_logs() as logs:
        stats = extractor.run(_InMemoryPostingRepo([posting]), extract_repo)  # type: ignore[arg-type]

    assert stats.refused == 1
    assert stats.inserted == 0
    assert extract_repo.added == []
    assert any(entry["event"] == "extract.refused" for entry in logs)
