import logging
import os
import re
import sys
from pathlib import Path

import sqlalchemy.exc
from flask import Flask, jsonify, render_template, request, send_from_directory, session
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from .auth import (  # noqa: F401 — re-exported for backward compatibility
    admin_required,
    csrf_protected,
    get_current_player,
    get_current_user,
    login_required,
    player_required,
)
from .models import Destination, GuestQuizResult, QuizResult, User, db
from .quiz_types import IDENTIFIER_PATTERN, get_registry, validate_registry
from .routes_admin import admin_bp
from .routes_auth import auth_bp
from .routes_quiz import quiz_bp
from .stats import compute_stats
from .validation_rules import as_dict as validation_rules_dict

# Re-export auth utilities so existing imports like `from backend import admin_required` still work.

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
STATIC_DIR = os.path.join(PROJECT_ROOT, "frontend")

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")

# Media directory for quiz images (convention: media/<dest_id>/<hint_level>a.jpg)
MEDIA_DIR = os.environ.get("MEDIA_DIR", os.path.join(PROJECT_ROOT, "media"))
app.config["MEDIA_DIR"] = MEDIA_DIR
logging.getLogger(__name__).debug("Configured MEDIA_DIR=%s", app.config["MEDIA_DIR"])

# Restrict CORS to the app's own origin in production; allow all in dev.
_env = os.environ.get('FLASK_ENV', 'development')
_cors_origins_raw = os.environ.get('CORS_ALLOWED_ORIGINS', '*').strip()
if _env == 'production' and (_cors_origins_raw == '*' or not _cors_origins_raw):
    raise RuntimeError(
        "CORS_ALLOWED_ORIGINS must be explicitly set in production and cannot be '*'."
    )
_cors_origins = [o.strip() for o in _cors_origins_raw.split(',') if o.strip()]
if not _cors_origins:
    _cors_origins = ['*']
CORS(app, origins=_cors_origins, supports_credentials=True)
_secret_key = os.environ.get('SECRET_KEY')
if not _secret_key:
    import logging as _logging

    if _env == 'production':
        raise RuntimeError(
            "SECRET_KEY environment variable must be set in production. "
            "Refusing to start with an insecure default."
        )
    logging.getLogger(__name__).warning(
        "SECRET_KEY is not set — using an insecure default. "
        "Do NOT run like this in production."
    )
    _secret_key = "change-me-in-production"

app.secret_key = _secret_key

# Secure session cookie configuration
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (
    os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
)

_csp = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "object-src 'none'",
    "base-uri 'self'",
    "frame-ancestors 'none'",
])


@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    response.headers['Content-Security-Policy'] = _csp
    if app.config.get('SESSION_COOKIE_SECURE'):
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# Rate limiter (uses in-memory storage by default; set RATELIMIT_STORAGE_URI for Redis)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "memory://"),
)


@limiter.request_filter
def _disable_limiter_in_testing():
    """Skip rate limiting when app is in testing mode."""
    return app.testing


# ---------------------------------------------------------------------------
# Database configuration
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

_HINT_IMAGE_PATH_RE = re.compile(
    r"^countries/(?P<destination_id>\d+)/(?P<hint_difficulty>[1-5])[ab](?:\.jpg|_small\.webp)$",
    re.IGNORECASE,
)
_ZERO_PREFIX_MEDIA_PATH_RE = re.compile(
    r"^countries/(?P<destination_id>\d+)/(?P<filename>0[^/]+)$",
    re.IGNORECASE,
)
MEDIA_ACCESS_SESSION_KEY = "media_access_state"


def _active_quiz_result_for_player(player):
    if player.is_user:
        return QuizResult.query.filter_by(user_id=player.user_id, ongoing=True).first()
    if player.is_guest:
        return GuestQuizResult.query.filter_by(
            guest_session_id=player.guest_session_id,
            ongoing=True,
        ).first()
    return None


