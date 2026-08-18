"""Gameplay adapters for registered quiz types."""

import os
import random
from pathlib import Path
from typing import Protocol

from flask import current_app

from .admin import normalize_answers
from .models import Destination, GuestQuizResult, QuizResult, db


class QuizAdapter(Protocol):
    """Behavior a quiz type supplies to the shared gameplay routes."""

    identifier: str
    media_namespace: str

    def random_question(self): ...

    def get_question(self, source_id: int): ...

    def question_id(self, question) -> int: ...

    def answer_name(self, question) -> str: ...

    def correct_answers(self, question) -> list[str]: ...

    def hint_text(self, question, difficulty: int) -> str: ...

    def hint_images(self, question, difficulty: int) -> list[str]: ...

    def result_images(self, question) -> list[str]: ...

    def active_result(self, player): ...

    def active_results(self, player) -> list: ...

    def all_results(self, player) -> list: ...

    def guest_results(self, guest_session_id: int) -> list: ...

    def result_for_question(self, player, source_id: int): ...

    def new_result(self, player, source_id: int): ...

    def result_source_id(self, result) -> int: ...

    def list_questions(self) -> list: ...

    def serialize_question(self, question) -> dict: ...

    def create_question(self, data: dict): ...

    def update_question(self, question, data: dict): ...

    def delete_question(self, question) -> None: ...

    def seed_questions(self, records: list[dict]) -> int: ...


RESULT_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})


class StandardQuizAdapter:
    """Adapter for the standard name, hints, answers, and media schema."""

    def __init__(
        self,
        *,
        identifier: str,
        question_model,
        user_result_model,
        guest_result_model,
        result_source_field: str,
        media_namespace: str | None = None,
    ):
        self.identifier = identifier
        self.media_namespace = media_namespace or identifier
        self.question_model = question_model
        self.user_result_model = user_result_model
        self.guest_result_model = guest_result_model
        self.result_source_field = result_source_field

    def random_question(self):
        questions = self.question_model.query.all()
        return random.choice(questions) if questions else None

    def get_question(self, source_id: int):
        return self.question_model.query.filter_by(id=source_id).first()

    def question_id(self, question) -> int:
        return question.id

    def answer_name(self, question) -> str:
        return question.name

    def correct_answers(self, question) -> list[str]:
        return question.correct_answers

    def hint_text(self, question, difficulty: int) -> str:
        return getattr(question, f"hint{difficulty}", "")

    def _question_media_dir(self, question) -> Path:
        media_root = os.environ.get("MEDIA_DIR") or current_app.config["MEDIA_DIR"]
        return Path(media_root) / self.media_namespace / str(question.id)

    def hint_images(self, question, difficulty: int) -> list[str]:
        question_dir = self._question_media_dir(question)
        images = []
        for suffix in ("a", "b"):
            optimized_name = f"{difficulty}{suffix}_small.webp"
            if (question_dir / optimized_name).is_file():
                filename = optimized_name
            else:
                filename = f"{difficulty}{suffix}.jpg"
            images.append(f"/media/{self.media_namespace}/{question.id}/{filename}")
        return images

    def result_images(self, question) -> list[str]:
        question_dir = self._question_media_dir(question)
        if not question_dir.is_dir():
            return []

        selected_by_stem: dict[str, Path] = {}
        for file_path in sorted(question_dir.iterdir(), key=lambda path: path.name):
            if (
                not file_path.is_file()
                or file_path.suffix.lower() not in RESULT_IMAGE_EXTENSIONS
            ):
                continue
            base_stem = (
                file_path.stem[: -len("_small")]
                if file_path.stem.endswith("_small")
                else file_path.stem
            )
            existing = selected_by_stem.get(base_stem)
            if existing is None or (
                file_path.stem.endswith("_small")
                and not existing.stem.endswith("_small")
            ):
                selected_by_stem[base_stem] = file_path

        return [
            f"/media/{self.media_namespace}/{question.id}/{selected_by_stem[stem].name}"
            for stem in sorted(selected_by_stem)
        ]

    def active_result(self, player):
        if player.is_user:
            return self.user_result_model.query.filter_by(
                user_id=player.user_id,
                ongoing=True,
            ).first()
        if player.is_guest:
            return self.guest_result_model.query.filter_by(
                guest_session_id=player.guest_session_id,
                ongoing=True,
            ).first()
        return None

    def active_results(self, player) -> list:
        if player.is_user:
            return self.user_result_model.query.filter_by(
                user_id=player.user_id,
                ongoing=True,
            ).all()
        if player.is_guest:
            return self.guest_result_model.query.filter_by(
                guest_session_id=player.guest_session_id,
                ongoing=True,
            ).all()
        return []

    def all_results(self, player) -> list:
        if player.is_user:
            return self.user_result_model.query.filter_by(
                user_id=player.user_id,
            ).all()
        if player.is_guest:
            return self.guest_result_model.query.filter_by(
                guest_session_id=player.guest_session_id,
            ).all()
        return []

    def guest_results(self, guest_session_id: int) -> list:
        return self.guest_result_model.query.filter_by(
            guest_session_id=guest_session_id,
        ).all()

    def result_for_question(self, player, source_id: int):
        source_filter = {self.result_source_field: source_id}
        if player.is_user:
            return self.user_result_model.query.filter_by(
                user_id=player.user_id,
                **source_filter,
            ).first()
        if player.is_guest:
            return self.guest_result_model.query.filter_by(
                guest_session_id=player.guest_session_id,
                **source_filter,
            ).first()
        return None

    def new_result(self, player, source_id: int):
        source_values = {self.result_source_field: source_id}
        if player.is_user:
            return self.user_result_model(user_id=player.user_id, **source_values)
        return self.guest_result_model(
            guest_session_id=player.guest_session_id,
            **source_values,
        )

    def result_source_id(self, result) -> int:
        return getattr(result, self.result_source_field)

    def list_questions(self) -> list:
        return self.question_model.query.order_by(self.question_model.id.asc()).all()

    def serialize_question(self, question) -> dict:
        return {
            "id": question.id,
            "name": question.name,
            "hints": [
                self.hint_text(question, difficulty) for difficulty in range(1, 6)
            ],
            "correct_answers": question.correct_answers,
        }

    def _question_values(self, data: dict) -> dict:
        hints = data.get("hints")
        if hints is None:
            hints = [data[f"hint{difficulty}"] for difficulty in range(1, 6)]
        values = {
            "name": data["name"],
            "correct_answers": normalize_answers(data["correct_answers"]),
        }
        for index, hint in enumerate(hints, start=1):
            values[f"hint{index}"] = hint
            source_key = f"hint{index}_source"
            if hasattr(self.question_model, source_key) and source_key in data:
                values[source_key] = data[source_key]
        if data.get("id") is not None:
            values["id"] = int(data["id"])
        return values

    def create_question(self, data: dict):
        return self.question_model(**self._question_values(data))

    def update_question(self, question, data: dict):
        values = self._question_values(data)
        values.pop("id", None)
        for field, value in values.items():
            setattr(question, field, value)
        return question

    def delete_question(self, question) -> None:
        source_id = self.question_id(question)
        self.user_result_model.query.filter_by(
            **{self.result_source_field: source_id}
        ).delete(synchronize_session=False)
        self.guest_result_model.query.filter_by(
            **{self.result_source_field: source_id}
        ).delete(synchronize_session=False)

    def seed_questions(self, records: list[dict]) -> int:
        added = 0
        for record in records:
            source_id = record.get("id")
            if source_id is not None and self.get_question(int(source_id)) is not None:
                continue
            if self.question_model.query.filter_by(name=record["name"]).first():
                continue
            db_question = self.create_question(record)
            db.session.add(db_question)
            added += 1
        return added


