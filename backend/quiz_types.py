"""Quiz type registry for the Quizzler application.

Defines available quiz types and provides startup validation. Conventional
hint-based types use ``StandardQuizAdapter``; see ``docs/quiz_types.md`` for
the source/result model and registration contract.
"""

import re
from dataclasses import dataclass
from pathlib import Path

IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
PUBLIC_CODE_PATTERN = re.compile(r"^[a-z]$")
_RULES_DIR = Path(__file__).parent / "assets" / "rules"


@dataclass(frozen=True)
class QuizType:
    """A registered quiz type."""

    identifier: str
    display_name: str
    rules_file: str
    source_table: str
    public_code: str = ""
    adapter: str | None = None


QUIZ_TYPES: list[QuizType] = [
    QuizType(
        identifier="countries",
        display_name="Countries",
        rules_file="countries.md",
        source_table="countries",
        public_code="c",
        adapter="countries",
    ),
]


def get_registry() -> list[QuizType]:
    """Return the list of registered quiz types."""
    return QUIZ_TYPES


def get_quiz_type(identifier: str) -> QuizType | None:
    """Return a registered quiz type by identifier."""
    return next(
        (quiz_type for quiz_type in QUIZ_TYPES if quiz_type.identifier == identifier),
        None,
    )


def validate_registry(quiz_types: list[QuizType]) -> list[str]:
    """Validate registry entries.

    Checks:
    - Each identifier matches ^[a-z0-9][a-z0-9_-]{0,63}$
    - Each display_name is 1-100 characters
    - No duplicate identifiers
    - Each rules_file exists in backend/assets/rules/

    Returns a list of error messages. An empty list means the registry is valid.
    """
    errors: list[str] = []
    seen_identifiers: set[str] = set()
    seen_public_codes: set[str] = set()

    from .quiz_adapters import get_quiz_adapter

    for qt in quiz_types:
        if not IDENTIFIER_PATTERN.match(qt.identifier):
            errors.append(
                f"Invalid identifier '{qt.identifier}': must match "
                f"^[a-z0-9][a-z0-9_-]{{0,63}}$"
            )

        if not (1 <= len(qt.display_name) <= 100):
            errors.append(
                f"Invalid display_name for '{qt.identifier}': "
                f"must be 1-100 characters, got {len(qt.display_name)}"
            )

        if qt.identifier in seen_identifiers:
            errors.append(f"Duplicate identifier: '{qt.identifier}'")
        seen_identifiers.add(qt.identifier)

        if qt.public_code:
            if not PUBLIC_CODE_PATTERN.fullmatch(qt.public_code):
                errors.append(
                    f"Invalid public_code for '{qt.identifier}': "
                    "must be one lowercase letter"
                )
            elif qt.public_code in seen_public_codes:
                errors.append(f"Duplicate public_code: '{qt.public_code}'")
            else:
                seen_public_codes.add(qt.public_code)

        rules_path = _RULES_DIR / qt.rules_file
        if not rules_path.is_file():
            errors.append(
                f"Rules file not found for '{qt.identifier}': {qt.rules_file}"
            )

        adapter_identifier = qt.adapter or qt.identifier
        adapter = get_quiz_adapter(adapter_identifier)
        if adapter is None:
            errors.append(
                f"Quiz adapter not found for '{qt.identifier}': "
                f"{adapter_identifier}"
            )
        elif adapter.identifier != qt.identifier:
            errors.append(
                f"Quiz adapter identifier mismatch for '{qt.identifier}': "
                f"{adapter.identifier}"
            )

    return errors
