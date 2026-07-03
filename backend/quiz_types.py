"""Quiz type registry for the Quizzler application.

Defines available quiz types and provides startup validation. Adding a
new quiz type requires only appending to the QUIZ_TYPES list and placing
the corresponding rules markdown file in backend/assets/rules/.
"""

import re
from dataclasses import dataclass
from pathlib import Path

IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_RULES_DIR = Path(__file__).parent / "assets" / "rules"


@dataclass(frozen=True)
class QuizType:
    """A registered quiz type."""

    identifier: str
    display_name: str
    rules_file: str
    source_table: str


QUIZ_TYPES: list[QuizType] = [
    QuizType(
        identifier="countries",
        display_name="Countries",
        rules_file="countries.md",
        source_table="countries",
    ),
]


def get_registry() -> list[QuizType]:
    """Return the list of registered quiz types."""
    return QUIZ_TYPES


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

        rules_path = _RULES_DIR / qt.rules_file
        if not rules_path.is_file():
            errors.append(
                f"Rules file not found for '{qt.identifier}': {qt.rules_file}"
            )

    return errors
