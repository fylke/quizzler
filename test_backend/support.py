from werkzeug.security import generate_password_hash

from backend import app
from backend.models import Destination, User, db
from backend.quiz_catalog import get_or_create_quiz_identity, public_quiz_id


def configure_test_app():
    app.testing = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    return app.test_client()


def reset_database():
    with app.app_context():
        db.drop_all()
        db.create_all()


def cleanup_database():
    with app.app_context():
        db.session.remove()
        db.drop_all()


def add_user(email, password="password123", *, is_admin=False):
    user = User(
        email=email,
        password_hash=generate_password_hash(password),
        is_admin=is_admin,
    )
    db.session.add(user)
    return user


def add_destination(
    *,
    destination_id=None,
    name="paris",
    hints=None,
    correct_answers=None,
):
    values = {
        "name": name,
        "hint1": "Hint 1",
        "hint2": "Hint 2",
        "hint3": "Hint 3",
        "hint4": "Hint 4",
        "hint5": "Hint 5",
        "correct_answers": correct_answers or [name.lower()],
    }
    if destination_id is not None:
        values["id"] = destination_id
    if hints is not None:
        values.update({f"hint{index}": hint for index, hint in enumerate(hints, 1)})

    destination = Destination(**values)
    db.session.add(destination)
    return destination


def add_destination_from_sample(sample):
    return add_destination(
        destination_id=sample["id"],
        name=sample["destination"],
        hints=[sample["hints"][str(index)] for index in range(1, 6)],
        correct_answers=sample["correct_answers"],
    )


def ensure_public_quiz_id(quiz_type, source_id):
    identity = get_or_create_quiz_identity(quiz_type, source_id)
    return public_quiz_id(identity.quiz_type, identity.source_id)


def login_client_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
