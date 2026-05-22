"""End-to-end tests for the ``jmi generate-resume`` CLI command (PR-3.4d).

Mocks every Anthropic-touching component (JD parser, research agent, bullet
generator, cover letter generator) and the retrieval pipeline. Uses the real
testcontainers Postgres so persistence is exercised.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from jmi.cli import app
from jmi.cover_letter.generator import CoverLetterGenerationResult
from jmi.rag.retrieval import ScoredChunk
from jmi.research.company_agent import ResearchResult
from jmi.research.schemas import CompanyFact, CompanyResearch
from jmi.resume.bullet_generator import BulletGenerationResult
from jmi.resume.jd_parser import ParsedJDResult
from jmi.resume.schemas import (
    BulletGenerationOutput,
    CoverLetterDraft,
    CoverLetterParagraph,
    JobDescription,
    ResumeBullet,
    Tone,
)

runner = CliRunner()


def _jd(*, language: str = "en", company: str = "Acme") -> JobDescription:
    return JobDescription(
        raw_text="Senior AI Engineer at " + company + " — Python, RAG, pgvector. " * 4,
        company_name=company,
        company_domain="acme.com",
        role_title="Senior AI Engineer",
        seniority="senior",
        must_have_skills=["Python", "RAG"],
        nice_to_have_skills=["pgvector"],
        location="Warsaw, Poland",
        language=cast(Any, language),
        raw_url=None,
    )


def _chunk(cid: UUID, text: str) -> ScoredChunk:
    return ScoredChunk(
        chunk_id=cid,
        achievement_id=uuid4(),
        chunk_index=0,
        chunk_text=text,
        score=0.85,
    )


def _bullet(text: str, chunk_id: str) -> ResumeBullet:
    return ResumeBullet(
        text=text,
        chunk_ids=[chunk_id],
        mapped_jd_requirement="r",
        contains_metric=False,
        confidence=cast(Any, "high"),
    )


def _research() -> CompanyResearch:
    return CompanyResearch(
        company_name="Acme",
        one_line_summary="Acme builds RAG agents.",
        recent_news=[
            CompanyFact(
                fact="Launched Vertex AI agents.",
                source_url="https://acme.com/news",
                recency_estimate="last_30d",
            )
        ],
        confidence=cast(Any, "high"),
        specific_opener_candidates=["I noticed your Vertex launch..."],
    )


def _cover_letter() -> CoverLetterDraft:
    return CoverLetterDraft(
        paragraphs=[
            CoverLetterParagraph(
                text="I noticed your Vertex launch.",
                role="opener",
                specific_company_fact_referenced="Vertex launch",
            ),
            CoverLetterParagraph(
                text="My RAG pipeline maps to your stack.",
                role="body",
                chunk_ids=[str(uuid4())],
            ),
            CoverLetterParagraph(text="Happy to walk through it.", role="closer"),
        ],
        word_count=270,
        company_specific_opener=True,
        research_confidence=cast(Any, "high"),
        tone=cast(Any, "conversational"),
    )


class _FakePipeline:
    """Drop-in for jmi.rag.pipeline.RagPipeline with configurable chunks."""

    def __init__(self, chunks: list[ScoredChunk]) -> None:
        self._chunks = chunks

    @property
    def has_reranker(self) -> bool:
        return True

    def retrieve_top_k(
        self, session: object, query: str, k: int = 5, **_: object
    ) -> list[ScoredChunk]:
        return list(self._chunks[:k])


class _FakeBulletGenerator:
    def __init__(self, *_: object, **__: object) -> None:
        pass

    def generate(
        self, jd: JobDescription, chunks: list[ScoredChunk], *, bullet_count: int = 6
    ) -> BulletGenerationResult:
        cid = str(chunks[0].chunk_id)
        return BulletGenerationResult(
            output=BulletGenerationOutput(
                bullets=[
                    _bullet("Built a RAG pipeline.", cid),
                    _bullet("Implemented a benchmark harness.", cid),
                ],
                uncovered_requirements=[],
            ),
            input_tokens=3000,
            output_tokens=1200,
            cost_usd=0.045,
            model="claude-opus-4-7",
            refused_bullet_count=0,
            retried=False,
        )


class _FakeCoverLetterGenerator:
    def __init__(self, *_: object, **__: object) -> None:
        pass

    def generate(
        self,
        jd: JobDescription,
        research: CompanyResearch | None,
        chunks: list[ScoredChunk],
        *,
        tone: Tone = "conversational",
    ) -> CoverLetterGenerationResult:
        return CoverLetterGenerationResult(
            draft=_cover_letter(),
            input_tokens=3000,
            output_tokens=700,
            cost_usd=0.033,
            model="claude-opus-4-7",
        )


class _FakeResearchAgent:
    def __init__(self, *, cache_repo: object, **__: object) -> None:
        self._cache_repo = cache_repo

    def research_company(
        self,
        company_name: str,
        company_domain: str | None,
        *,
        depth: int = 3,
        use_cache: bool = True,
        ttl_days: int = 7,
    ) -> ResearchResult:
        return ResearchResult(
            research=_research(),
            cache_hit=False,
            web_search_calls=1,
            input_tokens=5000,
            output_tokens=1500,
            cost_usd=0.078,
            duration_ms=12000,
        )


@pytest.fixture
def patched_pipeline(monkeypatch: pytest.MonkeyPatch, db_session: Session) -> list[ScoredChunk]:
    """Patch the CLI's lazy-imported retrieval + generation + db session deps."""
    chunks = [
        _chunk(uuid4(), "Built a RAG pipeline with pgvector and BGE embeddings."),
        _chunk(uuid4(), "Implemented a benchmark harness with MRR and recall@k."),
    ]

    # Patch the heavy retrieval components so they don't actually load models.
    monkeypatch.setattr("jmi.rag.embedding.CustomEmbedder", lambda *a, **kw: object())
    monkeypatch.setattr("jmi.rag.reranking.CustomReranker", lambda *a, **kw: object())
    monkeypatch.setattr("jmi.rag.retrieval.CustomRetriever", lambda *a, **kw: object())
    monkeypatch.setattr("jmi.rag.pipeline.RagPipeline", lambda *a, **kw: _FakePipeline(chunks))

    # Patch the generators / agent.
    monkeypatch.setattr(
        "jmi.resume.bullet_generator.StructuredBulletGenerator", _FakeBulletGenerator
    )
    monkeypatch.setattr(
        "jmi.cover_letter.generator.CoverLetterGenerator", _FakeCoverLetterGenerator
    )
    monkeypatch.setattr("jmi.research.company_agent.CompanyResearchAgent", _FakeResearchAgent)

    # Patch parse_jd to return canned without API call.
    def _fake_parse_jd(
        raw_text: str,
        *,
        override_company: str | None = None,
        override_url: str | None = None,
        client: object | None = None,
    ) -> ParsedJDResult:
        jd = _jd(company=override_company or "Acme")
        return ParsedJDResult(
            jd=jd,
            input_tokens=1500,
            output_tokens=400,
            cost_usd=0.011,
            model="claude-sonnet-4-6",
        )

    monkeypatch.setattr("jmi.resume.jd_parser.parse_jd", _fake_parse_jd)

    # Patch get_session to yield the test transaction-rollback session.
    @contextmanager
    def _yield_db_session() -> Any:
        yield db_session

    monkeypatch.setattr("jmi.db.base.get_session", _yield_db_session)
    return chunks


