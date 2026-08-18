"""Globally unique public identities for quizzes."""

from uuid import UUID, uuid4

from sqlalchemy import select

from .models import QuizIdentity, db
from .quiz_types import QuizType, get_registry


def canonical_quiz_guid(value: object) -> str | None:
    """Return a canonical UUID v4 string, or ``None`` for invalid input."""
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError):
        return None

    if parsed.version != 4:
        return None
    return str(parsed)


def get_or_create_quiz_identity(quiz_type: str, source_id: int) -> QuizIdentity:
    """Return the stable identity for a source row in the current database."""
    identity = QuizIdentity.query.filter_by(
        quiz_type=quiz_type,
        source_id=source_id,
    ).first()
    if identity is not None:
        return identity

    identity = QuizIdentity(
        guid=str(uuid4()),
        quiz_type=quiz_type,
        source_id=source_id,
    )
    db.session.add(identity)
    return identity


def get_quiz_identity(quiz_type: str, source_id: int) -> QuizIdentity | None:
    """Return an existing source identity without creating one during reads."""
    return QuizIdentity.query.filter_by(
        quiz_type=quiz_type,
        source_id=source_id,
    ).first()


def resolve_quiz_guid(guid: object) -> QuizIdentity | None:
    """Resolve a canonical UUID v4 to its catalog entry."""
    canonical_guid = canonical_quiz_guid(guid)
    if canonical_guid is None:
        return None
    return db.session.get(QuizIdentity, canonical_guid)


def synchronize_quiz_identities(
    quiz_types: list[QuizType] | None = None,
) -> int:
    """Create missing identities for all rows in registered source tables."""
    added = 0
    for quiz_type in quiz_types if quiz_types is not None else get_registry():
        table = db.metadata.tables.get(quiz_type.source_table)
        if table is None or "id" not in table.c:
            raise RuntimeError(
                f"Quiz type '{quiz_type.identifier}' source table "
                f"'{quiz_type.source_table}' must expose an id column"
            )

        existing_source_ids = set(
            db.session.execute(
                select(QuizIdentity.source_id).where(
                    QuizIdentity.quiz_type == quiz_type.identifier
                )
            ).scalars()
        )
        source_ids = db.session.execute(select(table.c.id)).scalars()
        for source_id in source_ids:
            if source_id in existing_source_ids:
                continue
            get_or_create_quiz_identity(quiz_type.identifier, source_id)
            added += 1

    return added
