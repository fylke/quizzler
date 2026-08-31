import os
import unittest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

from werkzeug.security import generate_password_hash

from backend import app
from backend.models import Destination, QuizResult, User, db


class AdminAPITestCase(unittest.TestCase):
    """Tests for the admin destination CRUD API endpoints."""

    def setUp(self):
        app.testing = True
        self.client = app.test_client()
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

        with app.app_context():
            db.drop_all()
            db.create_all()

            # Create a regular user
            self.regular_user = User(
                email="regular@example.com",
                password_hash=generate_password_hash("password123"),
            )
            db.session.add(self.regular_user)

            # Create an admin user
            self.admin_user = User(
                email="admin@example.com",
                password_hash=generate_password_hash("adminpass123"),
                is_admin=True,
            )
            db.session.add(self.admin_user)
            db.session.commit()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    # --- Helpers ---

    def _login_admin(self):
        """Login as admin and return the CSRF token."""
        response = self.client.post(
            "/api/login",
            json={"email": "admin@example.com", "password": "adminpass123"},
        )
        data = response.get_json()
        return data["csrfToken"]

    def _login_regular(self):
        """Login as regular user and return the CSRF token."""
        response = self.client.post(
            "/api/login",
            json={"email": "regular@example.com", "password": "password123"},
        )
        data = response.get_json()
        return data["csrfToken"]

    def _valid_destination_payload(self, name="Test City"):
        """Return a valid destination payload for tests."""
        return {
            "name": name,
            "hints": ["hint 1", "hint 2", "hint 3", "hint 4", "hint 5"],
            "correct_answers": ["test city", "Test City"],
        }

    def _create_destination(self, csrf_token, payload=None):
        """Helper to create a destination and return the response."""
        if payload is None:
            payload = self._valid_destination_payload()
        return self.client.post(
            "/api/admin/destinations",
            json=payload,
            headers={"X-CSRF-Token": csrf_token},
        )

    # =====================================================================
    # AUTH TESTS - Representative check (decorator tested in test_admin_auth.py)
    # =====================================================================

    def test_list_returns_401_unauthenticated(self):
        """GET /api/admin/destinations returns 401 when not logged in."""
        client = app.test_client()
        response = client.get("/api/admin/destinations")
        self.assertEqual(response.status_code, 401)

    def test_list_returns_403_for_non_admin(self):
        """GET /api/admin/destinations returns 403 for non-admin user."""
        self._login_regular()
        response = self.client.get("/api/admin/destinations")
        self.assertEqual(response.status_code, 403)

    # =====================================================================
    # LIST DESTINATIONS - GET /api/admin/destinations
    # =====================================================================

    def test_list_returns_empty_list_when_no_destinations(self):
        """GET /api/admin/destinations returns empty list and count=0."""
        self._login_admin()
        response = self.client.get("/api/admin/destinations")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["destinations"], [])
        self.assertEqual(data["count"], 0)

    def test_list_returns_ordered_destinations_with_correct_count(self):
        """GET /api/admin/destinations returns destinations ordered by ID with correct count."""
        csrf = self._login_admin()
        # Create multiple destinations
        self._create_destination(csrf, self._valid_destination_payload("City A"))
        self._create_destination(csrf, self._valid_destination_payload("City B"))
        self._create_destination(csrf, self._valid_destination_payload("City C"))

        response = self.client.get("/api/admin/destinations")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["count"], 3)
        self.assertEqual(len(data["destinations"]), 3)
        # Verify ordering by ID
        names = [d["name"] for d in data["destinations"]]
        self.assertEqual(names, ["City A", "City B", "City C"])
        # Verify IDs are ascending
        ids = [d["id"] for d in data["destinations"]]
        self.assertEqual(ids, sorted(ids))

    # =====================================================================
    # GET DESTINATION - GET /api/admin/destinations/<id>
    # =====================================================================

    def test_get_returns_full_destination_data(self):
        """GET /api/admin/destinations/<id> returns full destination with hints array."""
        csrf = self._login_admin()
        create_response = self._create_destination(csrf)
        dest_id = create_response.get_json()["id"]

        response = self.client.get(f"/api/admin/destinations/{dest_id}")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["id"], dest_id)
        self.assertEqual(data["name"], "Test City")
        self.assertEqual(
            data["hints"], ["hint 1", "hint 2", "hint 3", "hint 4", "hint 5"]
        )
        # Answers are normalized (lowercased + trimmed)
        self.assertEqual(data["correct_answers"], ["test city", "test city"])

    def test_get_returns_404_for_nonexistent_id(self):
        """GET /api/admin/destinations/<id> returns 404 for non-existent ID."""
        self._login_admin()
        response = self.client.get("/api/admin/destinations/9999")
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertEqual(data["error"], "Destination not found")

    # =====================================================================
    # CREATE DESTINATION - POST /api/admin/destinations
    # =====================================================================

    def test_create_returns_201_with_id(self):
        """POST /api/admin/destinations returns 201 with the new destination ID."""
        csrf = self._login_admin()
        response = self._create_destination(csrf)
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertIn("id", data)
        self.assertIsInstance(data["id"], int)

    def test_create_stores_normalized_answers(self):
        """POST /api/admin/destinations normalizes answers (lowercased + trimmed)."""
        csrf = self._login_admin()
        payload = self._valid_destination_payload()
        payload["correct_answers"] = ["  Test City  ", "TEST CITY", "test city"]
        response = self._create_destination(csrf, payload)
        self.assertEqual(response.status_code, 201)
        dest_id = response.get_json()["id"]

        # Verify stored answers are normalized
        get_response = self.client.get(f"/api/admin/destinations/{dest_id}")
        data = get_response.get_json()
        self.assertEqual(
            data["correct_answers"], ["test city", "test city", "test city"]
        )

    def test_create_returns_400_for_invalid_payload(self):
        """POST /api/admin/destinations returns 400 for invalid payload."""
        csrf = self._login_admin()
        # Missing required fields
        response = self.client.post(
            "/api/admin/destinations", json={}, headers={"X-CSRF-Token": csrf}
        )
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertEqual(data["error"], "Validation failed")
        self.assertIn("details", data)
        self.assertIsInstance(data["details"], list)
        self.assertGreater(len(data["details"]), 0)

    def test_create_returns_400_for_wrong_hint_count(self):
        """POST /api/admin/destinations returns 400 when hints count is not 5."""
        csrf = self._login_admin()
        payload = self._valid_destination_payload()
        payload["hints"] = ["only one hint"]
        response = self.client.post(
            "/api/admin/destinations", json=payload, headers={"X-CSRF-Token": csrf}
        )
        self.assertEqual(response.status_code, 400)

    def test_create_returns_409_for_duplicate_name(self):
        """POST /api/admin/destinations returns 409 for duplicate destination name."""
        csrf = self._login_admin()
        self._create_destination(
            csrf, self._valid_destination_payload("Duplicate City")
        )
        # Attempt to create another with same name
        response = self._create_destination(
            csrf, self._valid_destination_payload("Duplicate City")
        )
        self.assertEqual(response.status_code, 409)
        data = response.get_json()
        self.assertEqual(data["error"], "A destination with this name already exists")

    def test_create_returns_403_without_csrf_token(self):
        """POST /api/admin/destinations returns 403 without CSRF token."""
        self._login_admin()
        response = self.client.post(
            "/api/admin/destinations", json=self._valid_destination_payload()
        )
        self.assertEqual(response.status_code, 403)
        data = response.get_json()
        self.assertEqual(data["error"], "Invalid or missing CSRF token")

    # =====================================================================
    # UPDATE DESTINATION - PUT /api/admin/destinations/<id>
    # =====================================================================

    def test_update_returns_200_with_updated_data(self):
        """PUT /api/admin/destinations/<id> returns 200 with updated destination data."""
        csrf = self._login_admin()
        create_response = self._create_destination(csrf)
        dest_id = create_response.get_json()["id"]

        updated_payload = {
            "name": "Updated City",
            "hints": [
                "new hint 1",
                "new hint 2",
                "new hint 3",
                "new hint 4",
                "new hint 5",
            ],
            "correct_answers": ["updated city"],
        }
        response = self.client.put(
            f"/api/admin/destinations/{dest_id}",
            json=updated_payload,
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["id"], dest_id)
        self.assertEqual(data["name"], "Updated City")
        self.assertEqual(
            data["hints"],
            ["new hint 1", "new hint 2", "new hint 3", "new hint 4", "new hint 5"],
        )
        self.assertEqual(data["correct_answers"], ["updated city"])

    def test_update_replaces_all_fields(self):
        """PUT /api/admin/destinations/<id> replaces all fields completely."""
        csrf = self._login_admin()
        create_response = self._create_destination(csrf)
        dest_id = create_response.get_json()["id"]

        new_payload = {
            "name": "Completely New",
            "hints": ["a", "b", "c", "d", "e"],
            "correct_answers": ["completely new", "brand new"],
        }
        self.client.put(
            f"/api/admin/destinations/{dest_id}",
            json=new_payload,
            headers={"X-CSRF-Token": csrf},
        )

        # Verify via GET
        get_response = self.client.get(f"/api/admin/destinations/{dest_id}")
        data = get_response.get_json()
        self.assertEqual(data["name"], "Completely New")
        self.assertEqual(data["hints"], ["a", "b", "c", "d", "e"])
        self.assertEqual(data["correct_answers"], ["completely new", "brand new"])

    def test_update_normalizes_answers(self):
        """PUT /api/admin/destinations/<id> normalizes answers on update."""
        csrf = self._login_admin()
        create_response = self._create_destination(csrf)
        dest_id = create_response.get_json()["id"]

        updated_payload = self._valid_destination_payload()
        updated_payload["correct_answers"] = ["  UPPER Case  ", "MiXeD"]
        response = self.client.put(
            f"/api/admin/destinations/{dest_id}",
            json=updated_payload,
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["correct_answers"], ["upper case", "mixed"])

    def test_update_returns_404_for_nonexistent(self):
        """PUT /api/admin/destinations/<id> returns 404 for non-existent destination."""
        csrf = self._login_admin()
        response = self.client.put(
            "/api/admin/destinations/9999",
            json=self._valid_destination_payload(),
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertEqual(data["error"], "Destination not found")

    def test_update_returns_400_for_invalid_payload(self):
        """PUT /api/admin/destinations/<id> returns 400 for invalid payload."""
        csrf = self._login_admin()
        create_response = self._create_destination(csrf)
        dest_id = create_response.get_json()["id"]

        # Send invalid payload (empty)
        response = self.client.put(
            f"/api/admin/destinations/{dest_id}",
            json={},
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertEqual(data["error"], "Validation failed")
        self.assertIn("details", data)

    def test_update_returns_403_without_csrf(self):
        """PUT /api/admin/destinations/<id> returns 403 without CSRF token."""
        csrf = self._login_admin()
        create_response = self._create_destination(csrf)
        dest_id = create_response.get_json()["id"]

        response = self.client.put(
            f"/api/admin/destinations/{dest_id}", json=self._valid_destination_payload()
        )
        self.assertEqual(response.status_code, 403)
        data = response.get_json()
        self.assertEqual(data["error"], "Invalid or missing CSRF token")

    # =====================================================================
    # DELETE DESTINATION - DELETE /api/admin/destinations/<id>
    # =====================================================================

    def test_delete_returns_200_with_message(self):
        """DELETE /api/admin/destinations/<id> returns 200 with success message."""
        csrf = self._login_admin()
        create_response = self._create_destination(csrf)
        dest_id = create_response.get_json()["id"]

        response = self.client.delete(
            f"/api/admin/destinations/{dest_id}", headers={"X-CSRF-Token": csrf}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["message"], "Destination deleted")

    def test_delete_destination_no_longer_exists(self):
        """After DELETE, the destination should no longer be accessible."""
        csrf = self._login_admin()
        create_response = self._create_destination(csrf)
        dest_id = create_response.get_json()["id"]

        self.client.delete(
            f"/api/admin/destinations/{dest_id}", headers={"X-CSRF-Token": csrf}
        )

        # Verify it's gone
        get_response = self.client.get(f"/api/admin/destinations/{dest_id}")
        self.assertEqual(get_response.status_code, 404)

    def test_delete_cascades_to_quiz_results(self):
        """DELETE /api/admin/destinations/<id> cascades to associated quiz_results."""
        csrf = self._login_admin()
        create_response = self._create_destination(csrf)
        dest_id = create_response.get_json()["id"]

        # Create a QuizResult linked to this destination
        with app.app_context():
            user = User.query.filter_by(email="admin@example.com").first()
            quiz_result = QuizResult(
                user_id=user.id,
                destination_id=dest_id,
                hint_difficulty=5,
                remaining_guesses=3,
                ongoing=False,
            )
            db.session.add(quiz_result)
            db.session.commit()

            # Verify quiz result exists
            qr = QuizResult.query.filter_by(destination_id=dest_id).first()
            self.assertIsNotNone(qr)

        # Delete the destination
        response = self.client.delete(
            f"/api/admin/destinations/{dest_id}", headers={"X-CSRF-Token": csrf}
        )
        self.assertEqual(response.status_code, 200)

        # Verify both destination and quiz result are gone
        with app.app_context():
            dest = db.session.get(Destination, dest_id)
            self.assertIsNone(dest)
            qr = QuizResult.query.filter_by(destination_id=dest_id).first()
            self.assertIsNone(qr)

    def test_delete_returns_404_for_nonexistent(self):
        """DELETE /api/admin/destinations/<id> returns 404 for non-existent destination."""
        csrf = self._login_admin()
        response = self.client.delete(
            "/api/admin/destinations/9999", headers={"X-CSRF-Token": csrf}
        )
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertEqual(data["error"], "Destination not found")

    def test_delete_returns_403_without_csrf(self):
        """DELETE /api/admin/destinations/<id> returns 403 without CSRF token."""
        csrf = self._login_admin()
        create_response = self._create_destination(csrf)
        dest_id = create_response.get_json()["id"]

        response = self.client.delete(f"/api/admin/destinations/{dest_id}")
        self.assertEqual(response.status_code, 403)
        data = response.get_json()
        self.assertEqual(data["error"], "Invalid or missing CSRF token")


if __name__ == "__main__":
    unittest.main()
