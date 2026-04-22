from __future__ import annotations

import pytest
from pydantic import ValidationError

from jmi.extractors.schema import JobExtractSchema


def test_all_fields_populated() -> None:
    schema = JobExtractSchema(
        seniority="senior",
        tech_stack=["Python", "PyTorch"],
        salary_min=120000,
        salary_max=150000,
        salary_currency="USD",
        remote_policy="remote",
        years_experience_min=5,
        employment_type="full_time",
    )
    assert schema.seniority == "senior"
    assert schema.tech_stack == ["Python", "PyTorch"]
    assert schema.salary_currency == "USD"


def test_all_optional_fields_default_to_none_or_empty() -> None:
    schema = JobExtractSchema()
    assert schema.seniority is None
    assert schema.tech_stack == []
    assert schema.salary_min is None
    assert schema.salary_max is None
    assert schema.salary_currency is None
    assert schema.remote_policy is None
    assert schema.years_experience_min is None
    assert schema.employment_type is None


def test_invalid_seniority_rejected() -> None:
    with pytest.raises(ValidationError):
        JobExtractSchema(seniority="ninja")  # type: ignore[arg-type]


def test_invalid_remote_policy_rejected() -> None:
    with pytest.raises(ValidationError):
        JobExtractSchema(remote_policy="mostly")  # type: ignore[arg-type]


def test_invalid_employment_type_rejected() -> None:
    with pytest.raises(ValidationError):
        JobExtractSchema(employment_type="gig")  # type: ignore[arg-type]


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        JobExtractSchema(seniority="mid", unknown_field="foo")  # type: ignore[call-arg]


def test_json_schema_generation_works() -> None:
    """Smoke test that the schema can be serialized (needed for messages.parse)."""
    schema_dict = JobExtractSchema.model_json_schema()
    assert "properties" in schema_dict
    assert "seniority" in schema_dict["properties"]
    assert "tech_stack" in schema_dict["properties"]
