"""Admin blueprint — quiz question CRUD endpoints."""

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

from .admin import validate_destination_payload
from .auth import admin_required, csrf_protected, get_current_user
from .models import (
    GuestSession,
    HintSourceReview,
    QuizIdentity,
    User,
    _utcnow_naive,
    db,
    get_app_setting,
    get_background_settings,
    set_app_setting,
)
from .quiz_adapters import get_quiz_adapter, get_quiz_adapters
from .quiz_catalog import get_or_create_quiz_identity, public_quiz_id
from .quiz_types import get_quiz_type
from .stats import compute_stats

admin_bp = Blueprint("admin", __name__)

_IMAGE_EXTENSIONS = {".gif", ".jpeg", ".jpg", ".png", ".webp"}
_HINT_COUNT = 5
_REVIEW_PAGE_SIZE = 20
_REVIEW_MAX_PAGE_SIZE = 100


@admin_bp.route("/api/admin/stats", methods=["GET"])
@admin_required
def admin_stats():
    """Return aggregate gameplay statistics for the admin dashboard."""
    all_results = [
        (adapter, result)
        for adapter in get_quiz_adapters()
        for result in adapter.user_result_model.query.all()
    ]
    all_results.extend(
        (adapter, result)
        for adapter in get_quiz_adapters()
        for result in adapter.guest_result_model.query.all()
    )
    completed = [result for adapter, result in all_results if not result.ongoing]
    completed_dicts = [
        {
            "hint_difficulty": result.hint_difficulty,
            "remaining_guesses": result.remaining_guesses,
            "destination_id": adapter.result_source_id(result),
        }
        for adapter, result in all_results
        if not result.ongoing
    ]
    stats = compute_stats(completed_dicts)
    stats.update(
        {
            "registeredUsers": User.query.count(),
            "guestSessions": GuestSession.query.count(),
            "quizzesStarted": len(all_results),
            "quizzesOngoing": len(all_results) - len(completed),
        }
    )
    return jsonify(stats)


def _standard_adapter(quiz_type_identifier):
    quiz_type = get_quiz_type(quiz_type_identifier)
    adapter = get_quiz_adapter(quiz_type.adapter) if quiz_type is not None else None
    if adapter is None or not all(
        hasattr(adapter, method)
        for method in (
            "list_questions",
            "serialize_question",
            "create_question",
            "update_question",
            "delete_question",
        )
    ):
        return None
    return adapter


def _hint_source_values(question):
    return [
        getattr(question, f"hint{difficulty}_source", "") or ""
        for difficulty in range(1, _HINT_COUNT + 1)
    ]


def _review_item_payload(adapter, question, difficulty, review=None):
    source = _hint_source_values(question)[difficulty - 1]
    reviewer = review.reviewed_by if review is not None else None
    return {
        "quiz_type": adapter.identifier,
        "source_id": adapter.question_id(question),
        "name": adapter.answer_name(question),
        "hint_difficulty": difficulty,
        "hint": adapter.hint_text(question, difficulty),
        "source": source,
        "reviewed": bool(review and review.reviewed),
        "reviewed_at": (
            review.reviewed_at.isoformat() if review and review.reviewed_at else None
        ),
        "reviewed_by": reviewer.email if reviewer else None,
    }


def _clear_changed_source_reviews(quiz_type, source_id, old_sources, new_sources):
    changed_difficulties = [
        difficulty
        for difficulty, (old_source, new_source) in enumerate(
            zip(old_sources, new_sources), start=1
        )
        if (old_source or "") != (new_source or "")
    ]
    if changed_difficulties:
        HintSourceReview.query.filter(
            HintSourceReview.quiz_type == quiz_type,
            HintSourceReview.source_id == source_id,
            HintSourceReview.hint_difficulty.in_(changed_difficulties),
        ).delete(synchronize_session=False)


