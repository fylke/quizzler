"""Property-based tests for admin quiz management using Hypothesis."""

import os
import unittest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

from hypothesis import assume, given, settings
from hypothesis import strategies as st
from werkzeug.security import generate_password_hash

from backend import app
from backend.admin import normalize_answers, validate_destination_payload
from backend.models import Destination, User, db

# --- Strategies for generating valid destination data ---

valid_name_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=128,
).filter(lambda s: len(s.strip()) > 0)

valid_hint_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=256,
).filter(lambda s: len(s.strip()) > 0)


valid_answer_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=128,
)

valid_destination_st = st.fixed_dictionaries(
    {
        "name": valid_name_st,
        "hints": st.lists(valid_hint_st, min_size=5, max_size=5),
        "correct_answers": st.lists(valid_answer_st, min_size=1, max_size=20),
    }
)


class PropertyTestUpdateRoundTrip(unittest.TestCase):
    """Property 7: Update round-trip.

    For any existing destination and for any valid update payload,
    after a successful PUT the subsequent GET for that destination
    SHALL return the updated values exactly as submitted (with answers normalized).
    """

    def setUp(self):
        app.testing = True
        self.client = app.test_client()
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

        with app.app_context():
            db.drop_all()
            db.create_all()

            # Create an admin user
            admin = User(
                email="admin@props.com",
                password_hash=generate_password_hash("adminpass123"),
                is_admin=True,
            )
            db.session.add(admin)
            db.session.commit()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def _login_admin(self):
        response = self.client.post(
            "/api/login",
            json={
                "email": "admin@props.com",
                "password": "adminpass123",
            },
        )
        return response.get_json()["csrfToken"]

    @settings(max_examples=8, deadline=5000)
    @given(
        create_data=valid_destination_st,
        update_data=valid_destination_st,
    )
    def test_update_round_trip(self, create_data, update_data):
        """After updating a destination, GET returns the updated values with normalized answers."""
        # Ensure unique names to avoid duplicate conflicts
        assume(create_data["name"].strip() != update_data["name"].strip())

        csrf = self._login_admin()

        # Create a destination
        create_resp = self.client.post(
            "/api/admin/destinations",
            json=create_data,
            headers={"X-CSRF-Token": csrf},
        )
        # If create fails due to duplicate name from a prior example, skip
        if create_resp.status_code == 409:
            return
        self.assertEqual(create_resp.status_code, 201, create_resp.get_json())
        dest_id = create_resp.get_json()["id"]

        # Update the destination with new data
        update_resp = self.client.put(
            f"/api/admin/destinations/{dest_id}",
            json=update_data,
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(update_resp.status_code, 200, update_resp.get_json())

        # GET the destination and verify it matches the update
        get_resp = self.client.get(f"/api/admin/destinations/{dest_id}")
        self.assertEqual(get_resp.status_code, 200)
        result = get_resp.get_json()

        self.assertEqual(result["name"], update_data["name"])
        self.assertEqual(result["hints"], update_data["hints"])

        # Answers should be normalized (lowercased + trimmed)
        expected_answers = [a.lower().strip() for a in update_data["correct_answers"]]
        self.assertEqual(result["correct_answers"], expected_answers)

        # Clean up: delete the destination to avoid name conflicts
        self.client.delete(
            f"/api/admin/destinations/{dest_id}",
            headers={"X-CSRF-Token": csrf},
        )


class PropertyTestValidation(unittest.TestCase):
    """Property 4: Destination validation accepts valid and rejects invalid payloads."""

    @settings(max_examples=8, deadline=2000)
    @given(data=valid_destination_st)
    def test_valid_payloads_pass_validation(self, data):
        """Any payload satisfying all constraints should pass validation."""
        is_valid, errors = validate_destination_payload(data)
        self.assertTrue(is_valid, f"Valid payload rejected: {errors}")

    @settings(max_examples=8, deadline=2000)
    @given(data=valid_destination_st)
    def test_missing_name_fails(self, data):
        """Removing the name field should fail validation."""
        del data["name"]
        is_valid, errors = validate_destination_payload(data)
        self.assertFalse(is_valid)
        self.assertTrue(any("name" in e for e in errors))

    @settings(max_examples=8, deadline=2000)
    @given(data=valid_destination_st)
    def test_wrong_hint_count_fails(self, data):
        """Having != 5 hints should fail validation."""
        data["hints"] = data["hints"][:3]
        is_valid, errors = validate_destination_payload(data)
        self.assertFalse(is_valid)
        self.assertTrue(any("hints" in e for e in errors))


class PropertyTestNormalization(unittest.TestCase):
    """Property 5: Answer normalization produces lowercase trimmed output."""

    @settings(max_examples=8, deadline=2000)
    @given(
        answers=st.lists(
            st.text(min_size=1, max_size=128),
            min_size=1,
            max_size=20,
        )
    )
    def test_normalization_produces_lowercase_trimmed(self, answers):
        """For any list of strings, normalize_answers produces lowercase trimmed output."""
        result = normalize_answers(answers)
        self.assertEqual(len(result), len(answers))
        for original, normalized in zip(answers, result):
            self.assertEqual(normalized, original.lower().strip())


if __name__ == "__main__":
    unittest.main()
