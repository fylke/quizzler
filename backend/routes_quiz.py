"""Quiz blueprint — quiz flow, hints, and answer checking."""

import os
import random
import re
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, session

from .auth import get_current_player, player_required
from .email_service import EmailServiceError, send_hint_complaint_email
from .models import Destination, GuestQuizResult, QuizResult, db
from .validation_rules import HINT_COUNT, MAX_GUESSES, STARTING_HINT_DIFFICULTY

quiz_bp = Blueprint("quiz", __name__)


RESULT_IMAGE_PREFIX = "0"
RESULT_IMAGE_MAX_COUNT = 10
RESULT_IMAGE_NAME_RE = re.compile(r"^0.*\.jpg$", re.IGNORECASE)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SCORE_LOCK_SESSION_KEY = "quiz_score_lock"
MEDIA_ACCESS_SESSION_KEY = "media_access_state"


def _media_root() -> Path:
    """Return the media root directory from env or project default."""
    media_dir = os.environ.get("MEDIA_DIR")
    if media_dir:
        return Path(str(media_dir))

    media_dir = current_app.config.get("MEDIA_DIR")
    if media_dir:
        return Path(str(media_dir))

    default_media = Path(__file__).resolve().parent.parent / "media"
    return Path(os.environ.get("MEDIA_DIR", str(default_media)))


def _result_images_for_destination(destination_id: int) -> list[str]:
    """Return up to 10 result image URLs for a destination.

    Result images are discovered from media/countries/<id>/ files that start
    with "0" (for example: 01.jpg, 0a.png).
    """
    destination_dir = _media_root() / "countries" / str(destination_id)
    if not destination_dir.is_dir():
        current_app.logger.debug(
            "Result images directory not found for destination %s: %s",
            destination_id,
            destination_dir,
        )
        return []

    images: list[str] = []
    for file_path in sorted(destination_dir.iterdir(), key=lambda p: p.name):
        if not file_path.is_file():
            continue
        if not file_path.name.startswith(RESULT_IMAGE_PREFIX):
            continue
        if not RESULT_IMAGE_NAME_RE.match(file_path.name):
            continue

        images.append(f"/media/countries/{destination_id}/{file_path.name}")
        if len(images) >= RESULT_IMAGE_MAX_COUNT:
            break

    current_app.logger.debug(
        "Discovered %s result images for destination %s in %s",
        len(images),
        destination_id,
        destination_dir,
    )

    return images


def _hint_images_for_destination(destination_id: int, hint_difficulty: int) -> list[str]:
    """Return the two quiz image URLs, preferring optimized _small.webp assets."""
    destination_dir = _media_root() / "countries" / str(destination_id)
    images: list[str] = []

    for suffix in ("a", "b"):
        optimized_name = f"{hint_difficulty}{suffix}_small.webp"
        optimized_path = destination_dir / optimized_name
        if optimized_path.is_file():
            images.append(f"/media/countries/{destination_id}/{optimized_name}")
        else:
            images.append(f"/media/countries/{destination_id}/{hint_difficulty}{suffix}.jpg")

    return images


def _active_result_for_player(player):
    if player.is_user:
        return QuizResult.query.filter_by(user_id=player.user_id, ongoing=True).first()
    if player.is_guest:
        return GuestQuizResult.query.filter_by(
            guest_session_id=player.guest_session_id,
            ongoing=True,
        ).first()
    return None


def _get_score_lock() -> dict | None:
    lock = session.get(SCORE_LOCK_SESSION_KEY)
    if not isinstance(lock, dict):
        return None

    required_keys = {"destination_id", "hint_difficulty", "remaining_guesses"}
    if not required_keys.issubset(lock.keys()):
        return None

    try:
        return {
            "destination_id": int(lock["destination_id"]),
            "hint_difficulty": int(lock["hint_difficulty"]),
            "remaining_guesses": int(lock["remaining_guesses"]),
        }
    except (TypeError, ValueError):
        return None


def _set_score_lock(destination_id: int, hint_difficulty: int, remaining_guesses: int):
    session[SCORE_LOCK_SESSION_KEY] = {
        "destination_id": int(destination_id),
        "hint_difficulty": int(hint_difficulty),
        "remaining_guesses": int(remaining_guesses),
    }


def _clear_score_lock():
    session.pop(SCORE_LOCK_SESSION_KEY, None)


def _get_media_access_state() -> dict | None:
    state = session.get(MEDIA_ACCESS_SESSION_KEY)
    if not isinstance(state, dict):
        return None

    required_keys = {"destination_id", "hint_difficulty"}
    if not required_keys.issubset(state.keys()):
        return None

    try:
        return {
            "destination_id": int(state["destination_id"]),
            "hint_difficulty": int(state["hint_difficulty"]),
        }
    except (TypeError, ValueError):
        return None