# ── Dry-run + budget gates ──────────────────────────────────────────────────


def test_dry_run_emits_plan_and_no_api_calls(patched_pipeline: list[ScoredChunk]) -> None:
    result = runner.invoke(
        app,
        ["generate-resume", "--jd-text", "x" * 500, "--dry-run"],
    )
    assert result.exit_code == 0, result.output
    assert "--dry-run" in result.stdout
    assert "Estimated cost" in result.stdout


def test_budget_exceeded_aborts_before_api(patched_pipeline: list[ScoredChunk]) -> None:
    result = runner.invoke(
        app,
        ["generate-resume", "--jd-text", "x" * 500, "--budget-usd", "0.001"],
    )
    assert result.exit_code == 2
    assert "exceeds --budget-usd" in result.output


def test_mutex_jd_file_xor_jd_text(patched_pipeline: list[ScoredChunk]) -> None:
    result = runner.invoke(app, ["generate-resume"])
    assert result.exit_code == 2
    assert "Exactly one of --jd-file or --jd-text" in result.output


def test_both_jd_file_and_jd_text_rejected(
    patched_pipeline: list[ScoredChunk], tmp_path: Path
) -> None:
    jd_file = tmp_path / "jd.txt"
    jd_file.write_text("x" * 500)
    result = runner.invoke(
        app, ["generate-resume", "--jd-file", str(jd_file), "--jd-text", "x" * 500]
    )
    assert result.exit_code == 2


def test_unknown_tone_rejected(patched_pipeline: list[ScoredChunk]) -> None:
    result = runner.invoke(
        app,
        ["generate-resume", "--jd-text", "x" * 500, "--tone", "robotic"],
    )
    assert result.exit_code == 2
    assert "Unknown --tone" in result.output


# ── Happy paths ─────────────────────────────────────────────────────────────


