"""Shared session helpers for quiz request state."""

from flask import session

from .quiz_adapters import get_quiz_adapters

MEDIA_ACCESS_SESSION_KEY = "media_access_state"


def active_result_for_player(player):
    for adapter in get_quiz_adapters():
        result = adapter.active_result(player)
        if result is not None:
            return adapter, result
    return None, None


def get_media_access_state() -> dict | None:
    state = session.get(MEDIA_ACCESS_SESSION_KEY)
    if not isinstance(state, dict):
        return None

    required_keys = {"quiz_type", "source_id", "hint_difficulty"}
    if not required_keys.issubset(state.keys()):
        return None

    try:
        source_id = int(state["source_id"])
        hint_difficulty = int(state["hint_difficulty"])
    except (TypeError, ValueError):
        return None

    if hint_difficulty < 1:
        return None

    return {
        "quiz_type": str(state["quiz_type"]),
        "source_id": source_id,
        "hint_difficulty": hint_difficulty,
    }


def set_media_access_state(quiz_type: str, source_id: int, hint_difficulty: int):
    session[MEDIA_ACCESS_SESSION_KEY] = {
        "quiz_type": quiz_type,
        "source_id": int(source_id),
        "hint_difficulty": int(hint_difficulty),
    }


def clear_media_access_state():
    session.pop(MEDIA_ACCESS_SESSION_KEY, None)
