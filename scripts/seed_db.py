"""Seed the database with travel destinations from an external JSON file.

Usage:
    uv run python -m scripts.seed_db

Or inside the container:
    podman exec quizzler uv run --no-project python -m scripts.seed_db

The seed data is loaded from data/countries.json (gitignored).
See data/countries.example.json for the expected format.
"""

import json
import sys
import os

# Ensure the project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from werkzeug.security import generate_password_hash

from backend import app
from backend.models import db, User
from backend.quiz_adapters import get_quiz_adapter
from backend.quiz_catalog import synchronize_quiz_identities
from backend.quiz_types import get_registry

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SEED_FILE = os.path.join(PROJECT_ROOT, "data", "countries.json")
LEGACY_SEED_FILE = os.path.join(PROJECT_ROOT, "data", "destinations.json")


def _ensure_legacy_sqlite_schema_compatibility():
    """Apply minimal schema upgrades for legacy SQLite databases.

    SQLite ``create_all`` does not alter existing tables, so older databases
    may miss columns introduced later. Keep this narrowly scoped to known
    compatibility gaps needed by startup/seed paths.
    """
    if db.engine.dialect.name != "sqlite":
        return

    user_table_exists = db.session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name='user'")
    ).scalar()
    if not user_table_exists:
        return

    user_columns = {
        row[1] for row in db.session.execute(text('PRAGMA table_info("user")')).all()
    }
    if "password_changed_at" not in user_columns:
        db.session.execute(
            text('ALTER TABLE "user" ADD COLUMN password_changed_at DATETIME')
        )
        db.session.commit()
        print("  Added missing user.password_changed_at column for legacy schema")


def _resolve_admin_accounts(has_existing_admins):
    """Resolve admin accounts to seed.

    If ADMIN_BOOTSTRAP_PASSWORD is provided, only a single admin account is
    seeded using ADMIN_BOOTSTRAP_EMAIL (defaults to admin@example.com).
    If REQUIRE_CUSTOM_ADMIN_BOOTSTRAP is true and no custom password is set,
    fail fast only when the database has no existing admin users.
    """
    custom_email = os.environ.get("ADMIN_BOOTSTRAP_EMAIL", "").strip()
    custom_password = os.environ.get("ADMIN_BOOTSTRAP_PASSWORD", "")
    require_custom = (
        os.environ.get("REQUIRE_CUSTOM_ADMIN_BOOTSTRAP", "").strip().lower() == "true"
    )

    if custom_password:
        if len(custom_password) < 12:
            raise ValueError("ADMIN_BOOTSTRAP_PASSWORD must be at least 12 characters")
        if not custom_email:
            custom_email = "admin@example.com"
        return [(custom_email, custom_password)]

    if require_custom:
        if has_existing_admins:
            print("  Existing admin user found; preserving current admin credentials")
            return []
        raise RuntimeError(
            "REQUIRE_CUSTOM_ADMIN_BOOTSTRAP=true requires ADMIN_BOOTSTRAP_PASSWORD to be set"
        )

    return [
        ("admin@example.com", "adminpass123"),
    ]


def _load_destinations(path=None):
    """Load destination data from a JSON file.

    Args:
        path: Path to the JSON file. Defaults to data/countries.json.

    Returns:
        List of destination dicts, or None if file not found.
    """
    seed_path = path or os.environ.get("SEED_DATA_PATH") or DEFAULT_SEED_FILE
    if (
        not os.path.isfile(seed_path)
        and seed_path == DEFAULT_SEED_FILE
        and os.path.isfile(LEGACY_SEED_FILE)
    ):
        print(
            f"WARNING: {DEFAULT_SEED_FILE} not found, falling back to {LEGACY_SEED_FILE}",
            file=sys.stderr,
        )
        seed_path = LEGACY_SEED_FILE
    if not os.path.isfile(seed_path):
        return None
    with open(seed_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_quiz_type_data(identifier):
    """Load optional seed data for a non-country registered quiz type."""
    seed_path = os.path.join(PROJECT_ROOT, "data", f"{identifier}.json")
    if not os.path.isfile(seed_path):
        return None
    with open(seed_path, "r", encoding="utf-8") as seed_file:
        return json.load(seed_file)


def seed(destinations=None, quiz_data=None):
    """Seed registered standard quiz types and admin users.

    Args:
        destinations: Optional list of destination dicts. If None, loads from
                      data/countries.json (or SEED_DATA_PATH env var).
        quiz_data: Optional mapping of quiz type identifiers to record lists.
    """
    with app.app_context():
        try:
            db.create_all()
            _ensure_legacy_sqlite_schema_compatibility()

            # Seed admin user(s)
            existing_admin_count = User.query.filter_by(is_admin=True).count()
            admin_accounts = _resolve_admin_accounts(existing_admin_count > 0)
            for admin_email, admin_password in admin_accounts:
                admin = User.query.filter_by(email=admin_email).first()
                if admin:
                    admin.password_hash = generate_password_hash(admin_password)
                    admin.is_admin = True
                    print(f"  Updated admin user: {admin_email}")
                else:
                    admin = User(
                        name="Admin",
                        email=admin_email,
                        password_hash=generate_password_hash(admin_password),
                        is_admin=True,
                    )
                    db.session.add(admin)
                    print(f"  Created admin user: {admin_email}")

            db.session.commit()

            synchronized = synchronize_quiz_identities()
            db.session.commit()
            if synchronized:
                print(f"  Added {synchronized} missing quiz identity mapping(s)")
            supplied_quiz_data = dict(quiz_data or {})
            if destinations is not None:
                supplied_quiz_data["countries"] = destinations

            total_added = 0
            for quiz_type in get_registry():
                adapter = get_quiz_adapter(quiz_type.adapter or quiz_type.identifier)
                if adapter is None or not hasattr(adapter, "seed_questions"):
                    continue

                existing = adapter.question_model.query.count()
                if existing > 0 and "--force" not in sys.argv:
                    print(
                        f"Quiz type '{quiz_type.identifier}' already has "
                        f"{existing} question(s). Skipping seed."
                    )
                    continue

                records = supplied_quiz_data.get(quiz_type.identifier)
                if records is None:
                    records = (
                        _load_destinations()
                        if quiz_type.identifier == "countries"
                        else _load_quiz_type_data(quiz_type.identifier)
                    )
                if not records:
                    if quiz_type.identifier == "countries" and destinations is None:
                        print(
                            "ERROR: No seed data found. Place destination data in "
                            "data/countries.json or set SEED_DATA_PATH.",
                            file=sys.stderr,
                        )
                        sys.exit(1)
                    continue

                added = adapter.seed_questions(records)
                total_added += added
                print(f"  Seeded {added} question(s) for '{quiz_type.identifier}'")

            db.session.flush()
            synchronize_quiz_identities()
            db.session.commit()
            print(f"Seeded {total_added} question(s) across registered quiz types")
        except (OperationalError, RuntimeError, ValueError) as e:
            print(f"ERROR: Seed script failed - {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    seed()