def test_full_generation_persists_row_and_writes_markdown(
    patched_pipeline: list[ScoredChunk], db_session: Session
) -> None:
    result = runner.invoke(app, ["generate-resume", "--jd-text", "x" * 500])
    assert result.exit_code == 0, result.output
    assert "# Senior AI Engineer — Acme" in result.stdout
    assert "## Selected Achievements" in result.stdout
    assert "## Cover Letter" in result.stdout

    # cost block to stderr
    assert "Cost:" in result.output
    assert "Saved row:" in result.output

    # row persisted
    from jmi.storage.tailored_resumes import TailoredResumeRepository

    repo = TailoredResumeRepository(db_session)
    assert repo.count() == 1


def test_bullets_only_skips_cover_letter(
    patched_pipeline: list[ScoredChunk], db_session: Session
) -> None:
    result = runner.invoke(app, ["generate-resume", "--jd-text", "x" * 500, "--bullets-only"])
    assert result.exit_code == 0, result.output
    assert "## Cover Letter" not in result.stdout

    from jmi.storage.tailored_resumes import TailoredResumeRepository

    repo = TailoredResumeRepository(db_session)
    rows = repo.find_by_jd_hash(_jd_hash_for("x" * 500))
    assert len(rows) == 1
    assert rows[0].cover_letter == ""  # empty when --bullets-only


def test_no_research_skips_research_agent(
    patched_pipeline: list[ScoredChunk], db_session: Session
) -> None:
    result = runner.invoke(app, ["generate-resume", "--jd-text", "x" * 500, "--no-research"])
    assert result.exit_code == 0, result.output
    assert "no research" in result.output

    from jmi.storage.tailored_resumes import TailoredResumeRepository

    repo = TailoredResumeRepository(db_session)
    rows = repo.find_by_jd_hash(_jd_hash_for("x" * 500))
    assert len(rows) == 1
    assert rows[0].research_blob is None
    assert rows[0].web_search_calls == 0


def test_output_flag_writes_markdown_to_file(
    patched_pipeline: list[ScoredChunk], tmp_path: Path
) -> None:
    out_md = tmp_path / "resume.md"
    result = runner.invoke(
        app, ["generate-resume", "--jd-text", "x" * 500, "--output", str(out_md)]
    )
    assert result.exit_code == 0, result.output
    assert out_md.read_text().startswith("# Senior AI Engineer")


def test_json_flag_writes_full_tailored_resume(
    patched_pipeline: list[ScoredChunk], tmp_path: Path
) -> None:
    out_json = tmp_path / "resume.json"
    result = runner.invoke(
        app, ["generate-resume", "--jd-text", "x" * 500, "--json", str(out_json)]
    )
    assert result.exit_code == 0, result.output

    import json

    data = json.loads(out_json.read_text())
    assert data["job_description"]["company_name"] == "Acme"
    assert len(data["bullets"]) == 2
    assert data["jd_hash"] == _jd_hash_for("x" * 500)


def test_polish_language_emits_warning_but_proceeds(
    patched_pipeline: list[ScoredChunk], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Override the JD parser stub to report language=pl
    def _pl_parser(
        raw_text: str,
        *,
        override_company: str | None = None,
        override_url: str | None = None,
        client: object | None = None,
    ) -> ParsedJDResult:
        jd = _jd(language="pl")
        return ParsedJDResult(
            jd=jd, input_tokens=100, output_tokens=50, cost_usd=0.01, model="claude-sonnet-4-6"
        )

    monkeypatch.setattr("jmi.resume.jd_parser.parse_jd", _pl_parser)
    result = runner.invoke(app, ["generate-resume", "--jd-text", "x" * 500])
    assert result.exit_code == 0, result.output
    assert "Polish JD detected" in result.output


def test_company_override_passed_through(
    patched_pipeline: list[ScoredChunk], db_session: Session
) -> None:
    result = runner.invoke(
        app,
        ["generate-resume", "--jd-text", "x" * 500, "--company", "Real Company"],
    )
    assert result.exit_code == 0, result.output

    from jmi.storage.tailored_resumes import TailoredResumeRepository

    repo = TailoredResumeRepository(db_session)
    rows = repo.find_by_jd_hash(_jd_hash_for("x" * 500))
    assert rows[0].company_name == "Real Company"


def test_include_meta_appends_metadata_section(
    patched_pipeline: list[ScoredChunk],
) -> None:
    result = runner.invoke(app, ["generate-resume", "--jd-text", "x" * 500, "--include-meta"])
    assert result.exit_code == 0, result.output
    assert "## Generation Metadata" in result.stdout


# ── Helpers ─────────────────────────────────────────────────────────────────


def _jd_hash_for(raw_jd: str) -> str:
    import hashlib

    return hashlib.sha256(raw_jd.strip().encode("utf-8")).hexdigest()
