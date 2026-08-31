"""Quiz blueprint — quiz flow, hints, and answer checking."""

import os
import re

from flask import Blueprint, current_app, jsonify, request, session

from .auth import get_current_player, player_required
from .email_service import EmailServiceError, send_hint_complaint_email
from .models import db
from .quiz_adapters import get_quiz_adapter, get_quiz_adapters
from .quiz_catalog import get_or_create_quiz_identity, public_quiz_id, resolve_quiz_id
from .quiz_types import get_quiz_type
from .validation_rules import HINT_COUNT, MAX_GUESSES, STARTING_HINT_DIFFICULTY

quiz_bp = Blueprint("quiz", __name__)


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SCORE_LOCK_SESSION_KEY = "quiz_score_lock"
MEDIA_ACCESS_SESSION_KEY = "media_access_state"


def _active_result_for_player(player):
    for adapter in get_quiz_adapters():
        result = adapter.active_result(player)
        if result is not None:
            return adapter, result
    return None, None


def _get_score_lock() -> dict | None:
    lock = session.get(SCORE_LOCK_SESSION_KEY)
    if not isinstance(lock, dict):
        return None

    required_keys = {"quiz_type", "source_id", "hint_difficulty", "remaining_guesses"}
    if not required_keys.issubset(lock.keys()):
        return None

    try:
        return {
            "quiz_type": str(lock["quiz_type"]),
            "source_id": int(lock["source_id"]),
            "hint_difficulty": int(lock["hint_difficulty"]),
            "remaining_guesses": int(lock["remaining_guesses"]),
        }
    except (TypeError, ValueError):
        return None


def _set_score_lock(
    quiz_type: str, source_id: int, hint_difficulty: int, remaining_guesses: int
):
    session[SCORE_LOCK_SESSION_KEY] = {
        "quiz_type": quiz_type,
        "source_id": int(source_id),
        "hint_difficulty": int(hint_difficulty),
        "remaining_guesses": int(remaining_guesses),
    }


def _clear_score_lock():
    session.pop(SCORE_LOCK_SESSION_KEY, None)


def _get_media_access_state() -> dict | None:
    state = session.get(MEDIA_ACCESS_SESSION_KEY)
    if not isinstance(state, dict):
        return None

    required_keys = {"quiz_type", "source_id", "hint_difficulty"}
    if not required_keys.issubset(state.keys()):
        return None

    try:
        return {
            "quiz_type": str(state["quiz_type"]),
            "source_id": int(state["source_id"]),
            "hint_difficulty": int(state["hint_difficulty"]),
        }
    except (TypeError, ValueError):
        return None


def _set_media_access_state(quiz_type: str, source_id: int, hint_difficulty: int):
    session[MEDIA_ACCESS_SESSION_KEY] = {
        "quiz_type": quiz_type,
        "source_id": int(source_id),
        "hint_difficulty": int(hint_difficulty),
    }


def _clear_media_access_state():
    session.pop(MEDIA_ACCESS_SESSION_KEY, None)


def _restore_locked_score_if_needed(adapter, quiz_result) -> int | None:
    """Restore preserved score fields for a rerun result when lock matches."""
    lock = _get_score_lock()
    if lock is None:
        return None

    if lock["quiz_type"] != adapter.identifier:
        return None
    if lock["source_id"] != adapter.result_source_id(quiz_result):
        return None

    quiz_result.hint_difficulty = lock["hint_difficulty"]
    quiz_result.remaining_guesses = lock["remaining_guesses"]
    return lock["hint_difficulty"] * lock["remaining_guesses"]


def _end_active_quizzes_for_player(player):
    active_results = []
    for adapter in get_quiz_adapters():
        for result in adapter.active_results(player):
            active_results.append(result)
            _restore_locked_score_if_needed(adapter, result)
            result.ongoing = False

    if active_results:
        db.session.commit()

    _clear_score_lock()
    _clear_media_access_state()


def _start_quiz_for_player(player, adapter, question):
    """Set up server-side state for a new quiz and return response payload."""
    hint_difficulty = STARTING_HINT_DIFFICULTY
    source_id = adapter.question_id(question)
    hint_text = adapter.hint_text(question, hint_difficulty)
    identity = get_or_create_quiz_identity(adapter.identifier, source_id)

    _end_active_quizzes_for_player(player)

    quiz_result = adapter.result_for_question(player, source_id)
    if quiz_result is not None and not quiz_result.ongoing:
        _set_score_lock(
            quiz_type=adapter.identifier,
            source_id=adapter.result_source_id(quiz_result),
            hint_difficulty=quiz_result.hint_difficulty,
            remaining_guesses=quiz_result.remaining_guesses,
        )
    else:
        _clear_score_lock()

    if quiz_result is None:
        quiz_result = adapter.new_result(player, source_id)

    quiz_result.hint_difficulty = hint_difficulty
    quiz_result.remaining_guesses = MAX_GUESSES
    quiz_result.ongoing = True
    db.session.add(quiz_result)
    db.session.commit()
    _set_media_access_state(adapter.identifier, source_id, hint_difficulty)

    return {
        "id": source_id,
        "guid": public_quiz_id(identity.quiz_type, identity.source_id),
        "quizType": adapter.identifier,
        "hint": hint_text,
        "hintDifficulty": hint_difficulty,
        "remainingGuesses": MAX_GUESSES,
        "images": adapter.hint_images(question, hint_difficulty),
    }


