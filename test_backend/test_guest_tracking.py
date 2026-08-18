"""Unit tests for server-side guest tracking and gameplay flows."""

import unittest

from backend import app
from backend.models import Destination, GuestSession, QuizResult, User, db
from backend.quiz_catalog import get_or_create_quiz_identity
from werkzeug.security import generate_password_hash


class GuestTrackingTestCase(unittest.TestCase):
    def setUp(self):
        app.testing = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        self.client = app.test_client()

        with app.app_context():
            db.drop_all()
            db.create_all()
            destination = Destination(
                id=1,
                name="paris",
                hint1="Hint 1",
                hint2="Hint 2",
                hint3="Hint 3",
                hint4="Hint 4",
                hint5="Hint 5",
                correct_answers=["paris"],
            )
            db.session.add(destination)
            db.session.commit()
            identity = get_or_create_quiz_identity("countries", destination.id)
            db.session.commit()
            self.quiz_guid = identity.guid

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def _start_guest_session(self):
        response = self.client.post("/api/guest-session")
        self.assertEqual(response.status_code, 200)
        return response

    def test_guest_session_endpoint_sets_cookie(self):
        response = self._start_guest_session()
        data = response.get_json()

        self.assertIn("guest", data)
        self.assertTrue(data["guest"]["isGuest"])
        self.assertIn("Set-Cookie", response.headers)
        self.assertIn("guest_token=", response.headers["Set-Cookie"])

    def test_guest_can_play_without_login(self):
        self._start_guest_session()

        quiz_response = self.client.get("/api/quiz")
        self.assertEqual(quiz_response.status_code, 200)
        quiz_data = quiz_response.get_json()
        self.assertEqual(quiz_data["hintDifficulty"], 5)
        self.assertEqual(quiz_data["remainingGuesses"], 3)

        wrong_response = self.client.post(
            "/api/check-answer", json={"answer": "london"}
        )
        self.assertEqual(wrong_response.status_code, 200)
        wrong_data = wrong_response.get_json()
        self.assertFalse(wrong_data["correct"])
        self.assertEqual(wrong_data["remainingGuesses"], 2)

    def test_existing_guest_session_is_restored_via_get(self):
        self._start_guest_session()

        response = self.client.get("/api/guest-session")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("guest", data)
        self.assertTrue(data["guest"]["isGuest"])

    def test_guest_stats_are_persisted_server_side(self):
        self._start_guest_session()

        self.client.get(f"/api/quiz/{self.quiz_guid}")
        answer_response = self.client.post(
            "/api/check-answer", json={"answer": "paris"}
        )
        self.assertEqual(answer_response.status_code, 200)
        answer_data = answer_response.get_json()
        self.assertTrue(answer_data["correct"])
        self.assertEqual(answer_data["points"], 15)

        stats_response = self.client.get("/api/stats")
        self.assertEqual(stats_response.status_code, 200)
        stats_data = stats_response.get_json()
        self.assertEqual(stats_data["quizzesCompleted"], 1)
        self.assertEqual(stats_data["cumulativeScore"], 15)

    def test_register_migrates_guest_results_into_new_account(self):
        self._start_guest_session()
        self.client.get(f"/api/quiz/{self.quiz_guid}")
        self.client.post("/api/check-answer", json={"answer": "paris"})

        response = self.client.post(
            "/api/register",
            json={
                "email": "migrated@example.com",
                "password": "password123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("guest_token=;", response.headers.get("Set-Cookie", ""))

        with app.app_context():
            user = User.query.filter_by(email="migrated@example.com").first()
            self.assertIsNotNone(user)
            result = QuizResult.query.filter_by(user_id=user.id, destination_id=1).first()
            self.assertIsNotNone(result)
            self.assertFalse(result.ongoing)
            self.assertEqual(result.hint_difficulty, 5)
            self.assertEqual(result.remaining_guesses, 3)
            self.assertEqual(GuestSession.query.count(), 0)

    def test_login_migrates_guest_results_into_existing_account(self):
        with app.app_context():
            user = User(
                name="Existing User",
                email="existing@example.com",
                password_hash=generate_password_hash("password123"),
            )
            db.session.add(user)
            db.session.commit()

        self._start_guest_session()
        self.client.get(f"/api/quiz/{self.quiz_guid}")
        self.client.get("/api/hint")

        response = self.client.post(
            "/api/login",
            json={"email": "existing@example.com", "password": "password123"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("guest_token=;", response.headers.get("Set-Cookie", ""))

        active_response = self.client.get("/api/quiz/active")
        self.assertEqual(active_response.status_code, 200)
        active_data = active_response.get_json()
        self.assertEqual(active_data["hintDifficulty"], 4)
        self.assertEqual(active_data["remainingGuesses"], 3)


if __name__ == "__main__":
    unittest.main()