@admin_bp.route("/api/admin/quiz-types/<quiz_type>/questions", methods=["GET"])
@admin_required
def list_questions(quiz_type):
    adapter = _standard_adapter(quiz_type)
    if adapter is None:
        return jsonify({"error": "Quiz type not found"}), 404
    questions = [
        {"id": question.id, "name": question.name}
        for question in adapter.list_questions()
    ]
    return jsonify({"questions": questions, "count": len(questions)})


@admin_bp.route(
    "/api/admin/quiz-types/<quiz_type>/questions/<int:source_id>",
    methods=["GET"],
)
@admin_required
def get_question(quiz_type, source_id):
    adapter = _standard_adapter(quiz_type)
    question = adapter.get_question(source_id) if adapter is not None else None
    if question is None:
        return jsonify({"error": "Question not found"}), 404
    return jsonify(adapter.serialize_question(question))


@admin_bp.route("/api/admin/quiz-types/<quiz_type>/hint-sources", methods=["GET"])
@admin_required
def list_hint_source_reviews(quiz_type):
    adapter = _standard_adapter(quiz_type)
    if adapter is None:
        return jsonify({"error": "Quiz type not found"}), 404

    status = request.args.get("status", "unreviewed")
    if status not in {"unreviewed", "reviewed", "all"}:
        return jsonify({"error": "status must be unreviewed, reviewed, or all"}), 400
    try:
        offset = max(int(request.args.get("offset", 0)), 0)
        limit = int(request.args.get("limit", _REVIEW_PAGE_SIZE))
    except (TypeError, ValueError):
        return jsonify({"error": "offset and limit must be integers"}), 400
    if not 1 <= limit <= _REVIEW_MAX_PAGE_SIZE:
        return (
            jsonify({"error": f"limit must be between 1 and {_REVIEW_MAX_PAGE_SIZE}"}),
            400,
        )

    review_rows = {
        (row.source_id, row.hint_difficulty): row
        for row in HintSourceReview.query.filter_by(quiz_type=quiz_type).all()
    }
    entries = []
    for question in adapter.list_questions():
        question_reviews = {
            difficulty: review_rows.get((adapter.question_id(question), difficulty))
            for difficulty in range(1, _HINT_COUNT + 1)
        }
        for difficulty, source in enumerate(_hint_source_values(question), start=1):
            if not source.strip():
                continue
            review = question_reviews[difficulty]
            is_reviewed = bool(review and review.reviewed)
            if status == "unreviewed" and is_reviewed:
                continue
            if status == "reviewed" and not is_reviewed:
                continue
            entries.append(_review_item_payload(adapter, question, difficulty, review))

    page = entries[offset : offset + limit]
    return jsonify(
        {
            "items": page,
            "count": len(entries),
            "offset": offset,
            "limit": limit,
            "has_more": offset + limit < len(entries),
        }
    )


@admin_bp.route(
    "/api/admin/quiz-types/<quiz_type>/hint-sources/<int:source_id>/<int:difficulty>",
    methods=["PATCH"],
)
@admin_required
@csrf_protected
def update_hint_source_review(quiz_type, source_id, difficulty):
    adapter = _standard_adapter(quiz_type)
    if adapter is None:
        return jsonify({"error": "Quiz type not found"}), 404
    if not 1 <= difficulty <= _HINT_COUNT:
        return jsonify({"error": "Hint difficulty must be between 1 and 5"}), 400

    question = adapter.get_question(source_id)
    if question is None:
        return jsonify({"error": "Question not found"}), 404
    source = _hint_source_values(question)[difficulty - 1]
    if not source.strip():
        return jsonify({"error": "Hint source is empty"}), 400

    data = request.json or {}
    reviewed = data.get("reviewed")
    if not isinstance(reviewed, bool):
        return jsonify({"error": "reviewed must be a boolean"}), 400

    review = HintSourceReview.query.filter_by(
        quiz_type=quiz_type,
        source_id=source_id,
        hint_difficulty=difficulty,
    ).first()
    if review is None:
        review = HintSourceReview(
            quiz_type=quiz_type,
            source_id=source_id,
            hint_difficulty=difficulty,
        )
        db.session.add(review)

    user = get_current_user()
    review.reviewed = reviewed
    review.reviewed_at = _utcnow_naive() if reviewed else None
    review.reviewed_by_user_id = user.id if reviewed else None
    db.session.commit()
    return jsonify(_review_item_payload(adapter, question, difficulty, review))


