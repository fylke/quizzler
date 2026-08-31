"""Property-based test for JSON column round-trip fidelity.

Feature: postgresql-migration, Property 1: JSON Column Round-Trip Fidelity

Validates: Requirements 3.2
"""

import os
import unittest

os.environ.setdefault("QUIZ_DATABASE_URL", "sqlite:///:memory:")

from hypothesis import given, settings
from hypothesis import strategies as st

from backend import app
from backend.models import Destination, db

# Strategy: lists of arbitrary text (unicode, empty strings, special characters)
json_string_list_st = st.lists(
    st.text(min_size=0, max_size=200),
    min_size=0,
    max_size=20,
)

# Strategy: unique name for each destination (must be non-empty)
unique_name_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=100,
)


class TestJsonColumnRoundTrip(unittest.TestCase):
    """Property 1: JSON Column Round-Trip Fidelity.

    For any valid Python list of strings (representing correct_answers),
    writing it to a JSON column via SQLAlchemy and reading it back SHALL produce
    an identical Python list — same elements, same order, same types.

    **Validates: Requirements 3.2**
    """

    def setUp(self):
        app.testing = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        self.app_context = app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @settings(max_examples=8, deadline=5000)
    @given(
        name=unique_name_st,
        correct_answers=json_string_list_st,
    )
    def test_json_round_trip_fidelity(self, name, correct_answers):
        """Writing a list of strings to a JSON column and reading back yields identical data."""
        dest = Destination(
            name=name,
            hint1="h1",
            hint2="h2",
            hint3="h3",
            hint4="h4",
            hint5="h5",
            correct_answers=correct_answers,
        )
        db.session.add(dest)
        db.session.commit()

        dest_id = dest.id

        # Expunge the object from the session to force a fresh read from DB
        db.session.expunge(dest)

        # Re-read from the database
        loaded = db.session.get(Destination, dest_id)

        # Assert round-trip equality
        self.assertEqual(loaded.correct_answers, correct_answers)

        # Cleanup for next iteration
        db.session.delete(loaded)
        db.session.commit()


if __name__ == "__main__":
    unittest.main()
