import unittest

from werkzeug.security import generate_password_hash

from backend import app
from backend.models import (
    Destination,
    GuestQuizResult,
    GuestSession,
    QuizResult,
    User,
    db,
)
from backend.quiz_catalog import get_or_create_quiz_identity, public_quiz_id

ADMIN_QUESTIONS_URL = "/api/admin/quiz-types/countries/questions"


class AdminAPITestCase(unittest.TestCase):
    """Tests for the generic admin question CRUD API endpoints."""

    def setUp(self):
        app.testing = True
        self.client = app.test_client()
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

        with app.app_context():
            db.drop_all()
            db.create_all()

            self.regular_user = User(
                email="regular@example.com",
                password_hash=generate_password_hash("password123"),
            )
            db.session.add(self.regular_user)

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

    def _question_url(self, source_id=None):
        if source_id is None:
            return ADMIN_QUESTIONS_URL
        return f"{ADMIN_QUESTIONS_URL}/{source_id}"

    def _login_admin(self):
        response = self.client.post(
            "/api/login",
            json={"email": "admin@example.com", "password": "adminpass123"},
        )
        return response.get_json()["csrfToken"]

    def _login_regular(self):
        response = self.client.post(
            "/api/login",
            json={"email": "regular@example.com", "password": "password123"},
        )
        return response.get_json()["csrfToken"]

    def _valid_question_payload(self, name="Test City"):
        return {
            "name": name,
            "hints": ["hint 1", "hint 2", "hint 3", "hint 4", "hint 5"],
            "correct_answers": ["test city", "Test City"],
        }

    def _create_question(self, csrf_token, payload=None):
        if payload is None:
            payload = self._valid_question_payload()
        return self.client.post(
            self._question_url(),
            json=payload,
            headers={"X-CSRF-Token": csrf_token},
        )

    def test_list_returns_401_unauthenticated(self):
        client = app.test_client()
        response = client.get(self._question_url())
        self.assertEqual(response.status_code, 401)

    def test_list_returns_403_for_non_admin(self):
        self._login_regular()
        response = self.client.get(self._question_url())
        self.assertEqual(response.status_code, 403)

    def test_list_returns_empty_questions_when_no_questions_exist(self):
        self._login_admin()
        response = self.client.get(self._question_url())
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["questions"], [])
        self.assertEqual(data["count"], 0)

    def test_list_returns_ordered_questions_with_correct_count(self):
        csrf = self._login_admin()
        self._create_question(csrf, self._valid_question_payload("City A"))
        self._create_question(csrf, self._valid_question_payload("City B"))
        self._create_question(csrf, self._valid_question_payload("City C"))

        response = self.client.get(self._question_url())
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["count"], 3)
        self.assertEqual(len(data["questions"]), 3)
        names = [question["name"] for question in data["questions"]]
        ids = [question["id"] for question in data["questions"]]
        self.assertEqual(names, ["City A", "City B", "City C"])
        self.assertEqual(ids, sorted(ids))

    def test_get_returns_full_question_data(self):
        csrf = self._login_admin()
        create_response = self._create_question(csrf)
        source_id = create_response.get_json()["id"]

        response = self.client.get(self._question_url(source_id))
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["id"], source_id)
        self.assertEqual(data["name"], "Test City")
        self.assertEqual(
            data["hints"], ["hint 1", "hint 2", "hint 3", "hint 4", "hint 5"]
        )
        self.assertEqual(data["correct_answers"], ["test city", "test city"])

    def test_get_returns_404_for_nonexistent_question(self):
        self._login_admin()
        response = self.client.get(self._question_url(9999))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "Question not found")

    def test_create_returns_201_with_id_and_guid(self):
        csrf = self._login_admin()
        response = self._create_question(csrf)
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertIn("id", data)
        self.assertIsInstance(data["id"], int)
        self.assertEqual(data["guid"], public_quiz_id("countries", data["id"]))

    def test_create_stores_normalized_answers(self):
        csrf = self._login_admin()
        payload = self._valid_question_payload()
        payload["correct_answers"] = ["  Test City  ", "TEST CITY", "test city"]
        response = self._create_question(csrf, payload)
        self.assertEqual(response.status_code, 201)

        get_response = self.client.get(self._question_url(response.get_json()["id"]))
        self.assertEqual(
            get_response.get_json()["correct_answers"],
            ["test city", "test city", "test city"],
        )

    def test_create_rejects_invalid_payload(self):
        csrf = self._login_admin()
        response = self.client.post(
            self._question_url(), json={}, headers={"X-CSRF-Token": csrf}
        )
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertEqual(data["error"], "Validation failed")
        self.assertIsInstance(data["details"], list)
        self.assertGreater(len(data["details"]), 0)

    def test_create_rejects_duplicate_name(self):
        csrf = self._login_admin()
        self._create_question(csrf, self._valid_question_payload("Duplicate City"))

        response = self._create_question(
            csrf, self._valid_question_payload("Duplicate City")
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.get_json()["error"], "A question with this name already exists"
        )

    def test_create_requires_csrf_token(self):
        self._login_admin()
        response = self.client.post(
            self._question_url(), json=self._valid_question_payload()
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "Invalid or missing CSRF token")

    def test_update_returns_updated_question_data(self):
        csrf = self._login_admin()
        source_id = self._create_question(csrf).get_json()["id"]
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
            self._question_url(source_id),
            json=updated_payload,
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["id"], source_id)
        self.assertEqual(data["name"], "Updated City")
        self.assertEqual(data["hints"], updated_payload["hints"])
        self.assertEqual(data["correct_answers"], ["updated city"])

    def test_update_rejects_invalid_payload(self):
        csrf = self._login_admin()
        source_id = self._create_question(csrf).get_json()["id"]

        response = self.client.put(
            self._question_url(source_id), json={}, headers={"X-CSRF-Token": csrf}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Validation failed")

    def test_update_returns_404_for_nonexistent_question(self):
        csrf = self._login_admin()
        response = self.client.put(
            self._question_url(9999),
            json=self._valid_question_payload(),
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "Question not found")

    def test_update_requires_csrf_token(self):
        csrf = self._login_admin()
        source_id = self._create_question(csrf).get_json()["id"]
        response = self.client.put(
            self._question_url(source_id), json=self._valid_question_payload()
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "Invalid or missing CSRF token")

    def test_delete_returns_200_and_removes_question(self):
        csrf = self._login_admin()
        source_id = self._create_question(csrf).get_json()["id"]

        response = self.client.delete(
            self._question_url(source_id), headers={"X-CSRF-Token": csrf}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["message"], "Question deleted")
        self.assertEqual(
            self.client.get(self._question_url(source_id)).status_code, 404
        )

    def test_delete_cascades_to_user_and_guest_results(self):
        csrf = self._login_admin()
        source_id = self._create_question(csrf).get_json()["id"]

        with app.app_context():
            user = User.query.filter_by(email="admin@example.com").first()
            guest_session = GuestSession(token_hash="guest-token-hash")
            db.session.add(guest_session)
            db.session.flush()
            db.session.add_all(
                [
                    QuizResult(
                        user_id=user.id,
                        destination_id=source_id,
                        hint_difficulty=5,
                        remaining_guesses=3,
                        ongoing=False,
                    ),
                    GuestQuizResult(
                        guest_session_id=guest_session.id,
                        destination_id=source_id,
                        hint_difficulty=4,
                        remaining_guesses=2,
                        ongoing=False,
                    ),
                ]
            )
            get_or_create_quiz_identity("countries", source_id)
            db.session.commit()

        response = self.client.delete(
            self._question_url(source_id), headers={"X-CSRF-Token": csrf}
        )
        self.assertEqual(response.status_code, 200)

        with app.app_context():
            self.assertIsNone(db.session.get(Destination, source_id))
            self.assertIsNone(
                QuizResult.query.filter_by(destination_id=source_id).first()
            )
            self.assertIsNone(
                GuestQuizResult.query.filter_by(destination_id=source_id).first()
            )

    def test_delete_returns_404_for_nonexistent_question(self):
        csrf = self._login_admin()
        response = self.client.delete(
            self._question_url(9999), headers={"X-CSRF-Token": csrf}
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "Question not found")

    def test_delete_requires_csrf_token(self):
        csrf = self._login_admin()
        source_id = self._create_question(csrf).get_json()["id"]

        response = self.client.delete(self._question_url(source_id))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "Invalid or missing CSRF token")


if __name__ == "__main__":
    unittest.main()
