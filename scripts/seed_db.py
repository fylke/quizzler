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
from pathlib import Path

# Ensure the project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from werkzeug.security import generate_password_hash

from backend import app
from backend.models import db, Destination, User

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SEED_PATH = os.path.join(PROJECT_ROOT, "data")
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
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN password_changed_at DATETIME'))
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
    require_custom = os.environ.get("REQUIRE_CUSTOM_ADMIN_BOOTSTRAP", "").strip().lower() == "true"

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
        path: Path to a JSON file or directory of JSON files. Defaults to data/.

    Returns:
        List of destination dicts, or None if file not found.
    """
    seed_path = path or os.environ.get("SEED_DATA_PATH") or DEFAULT_SEED_PATH
    if not os.path.exists(seed_path) and seed_path == DEFAULT_SEED_PATH and os.path.isfile(LEGACY_SEED_FILE):
        print(
            f"WARNING: {DEFAULT_SEED_PATH} not found, falling back to {LEGACY_SEED_FILE}",
            file=sys.stderr,
        )
        seed_path = LEGACY_SEED_FILE

    seed_path_obj = Path(seed_path)
    if seed_path_obj.is_dir():
        destinations = []
        for json_path in sorted(seed_path_obj.glob("*.json")):
            with json_path.open("r", encoding="utf-8") as f:
                destinations.extend(json.load(f))
        return destinations or None

    if not seed_path_obj.is_file():
        return None
    with seed_path_obj.open("r", encoding="utf-8") as f:
        return json.load(f)


def seed(destinations=None):
    """Seed the database with destinations and admin users.

    Args:
        destinations: Optional list of destination dicts. If None, loads from
                      data/ (or SEED_DATA_PATH env var).
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

            existing = Destination.query.count()
            if existing > 0:
                print(f"Database already has {existing} destination(s). Skipping seed.")
                print("Use --force to seed anyway (existing data will be kept).")
                if "--force" not in sys.argv:
                    return

            # Load destinations from file if not passed directly
            if destinations is None:
                destinations = _load_destinations()
            if not destinations:
                print(
                    "ERROR: No seed data found. Place destination data in "
                    "data/ or set SEED_DATA_PATH.",
                    file=sys.stderr,
                )
                sys.exit(1)

            added = 0
            existing_ids = {row[0] for row in db.session.query(Destination.id).all()}
            existing_names = {row[0] for row in db.session.query(Destination.name).all()}
            for dest_data in destinations:
                destination_id = dest_data.get("id")
                destination_name = dest_data["name"]

                if destination_name in existing_names:
                    print(f"  Skipping '{destination_name}' (already exists)")
                    continue

                if destination_id is not None and int(destination_id) in existing_ids:
                    print(
                        f"  Reassigning id for '{destination_name}' "
                        f"(requested id={destination_id} already exists)"
                    )
                    destination_id = None

                create_kwargs = {
                    "name": destination_name,
                    "hint1": dest_data["hint1"],
                    "hint1_source": dest_data.get("hint1_source"),
                    "hint2": dest_data["hint2"],
                    "hint2_source": dest_data.get("hint2_source"),
                    "hint3": dest_data["hint3"],
                    "hint3_source": dest_data.get("hint3_source"),
                    "hint4": dest_data["hint4"],
                    "hint4_source": dest_data.get("hint4_source"),
                    "hint5": dest_data["hint5"],
                    "hint5_source": dest_data.get("hint5_source"),
                    "correct_answers": dest_data["correct_answers"],
                }
                if destination_id is not None:
                    create_kwargs["id"] = int(destination_id)
                    existing_ids.add(int(destination_id))

                dest = Destination(**create_kwargs)
                db.session.add(dest)
                existing_names.add(destination_name)
                added += 1

            db.session.commit()
            print(
                f"Seeded {added} destination(s). Total now: {Destination.query.count()}"
            )
        except (OperationalError, RuntimeError, ValueError) as e:
            print(f"ERROR: Seed script failed - {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    seed()
