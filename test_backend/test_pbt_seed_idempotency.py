"""Property-based test for seed script idempotency.

Feature: postgresql-migration, Property 3: Seed Script Idempotency

Validates: Requirements 7.2
"""

import os
import unittest

os.environ.setdefault("QUIZ_DATABASE_URL", "sqlite:///:memory:")

from hypothesis import given, settings
from hypothesis import strategies as st

from backend import app
from backend.models import Destination, db
from scripts.seed_db import seed

# Strategy: non-empty text for destination name
name_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P")),
    min_size=1,
    max_size=100,
)

# Strategy: hint strings (non-empty)
hint_st = st.text(min_size=1, max_size=200)

# Strategy: list of correct answer strings (at least 1, lowercase)
correct_answers_st = st.lists(
    st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "Zs")),
        min_size=1,
        max_size=50,
    ),
    min_size=1,
    max_size=5,
)

# Strategy: a full destination record (as a dict)
destination_st = st.fixed_dictionaries(
    {
        "name": name_st,
        "hint1": hint_st,
        "hint2": hint_st,
        "hint3": hint_st,
        "hint4": hint_st,
        "hint5": hint_st,
        "correct_answers": correct_answers_st,
    }
)

# Strategy: list of 1-5 destination records
destinations_st = st.lists(destination_st, min_size=1, max_size=5)


class TestSeedScriptIdempotency(unittest.TestCase):
    """Property 3: Seed Script Idempotency.

    For any database state where the destination table already contains one or
    more rows, running the seed script SHALL leave all existing rows unchanged —
    same count, same column values.

    **Validates: Requirements 7.2**
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

    def _snapshot_destinations(self):
        """Capture all destination rows as a list of dicts for comparison."""
        rows = []
        for dest in Destination.query.order_by(Destination.id).all():
            rows.append(
                {
                    "id": dest.id,
                    "name": dest.name,
                    "hint1": dest.hint1,
                    "hint2": dest.hint2,
                    "hint3": dest.hint3,
                    "hint4": dest.hint4,
                    "hint5": dest.hint5,
                    "correct_answers": dest.correct_answers,
                }
            )
        return rows

    @settings(max_examples=8, deadline=10000)
    @given(destinations=destinations_st)
    def test_seed_idempotency(self, destinations):
        """Running seed on a non-empty destination table leaves data unchanged.

        Feature: postgresql-migration, Property 3: Seed Script Idempotency

        **Validates: Requirements 7.2**
        """
        # Clean slate for this iteration
        db.session.query(Destination).delete()
        db.session.commit()

        # Insert generated destination(s) into the database
        for dest_data in destinations:
            dest = Destination(
                name=dest_data["name"],
                hint1=dest_data["hint1"],
                hint2=dest_data["hint2"],
                hint3=dest_data["hint3"],
                hint4=dest_data["hint4"],
                hint5=dest_data["hint5"],
                correct_answers=dest_data["correct_answers"],
            )
            db.session.add(dest)
        db.session.commit()

        # Snapshot before seed
        snapshot_before = self._snapshot_destinations()
        count_before = len(snapshot_before)

        # Run seed — should skip because destination table is non-empty
        seed(destinations=[])

        # Verify: row count unchanged, all field values unchanged
        snapshot_after = self._snapshot_destinations()
        count_after = len(snapshot_after)

        self.assertEqual(count_before, count_after, "Row count changed after seed()")
        self.assertEqual(
            snapshot_before, snapshot_after, "Destination data changed after seed()"
        )

        # Run seed again to confirm double-idempotency
        seed(destinations=[])

        # Verify again
        snapshot_after_second = self._snapshot_destinations()
        count_after_second = len(snapshot_after_second)

        self.assertEqual(
            count_before, count_after_second, "Row count changed after second seed()"
        )
        self.assertEqual(
            snapshot_before,
            snapshot_after_second,
            "Destination data changed after second seed()",
        )


if __name__ == "__main__":
    unittest.main()
