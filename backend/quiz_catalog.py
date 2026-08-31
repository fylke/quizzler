"""Stable internal and compact public identities for quizzes."""

import re
from uuid import uuid4

from sqlalchemy import select

from .models import QuizIdentity, db
from .quiz_types import QuizType, get_quiz_type, get_registry

PUBLIC_ID_PATTERN = r"^[a-z][0-9]+$"


def public_quiz_id(quiz_type: str, source_id: int) -> str:
    """Build the compact public ID for a quiz source row."""
    quiz_type_entry = get_quiz_type(quiz_type)
    if quiz_type_entry is None:
        raise ValueError(f"Unknown quiz type: {quiz_type}")
    public_code = quiz_type_entry.public_code or quiz_type_entry.identifier[:1]
    return f"{public_code}{int(source_id)}"


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


def resolve_quiz_id(quiz_id: object) -> QuizIdentity | None:
    """Resolve a compact public ID to its catalog entry."""
    value = str(quiz_id).strip().lower()
    if re.fullmatch(PUBLIC_ID_PATTERN, value):
        quiz_type_entry = next(
            (
                entry
                for entry in get_registry()
                if (entry.public_code or entry.identifier[:1]) == value[0]
            ),
            None,
        )
        if quiz_type_entry is not None:
            return QuizIdentity.query.filter_by(
                quiz_type=quiz_type_entry.identifier,
                source_id=int(value[1:]),
            ).first()

    return None


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