@admin_bp.route("/api/admin/quiz-types/<quiz_type>/questions", methods=["POST"])
@admin_required
@csrf_protected
def create_question(quiz_type):
    adapter = _standard_adapter(quiz_type)
    if adapter is None:
        return jsonify({"error": "Quiz type not found"}), 404
    data = request.json or {}
    is_valid, errors = validate_destination_payload(data)
    if not is_valid:
        return jsonify({"error": "Validation failed", "details": errors}), 400
    if adapter.question_model.query.filter_by(name=data["name"]).first():
        return jsonify({"error": "A question with this name already exists"}), 409

    question = adapter.create_question(data)
    db.session.add(question)
    db.session.flush()
    identity = get_or_create_quiz_identity(quiz_type, adapter.question_id(question))
    db.session.commit()
    return (
        jsonify(
            {
                "id": adapter.question_id(question),
                "guid": public_quiz_id(identity.quiz_type, identity.source_id),
            }
        ),
        201,
    )


@admin_bp.route(
    "/api/admin/quiz-types/<quiz_type>/questions/<int:source_id>/images",
    methods=["POST"],
)
@admin_required
@csrf_protected
def upload_question_images(quiz_type, source_id):
    adapter = _standard_adapter(quiz_type)
    question = adapter.get_question(source_id) if adapter is not None else None
    if question is None:
        return jsonify({"error": "Question not found"}), 404

    files = [file for file in request.files.getlist("images") if file.filename]
    if not 2 <= len(files) <= 10:
        return jsonify({"error": "Between 2 and 10 images are required"}), 400

    validated_files = []
    for image in files:
        filename = secure_filename(image.filename or "")
        extension = Path(filename).suffix.lower()
        if (
            not filename
            or extension not in _IMAGE_EXTENSIONS
            or not image.mimetype.startswith("image/")
        ):
            return jsonify({"error": "Only image files are allowed"}), 400
        validated_files.append((image, extension))

    media_dir = (
        Path(current_app.config["MEDIA_DIR"]) / adapter.media_namespace / str(source_id)
    )
    media_dir.mkdir(parents=True, exist_ok=True)
    existing_numbers = [
        int(path.stem[1:])
        for path in media_dir.iterdir()
        if path.is_file() and path.stem.startswith("0") and path.stem[1:].isdigit()
    ]
    next_number = max(existing_numbers, default=0) + 1
    for image, extension in validated_files:
        image.save(media_dir / f"0{next_number:02d}{extension}")
        next_number += 1

    return jsonify({"message": "Images uploaded", "count": len(files)}), 201


@admin_bp.route(
    "/api/admin/quiz-types/<quiz_type>/questions/<int:source_id>",
    methods=["PUT"],
)
@admin_required
@csrf_protected
def update_question(quiz_type, source_id):
    adapter = _standard_adapter(quiz_type)
    question = adapter.get_question(source_id) if adapter is not None else None
    if question is None:
        return jsonify({"error": "Question not found"}), 404
    data = request.json or {}
    is_valid, errors = validate_destination_payload(data)
    if not is_valid:
        return jsonify({"error": "Validation failed", "details": errors}), 400
    old_sources = _hint_source_values(question)
    adapter.update_question(question, data)
    new_sources = _hint_source_values(question)
    _clear_changed_source_reviews(quiz_type, source_id, old_sources, new_sources)
    db.session.commit()
    return jsonify(adapter.serialize_question(question))