class CountriesQuizAdapter(StandardQuizAdapter):
    def __init__(self):
        super().__init__(
            identifier="countries",
            question_model=Destination,
            user_result_model=QuizResult,
            guest_result_model=GuestQuizResult,
            result_source_field="destination_id",
        )


_ADAPTERS: dict[str, QuizAdapter] = {
    "countries": CountriesQuizAdapter(),
}


def get_quiz_adapter(identifier: str) -> QuizAdapter | None:
    """Return the adapter registered under an identifier."""
    return _ADAPTERS.get(identifier)


def get_quiz_adapters() -> list[QuizAdapter]:
    """Return all registered adapters."""
    return list(_ADAPTERS.values())


def get_quiz_adapter_by_media_namespace(namespace: str) -> QuizAdapter | None:
    """Return the adapter that owns a media path namespace."""
    return next(
        (
            adapter
            for adapter in _ADAPTERS.values()
            if adapter.media_namespace == namespace
        ),
        None,
    )


def register_quiz_adapter(adapter: QuizAdapter) -> None:
    """Register an adapter, primarily for application extensions and tests."""
    if adapter.identifier in _ADAPTERS:
        raise ValueError(f"Quiz adapter already registered: '{adapter.identifier}'")
    _ADAPTERS[adapter.identifier] = adapter


def unregister_quiz_adapter(identifier: str) -> None:
    """Remove a non-core adapter registered by an extension or test."""
    if identifier == "countries":
        raise ValueError("The countries adapter cannot be unregistered")
    _ADAPTERS.pop(identifier, None)