@quiz_bp.route("/api/quiz", methods=["GET"])
@player_required
def get_quiz():
    """Return a random question for a registered quiz type."""
    quiz_type = get_quiz_type(request.args.get("type", "countries"))
    adapter = get_quiz_adapter(quiz_type.adapter) if quiz_type is not None else None
    if adapter is None:
        return jsonify({"error": "Quiz type not found"}), 404

    question = adapter.random_question()
    if question is None:
        return jsonify({"error": "No quiz data available"}), 404

    player = get_current_player()
    return jsonify(_start_quiz_for_player(player, adapter, question))


@quiz_bp.route("/api/quiz/<quiz_guid>", methods=["GET"])
@player_required
def get_specific_quiz(quiz_guid):
    """Return a specific quiz identified by its public ID."""
    identity = resolve_quiz_id(quiz_guid)
    quiz_type = get_quiz_type(identity.quiz_type) if identity is not None else None
    adapter = get_quiz_adapter(quiz_type.adapter) if quiz_type is not None else None
    if identity is None or adapter is None:
        return jsonify({"error": "Quiz not found"}), 404

    question = adapter.get_question(identity.source_id)
    if question is None:
        return jsonify({"error": "Quiz not found"}), 404

    player = get_current_player()
    return jsonify(_start_quiz_for_player(player, adapter, question))


@quiz_bp.route("/api/quiz/active", methods=["GET"])
@player_required
def get_active_quiz():
    """Return the active quiz state for the logged-in user."""
    player = get_current_player()
    adapter, quiz_result = _active_result_for_player(player)
    if quiz_result is None:
        return jsonify({"error": "No active quiz"}), 404

    source_id = adapter.result_source_id(quiz_result)
    question = adapter.get_question(source_id)
    if question is None:
        return jsonify({"error": "Question not found"}), 404

    difficulty = quiz_result.hint_difficulty
    hint_text = adapter.hint_text(question, difficulty)
    identity = get_or_create_quiz_identity(adapter.identifier, source_id)
    db.session.commit()
    _set_media_access_state(adapter.identifier, source_id, difficulty)
    return jsonify(
        {
            "id": source_id,
            "guid": public_quiz_id(identity.quiz_type, identity.source_id),
            "quizType": adapter.identifier,
            "hint": hint_text,
            "hintDifficulty": difficulty,
            "remainingGuesses": quiz_result.remaining_guesses,
            "images": adapter.hint_images(question, difficulty),
        }
    )


@quiz_bp.route("/api/hint", methods=["GET"])
@player_required
def get_hint():
    """Fetch the next hint for the user's active quiz, decrementing difficulty."""
    player = get_current_player()
    adapter, quiz_result = _active_result_for_player(player)
    if quiz_result is None:
        return jsonify({"error": "No active quiz"}), 404

    # Decrement hint difficulty to reveal an easier hint
    new_difficulty = quiz_result.hint_difficulty - 1
    if new_difficulty < 1:
        return jsonify({"error": "No more hints remaining"}), 404

    source_id = adapter.result_source_id(quiz_result)
    question = adapter.get_question(source_id)
    if not question:
        return jsonify({"error": "Question not found"}), 404

    quiz_result.hint_difficulty = new_difficulty
    db.session.commit()
    _set_media_access_state(adapter.identifier, source_id, new_difficulty)

    hint_text = adapter.hint_text(question, new_difficulty)
    return jsonify(
        {
            "hint": hint_text,
            "hintDifficulty": new_difficulty,
            "remainingGuesses": quiz_result.remaining_guesses,
            "images": adapter.hint_images(question, new_difficulty),
        }
    )


