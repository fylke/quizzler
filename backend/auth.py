"""Authentication and CSRF utilities shared across blueprints."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import wraps

from flask import jsonify, request, session

from .models import GuestSession, User, db

GUEST_TOKEN_COOKIE = "guest_token"
GUEST_TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 365 * 20


@dataclass(frozen=True)
class PlayerContext:
    """Represents the active player for a request (user or guest)."""

    kind: str
    user: User | None = None
    guest: GuestSession | None = None

    @property
    def is_user(self) -> bool:
        return self.kind == "user" and self.user is not None

    @property
    def is_guest(self) -> bool:
        return self.kind == "guest" and self.guest is not None

    @property
    def user_id(self) -> int | None:
        return self.user.id if self.user is not None else None

    @property
    def guest_session_id(self) -> int | None:
        return self.guest.id if self.guest is not None else None


def generate_csrf_token():
    """Generate a new CSRF token and store it in the session."""
    token = secrets.token_hex(32)
    session["csrf_token"] = token
    return token


def _hash_guest_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def create_guest_session() -> tuple[GuestSession, str]:
    """Create a new guest session and return (record, raw_token)."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_guest_token(raw_token)
    guest_session = GuestSession(token_hash=token_hash)
    db.session.add(guest_session)
    db.session.commit()
    return guest_session, raw_token


def delete_guest_session(guest_session: GuestSession) -> None:
    """Delete a guest session and all associated server-side progress."""
    db.session.delete(guest_session)
    db.session.commit()


def get_current_guest_session() -> GuestSession | None:
    """Resolve guest session from the signed guest token cookie."""
    raw_token = request.cookies.get(GUEST_TOKEN_COOKIE, "")
    if not raw_token:
        return None

    token_hash = _hash_guest_token(raw_token)
    return GuestSession.query.filter_by(token_hash=token_hash).first()


def migrate_guest_session_to_user(user: User, guest_session: GuestSession) -> None:
    """Move guest quiz progress into the authenticated user's account."""
    from .quiz_adapters import get_quiz_adapters

    adapters = get_quiz_adapters()
    guest_results_by_adapter = [
        (adapter, adapter.guest_results(guest_session.id)) for adapter in adapters
    ]
    guest_results = [
        result
        for _, adapter_results in guest_results_by_adapter
        for result in adapter_results
    ]
    if not guest_results:
        db.session.delete(guest_session)
        db.session.commit()
        return

    user_player = PlayerContext(kind="user", user=user)
    if any(result.ongoing for result in guest_results):
        for adapter in adapters:
            for active_result in adapter.active_results(user_player):
                active_result.ongoing = False

    for adapter, adapter_results in guest_results_by_adapter:
        for guest_result in adapter_results:
            source_id = adapter.result_source_id(guest_result)
            user_result = adapter.result_for_question(user_player, source_id)
            if user_result is None:
                user_result = adapter.new_result(user_player, source_id)

            user_result.hint_difficulty = guest_result.hint_difficulty
            user_result.remaining_guesses = guest_result.remaining_guesses
            user_result.ongoing = guest_result.ongoing
            db.session.add(user_result)
            db.session.delete(guest_result)

    db.session.delete(guest_session)
    db.session.commit()


def get_current_player() -> PlayerContext | None:
    """Resolve request actor as authenticated user or guest session."""
    user = get_current_user()
    if user is not None:
        return PlayerContext(kind="user", user=user)

    guest_session = get_current_guest_session()
    if guest_session is not None:
        return PlayerContext(kind="guest", guest=guest_session)

    return None


def check_csrf_token():
    """Validate the CSRF token from the X-CSRF-Token header against the session."""
    token = request.headers.get("X-CSRF-Token", "")
    expected = session.get("csrf_token", "")
    if not expected or not secrets.compare_digest(token, expected):
        return False
    return True


def csrf_protected(fn):
    """Decorator that rejects requests with a missing or invalid CSRF token."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not check_csrf_token():
            return jsonify({"error": "Invalid or missing CSRF token"}), 403
        return fn(*args, **kwargs)

    return wrapper


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = db.session.get(User, user_id)
    if user is None:
        return None
    if user.password_changed_at is not None:
        logged_in_at_str = session.get("logged_in_at")
        if not logged_in_at_str:
            return None
        logged_in_at = datetime.fromisoformat(logged_in_at_str)
        # password_changed_at is naive UTC from the DB — make it aware for comparison
        changed_at = user.password_changed_at.replace(tzinfo=UTC)
        if logged_in_at < changed_at:
            return None
    return user


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if get_current_user() is None:
            return jsonify({"error": "Authentication required"}), 401
        return fn(*args, **kwargs)

    return wrapper


def player_required(fn):
    """Decorator requiring either authenticated user or active guest session."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if get_current_player() is None:
            return jsonify({"error": "Authentication required"}), 401
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    """Decorator that requires the user to be authenticated AND an admin."""

    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user.is_admin:
            return jsonify({"error": "Admin access required"}), 403
        return fn(*args, **kwargs)

    return wrapper


def user_response(user):
    """Build the standard user JSON response dict (includes a fresh CSRF token)."""
    csrf_token = generate_csrf_token()
    return {
        "id": user.id,
        "email": user.email,
        "isAdmin": user.is_admin,
        "csrfToken": csrf_token,
    }


def login_user_session(user):
    """Set session fields for a logged-in user."""
    session["user_id"] = user.id
    session["logged_in_at"] = datetime.now(UTC).isoformat()
