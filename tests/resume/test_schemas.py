"""Schema constraint tests for ``jmi.resume.schemas`` (PR-3.4c)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from jmi.resume.schemas import (
    BulletGenerationOutput,
    JobDescription,
    ResumeBullet,
)


def test_resume_bullet_caps_text_length() -> None:
    with pytest.raises(ValidationError):
        ResumeBullet(
            text="x" * 281,
            chunk_ids=["a"],
            mapped_jd_requirement="anything",
            contains_metric=False,
            confidence="high",
        )


def test_resume_bullet_requires_at_least_one_chunk_id() -> None:
    with pytest.raises(ValidationError):
        ResumeBullet(
            text="Built a thing.",
            chunk_ids=[],
            mapped_jd_requirement="x",
            contains_metric=False,
            confidence="high",
        )


def test_resume_bullet_caps_chunk_ids_at_three() -> None:
    with pytest.raises(ValidationError):
        ResumeBullet(
            text="Built a thing.",
            chunk_ids=["a", "b", "c", "d"],
            mapped_jd_requirement="x",
            contains_metric=False,
            confidence="high",
        )


def test_bullet_generation_output_requires_at_least_one_bullet() -> None:
    with pytest.raises(ValidationError):
        BulletGenerationOutput(bullets=[], uncovered_requirements=["x"])


def test_bullet_generation_output_caps_at_ten() -> None:
    bullet = ResumeBullet(
        text="x",
        chunk_ids=["a"],
        mapped_jd_requirement="r",
        contains_metric=False,
        confidence="high",
    )
    with pytest.raises(ValidationError):
        BulletGenerationOutput(bullets=[bullet] * 11)


def test_job_description_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        JobDescription(  # type: ignore[call-arg]
            raw_text="x",
            company_name="A",
            role_title="r",
            seniority="senior",
            language="en",
            bogus_field=1,
        )