def _media_access_state_from_session() -> dict | None:
    state = session.get(MEDIA_ACCESS_SESSION_KEY)
    if not isinstance(state, dict):
        return None

    required_keys = {"destination_id", "hint_difficulty"}
    if not required_keys.issubset(state.keys()):
        return None

    try:
        destination_id = int(state["destination_id"])
        hint_difficulty = int(state["hint_difficulty"])
    except (TypeError, ValueError):
        return None

    if hint_difficulty < 1:
        return None

    return {
        "destination_id": destination_id,
        "hint_difficulty": hint_difficulty,
    }


def _can_access_media_path(filename: str) -> bool:
    """Authorize direct media URL access for hint images based on server-side state."""
    match = _HINT_IMAGE_PATH_RE.fullmatch(filename)
    if match is None:
        zero_prefixed_match = _ZERO_PREFIX_MEDIA_PATH_RE.fullmatch(filename)
        if zero_prefixed_match is None:
            return True

        player = get_current_player()
        if player is None:
            return False

        requested_destination_id = int(zero_prefixed_match.group("destination_id"))
        quiz_result = _active_quiz_result_for_player(player)
        if quiz_result is None:
            return True

        if requested_destination_id != quiz_result.destination_id:
            return True

        # During an active hint flow, keep 0-prefixed result-gallery assets restricted.
        return False

    player = get_current_player()
    if player is None:
        return False

    requested_destination_id = int(match.group("destination_id"))
    requested_hint_difficulty = int(match.group("hint_difficulty"))

    session_state = _media_access_state_from_session()
    if session_state is not None:
        if session_state["destination_id"] != requested_destination_id:
            return False
        # Unlocked hints are the current live hint and all previously revealed harder hints.
        return requested_hint_difficulty >= session_state["hint_difficulty"]

    quiz_result = _active_quiz_result_for_player(player)
    if quiz_result is None:
        return False

    if requested_destination_id != quiz_result.destination_id:
        return False

    # Unlocked hints are the current live hint and all previously revealed harder hints.
    return requested_hint_difficulty >= quiz_result.hint_difficulty


def resolve_database_uri(quiz_db_url=None, database_url=None, default_path=None):
    """Resolve the database URI using the precedence chain.

    Priority:
      1. quiz_db_url (QUIZ_DATABASE_URL) if non-empty
      2. database_url (DATABASE_URL) if non-empty
      3. SQLite default at default_path

    Returns the resolved URI string.
    """
    if default_path is None:
        default_path = os.path.join(PROJECT_ROOT, "database", "quiz_data.db")
    env_url = quiz_db_url or database_url
    return env_url or f"sqlite:///{default_path}"


default_db_path = os.path.join(PROJECT_ROOT, "database", "quiz_data.db")
_env_db_url = os.environ.get("QUIZ_DATABASE_URL") or os.environ.get("DATABASE_URL")
db_url = _env_db_url or f"sqlite:///{default_db_path}"

if db_url.startswith("sqlite:///") and db_url != "sqlite:///:memory:":
    db_path = db_url.split("sqlite:///")[1]
    db_path = os.path.abspath(db_path)
    db_dir = os.path.dirname(db_path)
    if db_dir:
        # Ensure SQLite parent directory exists for both default and env-provided paths.
        os.makedirs(db_dir, exist_ok=True)
    db_url = f"sqlite:///{db_path}"

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

if db_url.startswith("postgresql"):
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"connect_args": {"connect_timeout": 5}}

db.init_app(app)

with app.app_context():
    try:
        db.create_all()
    except sqlalchemy.exc.OperationalError as e:
        logger.error("Database connection failed: %s", e)
        sys.exit(1)

# Validate quiz type registry at startup (fail fast)
_registry_errors = validate_registry(get_registry())
if _registry_errors:
    for _err in _registry_errors:
        logger.error("Quiz type registry error: %s", _err)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Register blueprints
# ---------------------------------------------------------------------------

app.register_blueprint(auth_bp)
app.register_blueprint(quiz_bp)
app.register_blueprint(admin_bp)

