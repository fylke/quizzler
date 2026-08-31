"""Playwright E2E test configuration.

Starts the Flask app on a free port in a background thread before
the test session, and tears it down afterward.
"""

import os
import shutil
import socket
import tempfile
import threading
import time
from pathlib import Path

import pytest
from werkzeug.serving import make_server

# Create the temp DB file BEFORE importing the app so the module-level
# initialization uses the correct database path.
_db_fd, _DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_db_fd)
os.environ["QUIZ_DATABASE_URL"] = f"sqlite:///{_DB_PATH}"

_MEDIA_ROOT = tempfile.mkdtemp(prefix="quizzler-media-")
os.environ["MEDIA_DIR"] = _MEDIA_ROOT

# Seed result images for destination id=1.
_dest_media = Path(_MEDIA_ROOT) / "countries" / "1"
_dest_media.mkdir(parents=True, exist_ok=True)
for i in range(1, 13):
    (_dest_media / f"0{i:02d}.jpg").write_bytes(b"test-image")
(_dest_media / "1a.jpg").write_bytes(b"hint-image-also-shown-in-results")
(_dest_media / "1b.jpg").write_bytes(b"hint-image-also-shown-in-results")
(_dest_media / "README.txt").write_bytes(b"not-an-image")

from backend import app  # noqa: E402
from backend.models import Destination, db  # noqa: E402
from backend.quiz_catalog import (  # noqa: E402
    get_or_create_quiz_identity,
    public_quiz_id,
)

COOKIE_CONSENT_STORAGE_KEY = "quizzler_cookie_consent_acknowledged_v1"


def _get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def app_server():
    """Start the Flask app on a random free port and seed test data."""
    port = _get_free_port()

    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"

    with app.app_context():
        db.drop_all()
        db.create_all()

        # Seed a test destination
        dest = Destination(
            id=1,
            name="Paris",
            hint1="This city is famous for a tower built in 1889.",
            hint2="It's the capital of France.",
            hint3="Known as the City of Light.",
            hint4="Home to the Louvre museum.",
            hint5="Located on the Seine river.",
            correct_answers=["paris", "paris, france"],
        )
        db.session.add(dest)
        db.session.flush()
        get_or_create_quiz_identity("countries", dest.id)
        db.session.commit()

    server = make_server("127.0.0.1", port, app)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()

    # Wait for server to be ready
    for _ in range(50):
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=0.1)
            s.close()
            break
        except OSError:
            time.sleep(0.1)

    yield f"http://127.0.0.1:{port}"

    server.shutdown()
    try:
        os.unlink(_DB_PATH)
    except OSError:
        pass
    shutil.rmtree(_MEDIA_ROOT, ignore_errors=True)


@pytest.fixture(scope="session")
def base_url(app_server):
    """Provide the base_url to pytest-playwright."""
    return app_server


@pytest.fixture(scope="session")
def quiz_guid(app_server):
    """Return the public GUID for the seeded E2E quiz."""
    with app.app_context():
        return public_quiz_id("countries", 1)


@pytest.fixture()
def clean_db(app_server):
    """Reset user data between tests while keeping destinations."""
    with app.app_context():
        from backend.models import GuestQuizResult, GuestSession, QuizResult, User

        GuestQuizResult.query.delete()
        GuestSession.query.delete()
        QuizResult.query.delete()
        User.query.delete()
        db.session.commit()
    yield


@pytest.fixture(autouse=True)
def acknowledge_cookie_banner(context):
    """Pre-acknowledge cookie consent so the banner does not intercept test clicks."""
    context.add_init_script(
        f"""
        (() => {{
            try {{
                window.localStorage.setItem("{COOKIE_CONSENT_STORAGE_KEY}", "true");
            }} catch (_) {{
                // Ignore storage errors in constrained browser contexts.
            }}
        }})();
        """
    )
