"""Validation rules and game constants shared across the application.

This module is the single source of truth for all input validation
constraints and gameplay parameters. The frontend fetches the validation
values via /api/validation-rules so they never drift out of sync.
"""

# --- Password ---
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128

# --- Destination name ---
DESTINATION_NAME_MAX_LENGTH = 128

# --- Hints ---
HINT_COUNT = 5
HINT_MAX_LENGTH = 256

# --- Images ---
IMAGES_MIN_COUNT = 2
IMAGES_MAX_COUNT = 10
UPLOAD_MAX_BYTES = 25 * 1024 * 1024

# --- Correct answers ---
ANSWERS_MIN_COUNT = 1
ANSWERS_MAX_COUNT = 20
ANSWER_MAX_LENGTH = 128

# --- Gameplay ---
STARTING_HINT_DIFFICULTY = 5
MAX_GUESSES = 3


def as_dict() -> dict:
    """Return all validation rules as a JSON-serializable dict."""
    return {
        "password": {
            "minLength": PASSWORD_MIN_LENGTH,
            "maxLength": PASSWORD_MAX_LENGTH,
        },
        "destination": {
            "nameMaxLength": DESTINATION_NAME_MAX_LENGTH,
            "hintCount": HINT_COUNT,
            "hintMaxLength": HINT_MAX_LENGTH,
            "imagesMinCount": IMAGES_MIN_COUNT,
            "imagesMaxCount": IMAGES_MAX_COUNT,
            "answersMinCount": ANSWERS_MIN_COUNT,
            "answersMaxCount": ANSWERS_MAX_COUNT,
            "answerMaxLength": ANSWER_MAX_LENGTH,
        },
    }
