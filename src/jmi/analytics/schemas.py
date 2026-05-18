from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class JobView(BaseModel):
    """Analytics-facing projection of one job posting — the fields the market
    report renders. Built by `analytics.runner` from a posting joined with its
    most recent extract; `tech_stack` is empty when the posting has no extract.
    """

    model_config = ConfigDict(extra="forbid")

    posting_id: UUID
    title: str
    source: str
    tech_stack: list[str] = Field(default_factory=list)
