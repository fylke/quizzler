"""Friend-game API routes."""

from flask import Blueprint, jsonify, request

from .auth import (
    csrf_protected,
    generate_csrf_token,
    get_current_player,
    player_required,
)
from .friend_games import (
    GAME_LIFETIME,
    MAX_QUESTION_COUNT,
    MIN_QUESTION_COUNT,
    answer_for_position,
    complete_participant_if_needed,
    create_game,
    current_answer,
    game_adapter,
    get_game,
    join_game,
    participant_for,
    serialize_leaderboard,
    _now,
)
from .models import _utcnow_naive, db

friend_games_bp = Blueprint("friend_games", __name__)


def _game_metadata(game):
    return {
        "questionCount": game.question_count,
        "participantCount": len(game.participants),
        "expiresAt": game.expires_at.isoformat(),
    }


def _question_payload(game, participant, answer):
    if answer is None:
        return {"position": game.question_count, "questionCount": game.question_count}
    adapter = game_adapter(game)
    question = adapter.get_question(game.questions[answer.position].source_id)
    return {
        "position": answer.position,
        "questionCount": game.question_count,
        "hint": adapter.hint_text(question, answer.hint_difficulty),
        "hintDifficulty": answer.hint_difficulty,
        "remainingGuesses": answer.remaining_guesses,
        "images": adapter.hint_images(question, answer.hint_difficulty),
    }


def _participant_state(game, participant):
    answer = current_answer(participant)
    db.session.commit()
    return {
        "game": _game_metadata(game),
        "participant": {
            "displayName": participant.display_name,
            "completed": participant.completed_at is not None,
        },
        "question": _question_payload(game, participant, answer),
        "leaderboard": serialize_leaderboard(game),
    }


def _find_game_or_404(token):
    game = get_game(token)
    if game is None:
        return None, (jsonify({"error": "Friend game not found or expired"}), 404)
    return game, None


@friend_games_bp.get("/api/friend-games/csrf")
def friend_game_csrf():
    return jsonify({"csrfToken": generate_csrf_token()})


@friend_games_bp.post("/api/friend-games")
@player_required
@csrf_protected
def create_friend_game():
    data = request.json or {}
    raw_question_ids = data.get("quizIds")
    question_ids = None
    if raw_question_ids is not None:
        if not isinstance(raw_question_ids, list):
            return jsonify({"error": "quizIds must be a list of integers"}), 400
        try:
            question_ids = [int(question_id) for question_id in raw_question_ids]
        except (TypeError, ValueError):
            return jsonify({"error": "quizIds must be a list of integers"}), 400
        question_count = len(question_ids)
    else:
        try:
            question_count = int(data.get("questionCount"))
        except (TypeError, ValueError):
            return jsonify({"error": "Question count must be an integer"}), 400
        if not MIN_QUESTION_COUNT <= question_count <= MAX_QUESTION_COUNT:
            return jsonify({"error": "Question count must be between 1 and 10"}), 400

    try:
        game, participant, raw_token = create_game(
            get_current_player(),
            str(data.get("quizType", "countries")),
            question_count,
            data.get("displayName"),
            question_ids=question_ids,
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    return (
        jsonify(
            {
                "token": raw_token,
                "url": f"/friend/{raw_token}",
                "participant": {"displayName": participant.display_name},
                "game": _game_metadata(game),
            }
        ),
        201,
    )


@friend_games_bp.get("/api/friend-games/<token>")
def inspect_friend_game(token):
    game, error = _find_game_or_404(token)
    if error:
        return error
    return jsonify(_game_metadata(game))


@friend_games_bp.post("/api/friend-games/<token>/join")
@player_required
@csrf_protected
def join_friend_game(token):
    game, error = _find_game_or_404(token)
    if error:
        return error
    try:
        participant = join_game(
            game, get_current_player(), (request.json or {}).get("displayName")
        )
    except ValueError as validation_error:
        return jsonify({"error": str(validation_error)}), 400
    return jsonify(_participant_state(game, participant))


@friend_games_bp.get("/api/friend-games/<token>/state")
@player_required
def friend_game_state(token):
    game, error = _find_game_or_404(token)
    if error:
        return error
    participant = participant_for(game, get_current_player())
    if participant is None:
        return jsonify({"error": "Join this friend game first"}), 403
    return jsonify(_participant_state(game, participant))


@friend_games_bp.post("/api/friend-games/<token>/hint")
@player_required
@csrf_protected
def friend_game_hint(token):
    game, error = _find_game_or_404(token)
    if error:
        return error
    participant = participant_for(game, get_current_player())
    if participant is None:
        return jsonify({"error": "Join this friend game first"}), 403
    answer = current_answer(participant)
    if answer is None:
        return jsonify(_participant_state(game, participant))
    if answer.hint_difficulty <= 1:
        return jsonify({"error": "No more hints remaining"}), 400
    answer.hint_difficulty -= 1
    game.last_activity_at = _now()
    game.expires_at = _now() + GAME_LIFETIME
    db.session.commit()
    return jsonify(_participant_state(game, participant))


@friend_games_bp.post("/api/friend-games/<token>/answer")
@player_required
@csrf_protected
def friend_game_answer(token):
    game, error = _find_game_or_404(token)
    if error:
        return error
    participant = participant_for(game, get_current_player())
    if participant is None:
        return jsonify({"error": "Join this friend game first"}), 403
    answer = current_answer(participant)
    if answer is None:
        return jsonify(_participant_state(game, participant))

    data = request.json or {}
    try:
        position = int(data.get("position"))
    except (TypeError, ValueError):
        return jsonify({"error": "Question position must be an integer"}), 400
    if position != answer.position:
        return jsonify({"error": "Question is no longer active"}), 409

    adapter = game_adapter(game)
    question = adapter.get_question(game.questions[position].source_id)
    is_correct = str(data.get("answer", "")).strip().lower() in adapter.correct_answers(
        question
    )
    points = answer.hint_difficulty * answer.remaining_guesses if is_correct else 0
    answer.points = points
    answer.correct = is_correct
    if not is_correct:
        answer.remaining_guesses -= 1
    if is_correct or answer.remaining_guesses <= 0:
        answer.completed = True
        answer.completed_at = _utcnow_naive()
        complete_participant_if_needed(participant)
    game.last_activity_at = _now()
    db.session.commit()

    return jsonify(
        {
            "correct": is_correct,
            "points": points,
            "answer": adapter.answer_name(question),
            **_participant_state(game, participant),
        }
    )


@friend_games_bp.get("/api/friend-games/<token>/results")
@player_required
def friend_game_results(token):
    game, error = _find_game_or_404(token)
    if error:
        return error
    if participant_for(game, get_current_player()) is None:
        return jsonify({"error": "Join this friend game first"}), 403
    return jsonify({"leaderboard": serialize_leaderboard(game)})