def _set_media_access_state(destination_id: int, hint_difficulty: int):
    session[MEDIA_ACCESS_SESSION_KEY] = {
        "destination_id": int(destination_id),
        "hint_difficulty": int(hint_difficulty),
    }


def _clear_media_access_state():
    session.pop(MEDIA_ACCESS_SESSION_KEY, None)


def _restore_locked_score_if_needed(quiz_result) -> int | None:
    """Restore preserved score fields for a rerun result when lock matches."""
    lock = _get_score_lock()
    if lock is None:
        return None

    if lock["destination_id"] != quiz_result.destination_id:
        return None

    quiz_result.hint_difficulty = lock["hint_difficulty"]
    quiz_result.remaining_guesses = lock["remaining_guesses"]
    return lock["hint_difficulty"] * lock["remaining_guesses"]


def _result_for_player_and_destination(player, destination_id):
    if player.is_user:
        return QuizResult.query.filter_by(
            user_id=player.user_id,
            destination_id=destination_id,
        ).first()
    if player.is_guest:
        return GuestQuizResult.query.filter_by(
            guest_session_id=player.guest_session_id,
            destination_id=destination_id,
        ).first()
    return None


def _end_active_quizzes_for_player(player):
    if player.is_user:
        active_results = QuizResult.query.filter_by(user_id=player.user_id, ongoing=True).all()
    elif player.is_guest:
        active_results = GuestQuizResult.query.filter_by(
            guest_session_id=player.guest_session_id,
            ongoing=True,
        ).all()
    else:
        active_results = []

    for result in active_results:
        _restore_locked_score_if_needed(result)
        result.ongoing = False

    if active_results:
        db.session.commit()

    _clear_score_lock()
    _clear_media_access_state()


def _new_result_for_player(player, destination_id):
    if player.is_user:
        return QuizResult(user_id=player.user_id, destination_id=destination_id)
    return GuestQuizResult(
        guest_session_id=player.guest_session_id,
        destination_id=destination_id,
    )


def _start_quiz_for_player(player, destination):
    """Set up server-side state for a new quiz and return response payload."""
    hint_difficulty = STARTING_HINT_DIFFICULTY
    hint_text = getattr(destination, f"hint{hint_difficulty}", "")

    _end_active_quizzes_for_player(player)

    quiz_result = _result_for_player_and_destination(player, destination.id)
    if quiz_result is not None and not quiz_result.ongoing:
        _set_score_lock(
            destination_id=quiz_result.destination_id,
            hint_difficulty=quiz_result.hint_difficulty,
            remaining_guesses=quiz_result.remaining_guesses,
        )
    else:
        _clear_score_lock()

    if quiz_result is None:
        quiz_result = _new_result_for_player(player, destination.id)

    quiz_result.hint_difficulty = hint_difficulty
    quiz_result.remaining_guesses = MAX_GUESSES
    quiz_result.ongoing = True
    db.session.add(quiz_result)
    db.session.commit()
    _set_media_access_state(destination.id, hint_difficulty)

    return {
        "id": destination.id,
        "hint": hint_text,
        "hintDifficulty": hint_difficulty,
        "remainingGuesses": MAX_GUESSES,
        "images": _hint_images_for_destination(destination.id, hint_difficulty),
    }


@quiz_bp.route("/api/quiz", methods=["GET"])
@player_required
def get_quiz():
    """Return a random destination along with its first hint and pictures."""
    destinations = Destination.query.all()
    if not destinations:
        return jsonify({"error": "No quiz data available"}), 404

    random_destination = random.choice(destinations)
    player = get_current_player()
    return jsonify(_start_quiz_for_player(player, random_destination))


@quiz_bp.route("/api/quiz/<int:destination_id>", methods=["GET"])
@player_required
def get_specific_quiz(destination_id):
    """Return a specific destination for a quiz."""
    destination = Destination.query.filter_by(id=destination_id).first()
    if not destination:
        return jsonify({"error": "Destination not found"}), 404

    player = get_current_player()
    return jsonify(_start_quiz_for_player(player, destination))


@quiz_bp.route("/api/quiz/active", methods=["GET"])
@player_required
def get_active_quiz():
    """Return the active quiz state for the logged-in user."""
    player = get_current_player()
    quiz_result = _active_result_for_player(player)
    if quiz_result is None:
        return jsonify({"error": "No active quiz"}), 404

    destination = Destination.query.filter_by(id=quiz_result.destination_id).first()
    if destination is None:
        return jsonify({"error": "Question not found"}), 404

    difficulty = quiz_result.hint_difficulty
    hint_text = getattr(destination, f"hint{difficulty}", "")
    _set_media_access_state(destination.id, difficulty)
    return jsonify(
        {
            "id": destination.id,
            "hint": hint_text,
            "hintDifficulty": difficulty,
            "remainingGuesses": quiz_result.remaining_guesses,
            "images": _hint_images_for_destination(destination.id, difficulty),
        }
    )


