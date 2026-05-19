from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from jmi.db.models import AchievementORM
from jmi.models.achievement import Achievement


class AchievementRepository:
    """Domain ↔ persistence boundary for Achievement. Callers see Pydantic,
    SQLAlchemy stays behind the session — mirrors JobPostingRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, item: Achievement) -> Achievement:
        orm = _achievement_to_orm(item)
        self._session.add(orm)
        self._session.flush()
        return _achievement_to_domain(orm)

    def get(self, id: UUID) -> Achievement | None:
        orm = self._session.get(AchievementORM, id)
        return _achievement_to_domain(orm) if orm else None

    def get_by_slug(self, slug: str) -> Achievement | None:
        stmt = select(AchievementORM).where(AchievementORM.slug == slug)
        orm = self._session.execute(stmt).scalar_one_or_none()
        return _achievement_to_domain(orm) if orm else None

    def get_by_source_path(self, source_path: str) -> Achievement | None:
        """Look an achievement up by its vault-relative path — the ingestion upsert key."""
        stmt = select(AchievementORM).where(AchievementORM.source_path == source_path)
        orm = self._session.execute(stmt).scalar_one_or_none()
        return _achievement_to_domain(orm) if orm else None

    def list_all(self, limit: int = 100, offset: int = 0) -> list[Achievement]:
        stmt = (
            select(AchievementORM)
            .order_by(AchievementORM.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [_achievement_to_domain(o) for o in self._session.execute(stmt).scalars()]

    def update(self, item: Achievement) -> Achievement:
        """In-place UPDATE of an existing achievement, matched by `item.id`.

        Preserves the UUID so any FK references in `achievement_embeddings` stay
        valid. The caller owns upsert semantics (id / created_at preservation,
        updated_at bump). Raises KeyError if no row matches `item.id`.
        """
        orm = self._session.get(AchievementORM, item.id)
        if orm is None:
            raise KeyError(item.id)
        orm.title = item.title
        orm.slug = item.slug
        orm.source_path = str(item.source_path)
        orm.skills = list(item.skills)
        orm.tech_stack = list(item.tech_stack)
        orm.seniority_relevance = list(item.seniority_relevance)
        orm.impact_metrics = list(item.impact_metrics)
        orm.keywords = list(item.keywords)
        orm.context = item.context
        orm.approach = item.approach
        orm.impact = item.impact
        orm.lessons = item.lessons
        orm.created_at = item.created_at
        orm.updated_at = item.updated_at
        self._session.flush()
        return _achievement_to_domain(orm)


def _achievement_to_orm(a: Achievement) -> AchievementORM:
    return AchievementORM(
        id=a.id,
        title=a.title,
        slug=a.slug,
        source_path=str(a.source_path),
        skills=list(a.skills),
        tech_stack=list(a.tech_stack),
        seniority_relevance=list(a.seniority_relevance),
        impact_metrics=list(a.impact_metrics),
        keywords=list(a.keywords),
        context=a.context,
        approach=a.approach,
        impact=a.impact,
        lessons=a.lessons,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


def _achievement_to_domain(o: AchievementORM) -> Achievement:
    # `slug` is a computed field — not an init arg — so it is not passed here;
    # it re-derives from `title` (and equals the stored value by construction).
    return Achievement(
        id=o.id,
        title=o.title,
        source_path=Path(o.source_path),
        skills=list(o.skills),
        tech_stack=list(o.tech_stack),
        seniority_relevance=list(o.seniority_relevance),
        impact_metrics=list(o.impact_metrics),
        keywords=list(o.keywords),
        context=o.context,
        approach=o.approach,
        impact=o.impact,
        lessons=o.lessons,
        created_at=o.created_at,
        updated_at=o.updated_at,
    )
