import os
import unittest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

from werkzeug.security import generate_password_hash

from backend import app
from backend.models import User, db


class AdminAuthTestCase(unittest.TestCase):
    """Tests for the admin authorization system (is_admin field, admin_required decorator, isAdmin in responses)."""

    # The admin_required decorator is tested against a real admin endpoint
    # rather than a test-only route,
    # which avoids Flask's "setup already finished" error when tests run
    # after other modules have already made requests.
    ADMIN_ENDPOINT = "/api/admin/quiz-types/countries/questions"

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

    # --- is_admin field defaults ---

    def test_is_admin_defaults_to_false(self):
        """New users should have is_admin=False by default."""
        with app.app_context():
            user = User(
                email="new@example.com",
                password_hash=generate_password_hash("pass12345"),
            )
            db.session.add(user)
            db.session.commit()

            fetched = db.session.get(User, user.id)
            self.assertFalse(fetched.is_admin)

    # --- Registration response ---

    def test_register_response_includes_is_admin_false(self):
        """Registration response should include isAdmin: false for new users."""
        response = self.client.post(
            "/api/register",
            json={"email": "brandnew@example.com", "password": "password123"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("isAdmin", data)
        self.assertFalse(data["isAdmin"])

    # --- Login response ---

    def test_login_response_includes_is_admin_false_for_regular_user(self):
        """Login response should include isAdmin: false for non-admin users."""
        response = self.client.post(
            "/api/login",
            json={"email": "regular@example.com", "password": "password123"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("isAdmin", data)
        self.assertFalse(data["isAdmin"])

    def test_login_response_includes_is_admin_true_for_admin_user(self):
        """Login response should include isAdmin: true for admin users."""
        response = self.client.post(
            "/api/login",
            json={"email": "admin@example.com", "password": "adminpass123"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("isAdmin", data)
        self.assertTrue(data["isAdmin"])

    # --- /api/me response ---

    def test_me_response_includes_is_admin_false_for_regular_user(self):
        """/api/me should include isAdmin: false for non-admin users."""
        self.client.post(
            "/api/login",
            json={"email": "regular@example.com", "password": "password123"},
        )
        response = self.client.get("/api/me")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("isAdmin", data)
        self.assertFalse(data["isAdmin"])

    def test_me_response_includes_is_admin_true_for_admin_user(self):
        """/api/me should include isAdmin: true for admin users."""
        self.client.post(
            "/api/login",
            json={"email": "admin@example.com", "password": "adminpass123"},
        )
        response = self.client.get("/api/me")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("isAdmin", data)
        self.assertTrue(data["isAdmin"])

    # --- admin_required decorator ---

    def test_admin_required_returns_401_for_unauthenticated_request(self):
        """admin_required should return 401 when no user is authenticated."""
        client = app.test_client()  # fresh client, no session
        response = client.get(self.ADMIN_ENDPOINT)
        self.assertEqual(response.status_code, 401)
        data = response.get_json()
        self.assertEqual(data["error"], "Authentication required")

    def test_admin_required_returns_403_for_non_admin_user(self):
        """admin_required should return 403 for authenticated non-admin users."""
        self.client.post(
            "/api/login",
            json={"email": "regular@example.com", "password": "password123"},
        )
        response = self.client.get(self.ADMIN_ENDPOINT)
        self.assertEqual(response.status_code, 403)
        data = response.get_json()
        self.assertEqual(data["error"], "Admin access required")

    def test_admin_required_allows_admin_user(self):
        """admin_required should allow access for authenticated admin users."""
        self.client.post(
            "/api/login",
            json={"email": "admin@example.com", "password": "adminpass123"},
        )
        response = self.client.get(self.ADMIN_ENDPOINT)
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