@quiz_bp.route("/api/hint", methods=["GET"])
@player_required
def get_hint():
    """Fetch the next hint for the user's active quiz, decrementing difficulty."""
    player = get_current_player()
    quiz_result = _active_result_for_player(player)
    if quiz_result is None:
        return jsonify({"error": "No active quiz"}), 404

    # Decrement hint difficulty to reveal an easier hint
    new_difficulty = quiz_result.hint_difficulty - 1
    if new_difficulty < 1:
        return jsonify({"error": "No more hints remaining"}), 404

    question = Destination.query.filter_by(id=quiz_result.destination_id).first()
    if not question:
        return jsonify({"error": "Question not found"}), 404

    quiz_result.hint_difficulty = new_difficulty
    db.session.commit()
    _set_media_access_state(question.id, new_difficulty)

    hint_text = getattr(question, f"hint{new_difficulty}", "")
    return jsonify(
        {
            "hint": hint_text,
            "hintDifficulty": new_difficulty,
            "remainingGuesses": quiz_result.remaining_guesses,
            "images": _hint_images_for_destination(question.id, new_difficulty),
        }
    )


@quiz_bp.route("/api/check-answer", methods=["POST"])
@player_required
def check_answer():
    """Check if the answer is correct, using server-side state for scoring."""
    data = request.json or {}
    user_answer = (data.get("answer") or "").lower().strip()

    player = get_current_player()
    quiz_result = _active_result_for_player(player)
    if quiz_result is None:
        return jsonify({"error": "No active quiz"}), 404

    question = Destination.query.filter_by(id=quiz_result.destination_id).first()
    if not question:
        return jsonify({"error": "Question not found"}), 404

    is_correct = user_answer in question.correct_answers

    if is_correct:
        attempt_points = quiz_result.hint_difficulty * quiz_result.remaining_guesses
        preserved_score = _restore_locked_score_if_needed(quiz_result)
        score_preserved = preserved_score is not None
        quiz_result.ongoing = False
        db.session.commit()
        _clear_score_lock()
        _clear_media_access_state()
        response_payload = {
            "correct": True,
            "answer": question.name,
            "points": attempt_points,
            "scorePreserved": score_preserved,
            "resultImages": _result_images_for_destination(question.id),
        }
        if score_preserved:
            response_payload["preservedScore"] = preserved_score
        return jsonify(
            response_payload
        )

    # Wrong answer — decrement remaining guesses
    quiz_result.remaining_guesses -= 1
    if quiz_result.remaining_guesses <= 0:
        preserved_score = _restore_locked_score_if_needed(quiz_result)
        score_preserved = preserved_score is not None
        quiz_result.ongoing = False
        db.session.commit()
        _clear_score_lock()
        _clear_media_access_state()
        response_payload = {
            "correct": False,
            "answer": question.name,
            "points": 0,
            "scorePreserved": score_preserved,
            "resultImages": _result_images_for_destination(question.id),
        }
        if score_preserved:
            response_payload["preservedScore"] = preserved_score
        return jsonify(
            response_payload
        )

    # Still has guesses left — keep same hint difficulty.
    # Users progress to the next hint only via the skip-hint flow.

    db.session.commit()
    _set_media_access_state(question.id, quiz_result.hint_difficulty)

    hint_text = getattr(question, f"hint{quiz_result.hint_difficulty}", "")
    return jsonify(
        {
            "correct": False,
            "remainingGuesses": quiz_result.remaining_guesses,
            "hintDifficulty": quiz_result.hint_difficulty,
            "hint": hint_text,
            "images": _hint_images_for_destination(
                question.id, quiz_result.hint_difficulty
            ),
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
    quiz_result = _active_result_for_player(player)
    if quiz_result is None:
        return jsonify({"error": "No active quiz"}), 404

    if quiz_result.destination_id != quiz_id:
        return jsonify({"error": "quizId does not match active quiz."}), 400

    if not (1 <= hint_difficulty <= HINT_COUNT):
        return jsonify({"error": "hintDifficulty is out of range."}), 400

    # Users can only complain about hints they have already unlocked.
    if hint_difficulty < quiz_result.hint_difficulty:
        return jsonify({"error": "Hint level has not been unlocked yet."}), 400

    question = Destination.query.filter_by(id=quiz_result.destination_id).first()
    if not question:
        return jsonify({"error": "Question not found"}), 404

    admin_email = (
        os.environ.get("ADMIN_EMAIL")
        or os.environ.get("SMTP_FROM_ADDRESS")
        or ""
    ).strip()

    hint_text = getattr(question, f"hint{hint_difficulty}", "")
    try:
        send_hint_complaint_email(
            admin_address=admin_email,
            reporter_email=complainer_email,
            reporter_name=(
                player.user.name if player.is_user else f"Guest #{player.guest_session_id}"
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
