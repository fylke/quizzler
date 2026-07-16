"""Unit tests for seed script.

Validates:
- Requirements 7.1: Empty DB gets seeded with at least 5 destinations and 1 admin user
- Requirements 7.3: Same seed data produced regardless of backend (tested with SQLite)
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from sqlalchemy import text
from werkzeug.security import generate_password_hash

# Ensure in-memory SQLite is used before importing anything from backend
os.environ["QUIZ_DATABASE_URL"] = "sqlite:///:memory:"

from backend import app
from backend.models import db, Destination, User  # noqa: F401 - User used in seed

# Test fixture — minimal destination data for unit tests
TEST_DESTINATIONS = [
    {
        "name": f"Test City {i}",
        "hint1": f"Hint 1 for city {i}",
        "hint2": f"Hint 2 for city {i}",
        "hint3": f"Hint 3 for city {i}",
        "hint4": f"Hint 4 for city {i}",
        "hint5": f"Hint 5 for city {i}",
        "correct_answers": [f"test city {i}"],
    }
    for i in range(1, 6)
]


class TestSeedEmptyDatabase(unittest.TestCase):
    """Test that an empty database gets seeded with expected data."""

    def setUp(self):
        app.testing = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

        with app.app_context():
            db.drop_all()
            db.create_all()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_seed_populates_empty_database_with_at_least_5_destinations(self):
        """Requirement 7.1: seed inserts at least 5 destinations when table is empty."""
        from scripts.seed_db import seed

        seed(destinations=TEST_DESTINATIONS)

        with app.app_context():
            count = Destination.query.count()
            self.assertGreaterEqual(count, 5)

    def test_seed_populates_empty_database_with_at_least_1_admin_user(self):
        """Requirement 7.1: seed inserts at least 1 admin user when table is empty."""
        from scripts.seed_db import seed

        seed(destinations=TEST_DESTINATIONS)

        with app.app_context():
            admin_count = User.query.filter_by(is_admin=True).count()
            self.assertGreaterEqual(admin_count, 1)

    def test_seed_destinations_have_all_required_fields(self):
        """Requirement 7.1: each destination has all required fields populated."""
        from scripts.seed_db import seed

        seed(destinations=TEST_DESTINATIONS)

        with app.app_context():
            destinations = Destination.query.all()
            for dest in destinations:
                self.assertTrue(dest.name, f"Destination {dest.id} has empty name")
                self.assertTrue(dest.hint1, f"Destination {dest.id} has empty hint1")
                self.assertTrue(dest.hint2, f"Destination {dest.id} has empty hint2")
                self.assertTrue(dest.hint3, f"Destination {dest.id} has empty hint3")
                self.assertTrue(dest.hint4, f"Destination {dest.id} has empty hint4")
                self.assertTrue(dest.hint5, f"Destination {dest.id} has empty hint5")
                self.assertIsInstance(dest.correct_answers, list)
                self.assertGreater(len(dest.correct_answers), 0)

    def test_seed_upgrades_legacy_user_table_missing_password_changed_at(self):
        """Seeding upgrades legacy SQLite schema that lacks user.password_changed_at."""
        from scripts.seed_db import seed

        with app.app_context():
            db.drop_all()
            db.session.execute(
                text(
                    """
                    CREATE TABLE user (
                        id INTEGER NOT NULL PRIMARY KEY,
                        password_hash VARCHAR(256) NOT NULL,
                        name VARCHAR(128) NOT NULL,
                        email VARCHAR(128) NOT NULL UNIQUE,
                        is_admin BOOLEAN NOT NULL DEFAULT 0
                    )
                    """
                )
            )
            db.session.commit()

        seed(destinations=TEST_DESTINATIONS)

        with app.app_context():
            columns = {
                row[1] for row in db.session.execute(text('PRAGMA table_info("user")')).all()
            }
            self.assertIn("password_changed_at", columns)
            self.assertGreaterEqual(User.query.filter_by(is_admin=True).count(), 1)

    def test_seed_preserves_existing_admin_when_custom_bootstrap_secret_missing(self):
        """Custom bootstrap secret is only required when no admin already exists."""
        from scripts.seed_db import seed

        with app.app_context():
            db.session.add(
                User(
                    name="Existing Admin",
                    email="admin@example.com",
                    password_hash=generate_password_hash("already-set-password"),
                    is_admin=True,
                )
            )
            db.session.commit()

        with patch.dict(
            os.environ,
            {
                "REQUIRE_CUSTOM_ADMIN_BOOTSTRAP": "true",
                "ADMIN_BOOTSTRAP_PASSWORD": "",
                "ADMIN_BOOTSTRAP_EMAIL": "",
            },
            clear=False,
        ):
            seed(destinations=TEST_DESTINATIONS)

        with app.app_context():
            self.assertEqual(User.query.filter_by(is_admin=True).count(), 1)
            self.assertEqual(Destination.query.count(), len(TEST_DESTINATIONS))

    def test_seed_requires_custom_bootstrap_secret_for_fresh_database(self):
        """Fresh databases still fail fast when custom bootstrap is required but missing."""
        from scripts.seed_db import seed

        with patch.dict(
            os.environ,
            {
                "REQUIRE_CUSTOM_ADMIN_BOOTSTRAP": "true",
                "ADMIN_BOOTSTRAP_PASSWORD": "",
                "ADMIN_BOOTSTRAP_EMAIL": "",
            },
            clear=False,
        ):
            with self.assertRaises(SystemExit) as ctx:
                seed(destinations=TEST_DESTINATIONS)

        self.assertEqual(ctx.exception.code, 1)

    def test_load_destinations_reads_all_json_files_from_seed_directory(self):
        """Default directory-based loading includes all JSON question files."""
        from scripts.seed_db import _load_destinations

        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "a.json"), "w", encoding="utf-8") as handle:
                handle.write(
                    '[{"name":"Alpha","hint1":"1","hint2":"2","hint3":"3","hint4":"4","hint5":"5","correct_answers":["alpha"]}]'
                )
            with open(os.path.join(tmpdir, "b.json"), "w", encoding="utf-8") as handle:
                handle.write(
                    '[{"name":"Beta","hint1":"1","hint2":"2","hint3":"3","hint4":"4","hint5":"5","correct_answers":["beta"]}]'
                )

            destinations = _load_destinations(tmpdir)

        self.assertIsNotNone(destinations)
        self.assertEqual([dest["name"] for dest in destinations], ["Alpha", "Beta"])

    def test_seed_force_adds_missing_destinations_even_when_ids_overlap(self):
        """Forced additive seed loads later files even when their source IDs overlap."""
        from scripts.seed_db import seed

        existing_destination = {
            "id": 1,
            "name": "Country One",
            "hint1": "a",
            "hint2": "b",
            "hint3": "c",
            "hint4": "d",
            "hint5": "e",
            "correct_answers": ["country one"],
        }
        overlapping_destination = {
            "id": 1,
            "name": "City One",
            "hint1": "f",
            "hint2": "g",
            "hint3": "h",
            "hint4": "i",
            "hint5": "j",
            "correct_answers": ["city one"],
        }

        seed(destinations=[existing_destination])

        with patch.object(sys, "argv", ["seed_db.py", "--force"]):
            seed(destinations=[existing_destination, overlapping_destination])

        with app.app_context():
            names = [dest.name for dest in Destination.query.order_by(Destination.id).all()]
            self.assertEqual(names, ["Country One", "City One"])
            self.assertEqual(Destination.query.count(), 2)


if __name__ == "__main__":
    unittest.main()