# Apply rate limits to auth blueprint routes after registration
limiter.limit("5 per minute")(app.view_functions["auth.login"])
limiter.limit("3 per hour", key_func=lambda: (request.json or {}).get("email", ""))(
    app.view_functions["auth.forgot_password"]
)
limiter.limit("10 per hour")(app.view_functions["auth.forgot_password"])

# ---------------------------------------------------------------------------
# Misc routes (health, static files, stats, quiz types, rules)
# ---------------------------------------------------------------------------


@app.route("/health", methods=["GET"])
def health_check():
    """Public health check endpoint for container orchestration."""
    try:
        db.session.execute(db.text("SELECT 1"))
        return jsonify({"status": "healthy"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 503


@app.route("/api/validation-rules", methods=["GET"])
def get_validation_rules():
    """Return validation constraints for use by the frontend."""
    return jsonify(validation_rules_dict())


@app.route("/api/status", methods=["GET"])
@player_required
def get_status():
    """Return quiz stats for the current user."""
    player = get_current_player()
    if player.is_user:
        results = QuizResult.query.filter_by(user_id=player.user_id).all()
    else:
        results = GuestQuizResult.query.filter_by(
            guest_session_id=player.guest_session_id
        ).all()

    completed = [r for r in results if not r.ongoing]
    total_points = sum(
        r.hint_difficulty * r.remaining_guesses
        for r in completed
        if r.remaining_guesses > 0
    )
    return jsonify(
        {
            "quizzesCompleted": len(completed),
            "totalPoints": total_points,
            "quizzesOngoing": len([r for r in results if r.ongoing]),
        }
    )


@app.route("/api/quiz-types", methods=["GET"])
@player_required
def list_quiz_types():
    """Return the list of registered quiz types."""
    registry = get_registry()
    return jsonify(
        [
            {"identifier": qt.identifier, "displayName": qt.display_name}
            for qt in registry
        ]
    )


@app.route("/api/rules/<quiz_type>", methods=["GET"])
@player_required
def get_rules(quiz_type):
    """Return raw markdown rules content for a given quiz type."""
    if "/" in quiz_type or "\\" in quiz_type:
        return jsonify({"error": "Invalid quiz type identifier"}), 400

    if not IDENTIFIER_PATTERN.match(quiz_type):
        return jsonify({"error": "Invalid quiz type identifier"}), 400

    rules_path = Path(__file__).parent / "assets" / "rules" / f"{quiz_type}.md"
    if not rules_path.is_file():
        return jsonify({"error": f"Rules not found for quiz type '{quiz_type}'"}), 404

    content = rules_path.read_text(encoding="utf-8")
    return jsonify({"content": content})


@app.route("/api/stats", methods=["GET"])
@player_required
def get_stats():
    """Return detailed cumulative statistics for the current user."""
    player = get_current_player()
    if player.is_user:
        results = QuizResult.query.filter_by(user_id=player.user_id).all()
    else:
        results = GuestQuizResult.query.filter_by(
            guest_session_id=player.guest_session_id
        ).all()

    completed = [r for r in results if not r.ongoing]
    ongoing = [r for r in results if r.ongoing]

    completed_dicts = [
        {
            "hint_difficulty": r.hint_difficulty,
            "remaining_guesses": r.remaining_guesses,
            "destination_id": r.destination_id,
        }
        for r in completed
    ]

    stats = compute_stats(completed_dicts)
    stats["quizzesOngoing"] = len(ongoing)
    return jsonify(stats)


@app.route("/reset-password")
def reset_password_page():
    """Serve the password reset form page."""
    return send_from_directory(STATIC_DIR, "reset_password.html")


@app.route("/")
def index():
    """Serve the main page."""
    return render_template("index.html")


@app.route("/media/<path:filename>")
def serve_media(filename):
    """Serve quiz images from the media directory."""
    if not _can_access_media_path(filename):
        return jsonify({"error": "Media access denied"}), 403

    media_dir = os.environ.get("MEDIA_DIR") or app.config["MEDIA_DIR"]
    return send_from_directory(media_dir, filename)


if __name__ == "__main__":
    app.run(debug=False, port=5000, host="0.0.0.0")
