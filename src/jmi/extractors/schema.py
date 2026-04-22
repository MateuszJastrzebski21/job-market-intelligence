from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from jmi.models.job import EmploymentType, RemotePolicy, Seniority


class JobExtractSchema(BaseModel):
    """Pydantic schema that the LLM populates. Distinct from `JobExtract`
    (DB row): no id, no FK, no metadata — just the fields Claude reasons
    about. See ADR-0005 for why this is split from the persistence model."""

    model_config = ConfigDict(extra="forbid")

    seniority: Seniority | None = Field(
        default=None,
        description=(
            "Seniority level inferred from title, required years, and "
            "scope of responsibility. Return null when the posting gives "
            "no clear signal."
        ),
    )
    tech_stack: list[str] = Field(
        default_factory=list,
        description=(
            "Canonical technology names the role uses day-to-day. "
            "Deduplicated, max 20 entries."
        ),
    )
    salary_min: int | None = Field(
        default=None,
        description=(
            "Annual salary lower bound, in whole units of salary_currency. "
            "Null if not stated or not annual."
        ),
    )
    salary_max: int | None = Field(
        default=None,
        description=(
            "Annual salary upper bound, in whole units of salary_currency. "
            "Null if not stated or not annual."
        ),
    )
    salary_currency: str | None = Field(
        default=None,
        description=(
            "ISO 4217 currency code, uppercase (e.g. USD, EUR, PLN, GBP). "
            "Null if currency not determinable."
        ),
    )
    remote_policy: RemotePolicy | None = Field(
        default=None,
        description="Work location policy: remote, hybrid, or onsite. Null if not stated.",
    )
    years_experience_min: int | None = Field(
        default=None,
        description="Minimum years of experience required, as a whole number. Null if not stated.",
    )
    employment_type: EmploymentType | None = Field(
        default=None,
        description="Employment contract type. Null if not stated.",
    )
