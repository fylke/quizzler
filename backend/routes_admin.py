"""Admin blueprint — destination CRUD endpoints."""

from flask import Blueprint, jsonify, request

from .admin import normalize_answers, validate_destination_payload
from .auth import admin_required, csrf_protected
from .models import Destination, QuizIdentity, db
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
    return jsonify({
        "id": adapter.question_id(question),
        "guid": public_quiz_id(identity.quiz_type, identity.source_id),
    }), 201


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


@admin_bp.route("/api/admin/destinations", methods=["GET"])
@admin_required
def list_destinations():
    """Return all destinations ordered by ID ascending."""
    destinations = Destination.query.order_by(Destination.id.asc()).all()
    result = [{"id": d.id, "name": d.name} for d in destinations]
    return jsonify({"destinations": result, "count": len(result)})


@admin_bp.route("/api/admin/destinations/<int:destination_id>", methods=["GET"])
@admin_required
def get_destination(destination_id):
    """Return full destination data by ID."""
    destination = db.session.get(Destination, destination_id)
    if not destination:
        return jsonify({"error": "Destination not found"}), 404
    return jsonify(
        {
            "id": destination.id,
            "name": destination.name,
            "hints": [
                destination.hint1,
                destination.hint2,
                destination.hint3,
                destination.hint4,
                destination.hint5,
            ],
            "correct_answers": destination.correct_answers,
        }
    )


@admin_bp.route("/api/admin/destinations", methods=["POST"])
@admin_required
@csrf_protected
def create_destination():
    """Create a new destination."""
    data = request.json or {}

    is_valid, errors = validate_destination_payload(data)
    if not is_valid:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    # Check for duplicate name (case-sensitive exact match)
    existing = Destination.query.filter_by(name=data["name"]).first()
    if existing:
        return jsonify({"error": "A destination with this name already exists"}), 409

    # Store hints as hint1–hint5 columns
    hints = data["hints"]
    normalized = normalize_answers(data["correct_answers"])

    destination = Destination(
        name=data["name"],
        hint1=hints[0],
        hint2=hints[1],
        hint3=hints[2],
        hint4=hints[3],
        hint5=hints[4],
        correct_answers=normalized,
    )
    db.session.add(destination)
    db.session.flush()
    identity = get_or_create_quiz_identity("countries", destination.id)
    db.session.commit()

    return jsonify({
        "id": destination.id,
        "guid": public_quiz_id(identity.quiz_type, identity.source_id),
    }), 201


@admin_bp.route("/api/admin/destinations/<int:destination_id>", methods=["DELETE"])
@admin_required
@csrf_protected
def delete_destination(destination_id):
    """Delete a destination and cascade to associated quiz results."""
    destination = db.session.get(Destination, destination_id)
    if not destination:
        return jsonify({"error": "Destination not found"}), 404
    identity = QuizIdentity.query.filter_by(
        quiz_type="countries",
        source_id=destination_id,
    ).first()
    if identity is not None:
        db.session.delete(identity)
    db.session.delete(destination)
    db.session.commit()
    return jsonify({"message": "Destination deleted"}), 200


@admin_bp.route("/api/admin/destinations/<int:destination_id>", methods=["PUT"])
@admin_required
@csrf_protected
def update_destination(destination_id):
    """Update (replace) all fields of an existing destination."""
    destination = db.session.get(Destination, destination_id)
    if not destination:
        return jsonify({"error": "Destination not found"}), 404

    data = request.json or {}

    is_valid, errors = validate_destination_payload(data)
    if not is_valid:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    # Replace all fields with submitted values
    hints = data["hints"]
    normalized = normalize_answers(data["correct_answers"])

    destination.name = data["name"]
    destination.hint1 = hints[0]
    destination.hint2 = hints[1]
    destination.hint3 = hints[2]
    destination.hint4 = hints[3]
    destination.hint5 = hints[4]
    destination.correct_answers = normalized

    db.session.commit()

    return jsonify(
        {
            "id": destination.id,
            "name": destination.name,
            "hints": [
                destination.hint1,
                destination.hint2,
                destination.hint3,
                destination.hint4,
                destination.hint5,
            ],
            "correct_answers": destination.correct_answers,
        }
    )