@admin_bp.route(
    "/api/admin/quiz-types/<quiz_type>/questions/<int:source_id>",
    methods=["DELETE"],
)
@admin_required
@csrf_protected
def delete_question(quiz_type, source_id):
    adapter = _standard_adapter(quiz_type)
    question = adapter.get_question(source_id) if adapter is not None else None
    if question is None:
        return jsonify({"error": "Question not found"}), 404
    adapter.delete_question(question)
    HintSourceReview.query.filter_by(
        quiz_type=quiz_type,
        source_id=source_id,
    ).delete(synchronize_session=False)
    identity = QuizIdentity.query.filter_by(
        quiz_type=quiz_type,
        source_id=source_id,
    ).first()
    if identity is not None:
        db.session.delete(identity)
    db.session.delete(question)
    db.session.commit()
    return jsonify({"message": "Question deleted"}), 200


def _remove_background_file(key: str) -> None:
    current_val = get_app_setting(key)
    if current_val and current_val.startswith("/media/"):
        rel_path = current_val.removeprefix("/media/")
        file_path = Path(current_app.config["MEDIA_DIR"]) / rel_path
        if file_path.is_file():
            try:
                file_path.unlink()
            except OSError:
                pass


@admin_bp.route("/api/admin/settings/background", methods=["GET"])
@admin_required
def get_admin_background_settings():
    return jsonify(get_background_settings())


@admin_bp.route("/api/admin/settings/background", methods=["POST"])
@admin_required
@csrf_protected
def update_background_settings():
    portrait_file = request.files.get("portrait")
    landscape_file = request.files.get("landscape")

    if not portrait_file and not landscape_file:
        return (
            jsonify(
                {
                    "error": (
                        "At least one background image (portrait or landscape)"
                        " must be provided"
                    )
                }
            ),
            400,
        )

    files_to_process = []
    if portrait_file and portrait_file.filename:
        filename = secure_filename(portrait_file.filename)
        extension = Path(filename).suffix.lower()
        if (
            not filename
            or extension not in _IMAGE_EXTENSIONS
            or not portrait_file.mimetype.startswith("image/")
        ):
            return jsonify({"error": "Only image files are allowed"}), 400
        files_to_process.append(
            ("portrait", "background_portrait", portrait_file, extension)
        )

    if landscape_file and landscape_file.filename:
        filename = secure_filename(landscape_file.filename)
        extension = Path(filename).suffix.lower()
        if (
            not filename
            or extension not in _IMAGE_EXTENSIONS
            or not landscape_file.mimetype.startswith("image/")
        ):
            return jsonify({"error": "Only image files are allowed"}), 400
        files_to_process.append(
            ("landscape", "background_landscape", landscape_file, extension)
        )

    if not files_to_process:
        return (
            jsonify(
                {
                    "error": (
                        "At least one background image (portrait or landscape)"
                        " must be provided"
                    )
                }
            ),
            400,
        )

    media_dir = Path(current_app.config["MEDIA_DIR"]) / "backgrounds"
    media_dir.mkdir(parents=True, exist_ok=True)

    timestamp = int(_utcnow_naive().timestamp())
    for orientation, setting_key, file_obj, extension in files_to_process:
        _remove_background_file(setting_key)
        saved_filename = f"{orientation}_{timestamp}{extension}"
        file_obj.save(media_dir / saved_filename)
        set_app_setting(setting_key, f"/media/backgrounds/{saved_filename}")

    db.session.commit()
    result = get_background_settings()
    result["message"] = "Background settings updated"
    return jsonify(result), 200


@admin_bp.route("/api/admin/settings/background/<orientation>", methods=["DELETE"])
@admin_required
@csrf_protected
def delete_background_setting(orientation):
    orientation = orientation.lower()
    if orientation not in {"portrait", "landscape", "all"}:
        return (
            jsonify(
                {"error": "Invalid orientation. Must be portrait, landscape, or all"}
            ),
            400,
        )

    if orientation in {"portrait", "all"}:
        _remove_background_file("background_portrait")
        set_app_setting("background_portrait", None)

    if orientation in {"landscape", "all"}:
        _remove_background_file("background_landscape")
        set_app_setting("background_landscape", None)

    db.session.commit()
    result = get_background_settings()
    result["message"] = f"Background {orientation} removed successfully"
    return jsonify(result), 200
