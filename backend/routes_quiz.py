"""Quiz blueprint — quiz flow, hints, and answer checking."""

import os
import random
import re
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from .auth import get_current_user, login_required
from .email_service import EmailServiceError, send_hint_complaint_email
from .models import Destination, QuizResult, db
from .validation_rules import HINT_COUNT, MAX_GUESSES, STARTING_HINT_DIFFICULTY

quiz_bp = Blueprint("quiz", __name__)


RESULT_IMAGE_PREFIX = "0"
RESULT_IMAGE_MAX_COUNT = 10
RESULT_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _media_root() -> Path:
    """Return the media root directory from env or project default."""
    default_media = Path(__file__).resolve().parent.parent / "media"
    return Path(os.environ.get("MEDIA_DIR", str(default_media)))


def _result_images_for_destination(destination_id: int) -> list[str]:
    """Return up to 10 result image URLs for a destination.

    Result images are discovered from media/countries/<id>/ files that start
    with "0" (for example: 01.jpg, 0a.png).
    """
    destination_dir = _media_root() / "countries" / str(destination_id)
    if not destination_dir.is_dir():
        return []

    images: list[str] = []
    for file_path in sorted(destination_dir.iterdir(), key=lambda p: p.name):
        if not file_path.is_file():
            continue
        if not file_path.name.startswith(RESULT_IMAGE_PREFIX):
            continue
        if file_path.suffix.lower() not in RESULT_IMAGE_EXTENSIONS:
            continue

        images.append(f"/media/countries/{destination_id}/{file_path.name}")
        if len(images) >= RESULT_IMAGE_MAX_COUNT:
            break

    return images


def _hint_images_for_destination(destination_id: int, hint_difficulty: int) -> list[str]:
    """Return the two quiz image URLs for a destination and hint difficulty."""
    return [
        f"/media/countries/{destination_id}/{hint_difficulty}a.jpg",
        f"/media/countries/{destination_id}/{hint_difficulty}b.jpg",
    ]


def _start_quiz(user, destination):
    """Set up server-side state for a new quiz and return the response dict.

    Ends any previously active quiz for this user, creates or resets
    the QuizResult row, and commits the transaction.
    """
    hint_difficulty = STARTING_HINT_DIFFICULTY
    hint_text = getattr(destination, f"hint{hint_difficulty}", "")

    # End any previously active quiz
    QuizResult.query.filter_by(user_id=user.id, ongoing=True).update({"ongoing": False})

    quiz_result = QuizResult.query.filter_by(
        user_id=user.id, destination_id=destination.id
    ).first()
    if quiz_result is None:
        quiz_result = QuizResult(user_id=user.id, destination_id=destination.id)
    quiz_result.hint_difficulty = hint_difficulty
    quiz_result.remaining_guesses = MAX_GUESSES
    quiz_result.ongoing = True
    db.session.add(quiz_result)
    db.session.commit()

    return {
        "id": destination.id,
        "hint": hint_text,
        "hintDifficulty": hint_difficulty,
        "remainingGuesses": MAX_GUESSES,
        "images": _hint_images_for_destination(destination.id, hint_difficulty),
    }


@quiz_bp.route("/api/quiz", methods=["GET"])
@login_required
def get_quiz():
    """Return a random destination along with its first hint and pictures."""
    destinations = Destination.query.all()
    if not destinations:
        return jsonify({"error": "No quiz data available"}), 404

    random_destination = random.choice(destinations)
    user = get_current_user()
    return jsonify(_start_quiz(user, random_destination))


@quiz_bp.route("/api/quiz/<int:destination_id>", methods=["GET"])
@login_required
def get_specific_quiz(destination_id):
    """Return a specific destination for a quiz."""
    destination = Destination.query.filter_by(id=destination_id).first()
    if not destination:
        return jsonify({"error": "Destination not found"}), 404

    user = get_current_user()
    return jsonify(_start_quiz(user, destination))


@quiz_bp.route("/api/quiz/active", methods=["GET"])
@login_required
def get_active_quiz():
    """Return the active quiz state for the logged-in user."""
    user = get_current_user()
    quiz_result = QuizResult.query.filter_by(user_id=user.id, ongoing=True).first()
    if quiz_result is None:
        return jsonify({"error": "No active quiz"}), 404

    destination = Destination.query.filter_by(id=quiz_result.destination_id).first()
    if destination is None:
        return jsonify({"error": "Question not found"}), 404

    difficulty = quiz_result.hint_difficulty
    hint_text = getattr(destination, f"hint{difficulty}", "")
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
@login_required
def get_hint():
    """Fetch the next hint for the user's active quiz, decrementing difficulty."""
    user = get_current_user()
    quiz_result = QuizResult.query.filter_by(user_id=user.id, ongoing=True).first()
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
@login_required
def check_answer():
    """Check if the answer is correct, using server-side state for scoring."""
    data = request.json or {}
    user_answer = (data.get("answer") or "").lower().strip()

    user = get_current_user()
    quiz_result = QuizResult.query.filter_by(user_id=user.id, ongoing=True).first()
    if quiz_result is None:
        return jsonify({"error": "No active quiz"}), 404

    question = Destination.query.filter_by(id=quiz_result.destination_id).first()
    if not question:
        return jsonify({"error": "Question not found"}), 404

    is_correct = user_answer in question.correct_answers

    if is_correct:
        points = quiz_result.hint_difficulty * quiz_result.remaining_guesses
        quiz_result.ongoing = False
        db.session.commit()
        return jsonify(
            {
                "correct": True,
                "answer": question.name,
                "points": points,
                "resultImages": _result_images_for_destination(question.id),
            }
        )

    # Wrong answer — decrement remaining guesses
    quiz_result.remaining_guesses -= 1
    if quiz_result.remaining_guesses <= 0:
        quiz_result.ongoing = False
        db.session.commit()
        return jsonify(
            {
                "correct": False,
                "answer": question.name,
                "points": 0,
                "resultImages": _result_images_for_destination(question.id),
            }
        )

    # Still has guesses left — keep same hint difficulty.
    # Users progress to the next hint only via the skip-hint flow.

    db.session.commit()

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
@login_required
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

    user = get_current_user()
    quiz_result = QuizResult.query.filter_by(user_id=user.id, ongoing=True).first()
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
            reporter_name=user.name,
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
