"""Domain operations for multi-player friend games."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from .auth import PlayerContext
from .models import (
    FriendGame,
    FriendGameAnswer,
    FriendGameParticipant,
    FriendGameQuestion,
    _utcnow_naive,
    db,
)
from .quiz_adapters import get_quiz_adapter
from .quiz_types import get_quiz_type
from .validation_rules import MAX_GUESSES, STARTING_HINT_DIFFICULTY

MIN_QUESTION_COUNT = 1
MAX_QUESTION_COUNT = 10
GAME_LIFETIME = timedelta(days=7)
DISPLAY_NAME_MAX_LENGTH = 64


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _touch(game: FriendGame) -> None:
    now = _now()
    game.last_activity_at = now
    game.expires_at = now + GAME_LIFETIME


def get_game(raw_token: str) -> FriendGame | None:
    if not raw_token:
        return None
    game = FriendGame.query.filter_by(token_hash=_hash_token(raw_token)).first()
    if game is None or game.closed or game.expires_at <= _now():
        return None
    return game


def validate_display_name(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    name = " ".join(value.split())
    if not name or len(name) > DISPLAY_NAME_MAX_LENGTH:
        return None
    return name


def _participant_filter(player: PlayerContext) -> dict:
    if player.is_user:
        return {"user_id": player.user_id}
    return {"guest_session_id": player.guest_session_id}


def participant_for(
    game: FriendGame, player: PlayerContext
) -> FriendGameParticipant | None:
    return FriendGameParticipant.query.filter_by(
        game_id=game.id, **_participant_filter(player)
    ).first()


def _completed_results_by_source(player: PlayerContext, adapter) -> dict[int, object]:
    return {
        adapter.result_source_id(result): result
        for result in adapter.all_results(player)
        if not result.ongoing
    }


def seed_completed_answers(
    game: FriendGame, participant: FriendGameParticipant, player: PlayerContext
) -> None:
    adapter = game_adapter(game)
    completed_results = _completed_results_by_source(player, adapter)
    for question in game.questions:
        result = completed_results.get(question.source_id)
        if result is None:
            continue
        participant.answers.append(
            FriendGameAnswer(
                position=question.position,
                hint_difficulty=result.hint_difficulty,
                remaining_guesses=result.remaining_guesses,
                points=result.hint_difficulty * result.remaining_guesses,
                completed=True,
                correct=True,
                completed_at=_utcnow_naive(),
            )
        )
    complete_participant_if_needed(participant)


def create_game(
    player: PlayerContext,
    quiz_type: str,
    question_count: int | None,
    display_name: str,
    question_ids: list[int] | None = None,
):
    quiz_definition = get_quiz_type(quiz_type)
    if quiz_definition is None:
        raise ValueError("Quiz type not found")
    if question_ids is not None:
        if not MIN_QUESTION_COUNT <= len(question_ids) <= MAX_QUESTION_COUNT:
            raise ValueError("Quiz IDs must contain between 1 and 10 items")
        if len(set(question_ids)) != len(question_ids):
            raise ValueError("Quiz IDs must be unique")
    elif (
        question_count is None
        or not MIN_QUESTION_COUNT <= question_count <= MAX_QUESTION_COUNT
    ):
        raise ValueError("Question count must be between 1 and 10")
    name = validate_display_name(display_name)
    if name is None:
        raise ValueError("Display name is required and must be 64 characters or fewer")

    adapter = get_quiz_adapter(quiz_definition.adapter)
    if question_ids is not None:
        questions = []
        for question_id in question_ids:
            question = adapter.get_question(question_id)
            if question is None:
                raise ValueError(f"Quiz ID not found: {question_id}")
            questions.append(question)
        question_count = len(questions)
    else:
        questions = adapter.list_questions()
        completed_source_ids = set(_completed_results_by_source(player, adapter))
        questions = [
            question
            for question in questions
            if adapter.question_id(question) not in completed_source_ids
        ]
        if len(questions) < question_count:
            raise ValueError("Not enough unplayed questions available")

    import random

    selected = (
        questions
        if question_ids is not None
        else random.sample(questions, question_count)
    )
    raw_token = secrets.token_urlsafe(32)
    now = _now()
    game = FriendGame(
        id=str(uuid.uuid4()),
        token_hash=_hash_token(raw_token),
        quiz_type=quiz_definition.identifier,
        question_count=question_count,
        created_at=now,
        last_activity_at=now,
        expires_at=now + GAME_LIFETIME,
    )
    db.session.add(game)
    for position, question in enumerate(selected):
        game.questions.append(
            FriendGameQuestion(
                position=position, source_id=adapter.question_id(question)
            )
        )

    participant = FriendGameParticipant(
        game=game,
        display_name=name,
        user_id=player.user_id if player.is_user else None,
        guest_session_id=player.guest_session_id if player.is_guest else None,
    )
    db.session.add(participant)
    db.session.flush()
    seed_completed_answers(game, participant, player)
    db.session.commit()
    return game, participant, raw_token


def join_game(game: FriendGame, player: PlayerContext, display_name: str):
    name = validate_display_name(display_name)
    if name is None:
        raise ValueError("Display name is required and must be 64 characters or fewer")

    participant = participant_for(game, player)
    if participant is None:
        participant = FriendGameParticipant(
            game=game,
            display_name=name,
            user_id=player.user_id if player.is_user else None,
            guest_session_id=player.guest_session_id if player.is_guest else None,
        )
        db.session.add(participant)
    else:
        participant.display_name = name
    if not participant.answers:
        db.session.flush()
        seed_completed_answers(game, participant, player)
    _touch(game)
    db.session.commit()
    return participant


def current_answer(participant: FriendGameParticipant) -> FriendGameAnswer | None:
    completed_positions = {
        answer.position for answer in participant.answers if answer.completed
    }
    if len(completed_positions) >= participant.game.question_count:
        return None
    position = 0
    while position in completed_positions:
        position += 1
    answer = next(
        (item for item in participant.answers if item.position == position), None
    )
    if answer is None:
        answer = FriendGameAnswer(
            participant=participant,
            position=position,
            hint_difficulty=STARTING_HINT_DIFFICULTY,
            remaining_guesses=MAX_GUESSES,
        )
        db.session.add(answer)
        db.session.flush()
    return answer


def answer_for_position(participant: FriendGameParticipant, position: int):
    return FriendGameAnswer.query.filter_by(
        participant_id=participant.id, position=position
    ).first()


def game_adapter(game: FriendGame):
    quiz_definition = get_quiz_type(game.quiz_type)
    return get_quiz_adapter(quiz_definition.adapter) if quiz_definition else None


def serialize_leaderboard(game: FriendGame) -> list[dict]:
    rows = []
    for participant in game.participants:
        rows.append(
            {
                "displayName": participant.display_name,
                "score": sum(answer.points for answer in participant.answers),
                "completedQuestions": sum(
                    answer.completed for answer in participant.answers
                ),
                "questionCount": game.question_count,
                "completed": participant.completed_at is not None,
            }
        )
    return sorted(rows, key=lambda row: (-row["score"], row["displayName"].lower()))


def complete_participant_if_needed(participant: FriendGameParticipant) -> None:
    if (
        all(answer.completed for answer in participant.answers)
        and len(participant.answers) == participant.game.question_count
    ):
        participant.completed_at = _utcnow_naive()
