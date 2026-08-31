"""Authentication blueprint — register, login, logout, password reset."""

import re

from flask import Blueprint, current_app, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from .auth import (
    GUEST_TOKEN_COOKIE,
    GUEST_TOKEN_MAX_AGE_SECONDS,
    check_csrf_token,
    create_guest_session,
    delete_guest_session,
    get_current_guest_session,
    get_current_user,
    login_user_session,
    migrate_guest_session_to_user,
    user_response,
)
from .email_service import EmailServiceError, send_password_reset_email
from .models import User, db
from .reset_tokens import consume_token, generate_token, validate_token
from .validation_rules import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH

auth_bp = Blueprint("auth", __name__)

# Basic email format check — intentionally lenient but catches obvious junk
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _guest_payload(guest_session):
    return {
        "guest": {
            "id": guest_session.id,
            "name": f"Guest #{guest_session.id}",
            "isGuest": True,
        }
    }


def _clear_guest_cookie(response):
    response.delete_cookie(GUEST_TOKEN_COOKIE, samesite="Lax")
    return response


@auth_bp.route("/api/register", methods=["POST"])
def register():
    data = request.json or {}
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    if not _EMAIL_RE.match(email):
        return jsonify({"error": "Invalid email format"}), 400

    if len(password) < PASSWORD_MIN_LENGTH:
        return (
            jsonify(
                {"error": f"Password must be at least {PASSWORD_MIN_LENGTH} characters"}
            ),
            400,
        )

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 400

    user = User(email=email, password_hash=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()

    guest_session = get_current_guest_session()
    if guest_session is not None:
        migrate_guest_session_to_user(user, guest_session)

    login_user_session(user)
    response = jsonify(user_response(user))
    if guest_session is not None:
        _clear_guest_cookie(response)
    return response


@auth_bp.route("/api/login", methods=["POST"])
def login():
    data = request.json or {}
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = User.query.filter_by(email=email).first()
    if user is None or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid credentials"}), 401

    guest_session = get_current_guest_session()
    if guest_session is not None:
        migrate_guest_session_to_user(user, guest_session)

    login_user_session(user)
    response = jsonify(user_response(user))
    if guest_session is not None:
        _clear_guest_cookie(response)
    return response


@auth_bp.route("/api/logout", methods=["POST"])
def logout():
    user = get_current_user()
    guest_session = get_current_guest_session()

    if user is not None:
        if not check_csrf_token():
            return jsonify({"error": "Invalid or missing CSRF token"}), 403
        session.clear()
        response = jsonify({"message": "Logged out"})
        if guest_session is not None:
            _clear_guest_cookie(response)
        return response

    if guest_session is not None:
        delete_guest_session(guest_session)
        response = jsonify({"message": "Logged out"})
        return _clear_guest_cookie(response)

    return jsonify({"message": "Logged out"})


@auth_bp.route("/api/me", methods=["GET"])
def me():
    user = get_current_user()
    if user is None:
        return jsonify({"error": "Not authenticated"}), 401
    return jsonify(user_response(user))


@auth_bp.route("/api/guest-session", methods=["GET", "POST"])
def create_or_restore_guest_session():
    """Create or restore a guest session and return guest identity metadata."""
    user = get_current_user()
    if user is not None:
        return jsonify(user_response(user))

    guest_session = get_current_guest_session()

    if request.method == "GET":
        if guest_session is None:
            return jsonify({"error": "No guest session"}), 404
        return jsonify(_guest_payload(guest_session))

    raw_token = None

    if guest_session is None:
        guest_session, raw_token = create_guest_session()

    response = jsonify(_guest_payload(guest_session))
    if raw_token:
        response.set_cookie(
            GUEST_TOKEN_COOKIE,
            raw_token,
            max_age=GUEST_TOKEN_MAX_AGE_SECONDS,
            httponly=True,
            secure=current_app.config.get("SESSION_COOKIE_SECURE", False),
            samesite="Lax",
        )

    return response


@auth_bp.route("/api/forgot-password", methods=["POST"])
def forgot_password():
    data = request.json or {}
    email = (data.get("email") or "").strip().lower()

    if not email:
        return jsonify({"error": "Email is required."}), 400

    if not _EMAIL_RE.match(email):
        return jsonify({"error": "Invalid email format."}), 400

    user = User.query.filter_by(email=email).first()
    if user:
        raw_token = generate_token(user)
        reset_url = f"{request.host_url}reset-password?token={raw_token}"
        try:
            send_password_reset_email(email, reset_url)
        except EmailServiceError as exc:
            current_app.logger.error(
                "Failed to send reset email to %s: %s", email, exc.reason
            )
            return (
                jsonify(
                    {"error": "Failed to send reset email. Please try again later."}
                ),
                500,
            )

    return jsonify(
        {"message": "If that email is registered, a reset link has been sent."}
    )


@auth_bp.route("/api/reset-password/validate", methods=["GET"])
def validate_reset_token_endpoint():
    token = request.args.get("token", "")
    record = validate_token(token)
    if record is not None:
        return jsonify({"valid": True})
    return jsonify({"error": "Invalid or expired reset link."}), 400


@auth_bp.route("/api/reset-password", methods=["POST"])
def reset_password():
    data = request.json or {}
    token = (data.get("token") or "").strip()
    password = data.get("password") or ""

    if not token:
        return jsonify({"error": "Token is required."}), 400

    if not password:
        return jsonify({"error": "Password is required."}), 400

    if len(password) < PASSWORD_MIN_LENGTH or len(password) > PASSWORD_MAX_LENGTH:
        return (
            jsonify(
                {
                    "error": f"Password must be between {PASSWORD_MIN_LENGTH} and {PASSWORD_MAX_LENGTH} characters."
                }
            ),
            400,
        )

    record = validate_token(token)
    if record is None:
        return jsonify({"error": "Invalid or expired reset link."}), 400

    try:
        consume_token(record, password)
    except Exception:
        current_app.logger.exception("Unexpected error during password reset")
        return (
            jsonify({"error": "An unexpected error occurred. Please try again."}),
            500,
        )

    return jsonify({"message": "Your password has been reset. You may now log in."})