@quiz_bp.route("/api/check-answer", methods=["POST"])
@player_required
def check_answer():
    """Check if the answer is correct, using server-side state for scoring."""
    data = request.json or {}
    user_answer = (data.get("answer") or "").lower().strip()

    player = get_current_player()
    adapter, quiz_result = _active_result_for_player(player)
    if quiz_result is None:
        return jsonify({"error": "No active quiz"}), 404

    source_id = adapter.result_source_id(quiz_result)
    question = adapter.get_question(source_id)
    if not question:
        return jsonify({"error": "Question not found"}), 404

    is_correct = user_answer in adapter.correct_answers(question)

    if is_correct:
        attempt_points = quiz_result.hint_difficulty * quiz_result.remaining_guesses
        preserved_score = _restore_locked_score_if_needed(adapter, quiz_result)
        score_preserved = preserved_score is not None
        quiz_result.ongoing = False
        db.session.commit()
        _clear_score_lock()
        # Keep result-gallery images readable after completion.
        _set_media_access_state(adapter.identifier, source_id, 1)
        response_payload = {
            "correct": True,
            "answer": adapter.answer_name(question),
            "points": attempt_points,
            "scorePreserved": score_preserved,
            "resultImages": adapter.result_images(question),
        }
        if score_preserved:
            response_payload["preservedScore"] = preserved_score
        return jsonify(response_payload)

    # Wrong answer — decrement remaining guesses
    quiz_result.remaining_guesses -= 1
    if quiz_result.remaining_guesses <= 0:
        preserved_score = _restore_locked_score_if_needed(adapter, quiz_result)
        score_preserved = preserved_score is not None
        quiz_result.ongoing = False
        db.session.commit()
        _clear_score_lock()
        # Keep result-gallery images readable after completion.
        _set_media_access_state(adapter.identifier, source_id, 1)
        response_payload = {
            "correct": False,
            "answer": adapter.answer_name(question),
            "points": 0,
            "scorePreserved": score_preserved,
            "resultImages": adapter.result_images(question),
        }
        if score_preserved:
            response_payload["preservedScore"] = preserved_score
        return jsonify(response_payload)

    # Still has guesses left — keep same hint difficulty.
    # Users progress to the next hint only via the skip-hint flow.

    db.session.commit()
    _set_media_access_state(
        adapter.identifier,
        source_id,
        quiz_result.hint_difficulty,
    )

    hint_text = adapter.hint_text(question, quiz_result.hint_difficulty)
    return jsonify(
        {
            "correct": False,
            "remainingGuesses": quiz_result.remaining_guesses,
            "hintDifficulty": quiz_result.hint_difficulty,
            "hint": hint_text,
            "images": adapter.hint_images(question, quiz_result.hint_difficulty),
        }
    )


@quiz_bp.route("/api/hint-complaint", methods=["POST"])
@player_required
def submit_hint_complaint():
    """Submit a hint complaint to admin email for the active quiz."""
    data = request.json or {}

    try:
        quiz_id = int(data.get("quizId"))
        hint_difficulty = int(data.get("hintDifficulty"))
    except (TypeError, ValueError):
        return jsonify({"error": "quizId and hintDifficulty must be integers."}), 400

    complaint_message = (data.get("message") or "").strip()
    complainer_email = (data.get("complainerEmail") or "").strip().lower()
    if not complainer_email:
        return jsonify({"error": "complainerEmail is required."}), 400
    if not EMAIL_RE.match(complainer_email):
        return jsonify({"error": "Invalid complainerEmail format."}), 400

    if not complaint_message:
        return jsonify({"error": "Complaint message is required."}), 400
    if len(complaint_message) > 2000:
        return jsonify({"error": "Complaint message is too long."}), 400

    player = get_current_player()
    adapter, quiz_result = _active_result_for_player(player)
    if quiz_result is None:
        return jsonify({"error": "No active quiz"}), 404

    source_id = adapter.result_source_id(quiz_result)
    if source_id != quiz_id:
        return jsonify({"error": "quizId does not match active quiz."}), 400

    if not (1 <= hint_difficulty <= HINT_COUNT):
        return jsonify({"error": "hintDifficulty is out of range."}), 400

    # Users can only complain about hints they have already unlocked.
    if hint_difficulty < quiz_result.hint_difficulty:
        return jsonify({"error": "Hint level has not been unlocked yet."}), 400

    question = adapter.get_question(source_id)
    if not question:
        return jsonify({"error": "Question not found"}), 404

    admin_email = (
        os.environ.get("ADMIN_EMAIL") or os.environ.get("SMTP_FROM_ADDRESS") or ""
    ).strip()

    hint_text = adapter.hint_text(question, hint_difficulty)
    try:
        send_hint_complaint_email(
            admin_address=admin_email,
            reporter_email=complainer_email,
            reporter_name=(
                player.user.email
                if player.is_user
                else f"Guest #{player.guest_session_id}"
            ),
            quiz_id=quiz_id,
            hint_difficulty=hint_difficulty,
            hint_text=hint_text,
            message=complaint_message,
        )
    except EmailServiceError as exc:
        current_app.logger.error(
            "Failed to send hint complaint email for quiz %s: %s",
            quiz_id,
            exc.reason,
        )
        return jsonify({"error": "Failed to send complaint email."}), 500

    return jsonify({"message": "Complaint sent."})
