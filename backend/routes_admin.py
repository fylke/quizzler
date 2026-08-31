"""Admin blueprint — quiz question CRUD endpoints."""

from flask import Blueprint, jsonify, request

from .admin import validate_destination_payload
from .auth import admin_required, csrf_protected
from .models import QuizIdentity, db
from .quiz_adapters import get_quiz_adapter
from .quiz_catalog import get_or_create_quiz_identity, public_quiz_id
from .quiz_types import get_quiz_type

admin_bp = Blueprint("admin", __name__)


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
    adapter.update_question(question, data)
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
    identity = QuizIdentity.query.filter_by(
        quiz_type=quiz_type,
        source_id=source_id,
    ).first()
    if identity is not None:
        db.session.delete(identity)
    db.session.delete(question)
    db.session.commit()
    return jsonify({"message": "Question deleted"}), 200
