"""Unit tests for /api/hint-complaint endpoint."""

import os
import unittest
from unittest.mock import patch

from backend import app
from backend.models import QuizResult, db
from test_backend.support import (
    add_destination,
    add_user,
    cleanup_database,
    configure_test_app,
    login_client_as,
    reset_database,
)


class HintComplaintAPITestCase(unittest.TestCase):
    def setUp(self):
        self.client = configure_test_app()
        reset_database()

        with app.app_context():
            self.user = add_user(
                email="complainer@example.com",
                password="password123",
            )

            self.destination = add_destination(
                destination_id=77,
                name="Lisbon",
                hints=["Hint 1", "Hint 2", "Hint 3", "Hint 4", "Hint 5"],
                correct_answers=["lisbon"],
            )
            db.session.commit()

            # Current live hint is 3, so unlocked hints are 3,4,5.
            self.quiz = QuizResult(
                user_id=self.user.id,
                destination_id=self.destination.id,
                hint_difficulty=3,
                remaining_guesses=2,
                ongoing=True,
            )
            db.session.add(self.quiz)
            db.session.commit()
            self._user_id = self.user.id

    def tearDown(self):
        cleanup_database()

    def _login(self):
        login_client_as(self.client, self._user_id)

    def test_requires_authentication(self):
        response = self.client.post(
            "/api/hint-complaint",
            json={
                "quizId": 77,
                "hintDifficulty": 3,
                "complainerEmail": "person@example.com",
                "message": "Bad hint",
            },
        )
        self.assertEqual(response.status_code, 401)

    @patch.dict(os.environ, {"ADMIN_EMAIL": "admin@example.com"}, clear=False)
    @patch("backend.routes_quiz.send_hint_complaint_email")
    def test_sends_complaint_email_for_unlocked_hint(self, mock_send):
        self._login()

        response = self.client.post(
            "/api/hint-complaint",
            json={
                "quizId": 77,
                "hintDifficulty": 4,
                "complainerEmail": "person@example.com",
                "message": "This hint is misleading.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["message"], "Complaint sent.")
        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs["admin_address"], "admin@example.com")
        self.assertEqual(kwargs["reporter_email"], "person@example.com")
        self.assertEqual(kwargs["quiz_id"], 77)
        self.assertEqual(kwargs["hint_difficulty"], 4)

    @patch.dict(
        os.environ,
        {"ADMIN_EMAIL": "", "SMTP_FROM_ADDRESS": "noreply@example.com"},
        clear=False,
    )
    @patch("backend.routes_quiz.send_hint_complaint_email")
    def test_uses_smtp_from_address_when_admin_email_missing(self, mock_send):
        self._login()

        response = self.client.post(
            "/api/hint-complaint",
            json={
                "quizId": 77,
                "hintDifficulty": 4,
                "complainerEmail": "person@example.com",
                "message": "Fallback recipient should be used.",
            },
        )

        self.assertEqual(response.status_code, 200)
        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs["admin_address"], "noreply@example.com")

    def test_rejects_hint_that_is_not_unlocked(self):
        self._login()

        response = self.client.post(
            "/api/hint-complaint",
            json={
                "quizId": 77,
                "hintDifficulty": 2,
                "complainerEmail": "person@example.com",
                "message": "I should not be allowed to report this yet.",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("not been unlocked", response.get_json()["error"])

    def test_rejects_quiz_id_mismatch(self):
        self._login()

        response = self.client.post(
            "/api/hint-complaint",
            json={
                "quizId": 999,
                "hintDifficulty": 3,
                "complainerEmail": "person@example.com",
                "message": "Wrong quiz id.",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("does not match active quiz", response.get_json()["error"])

    def test_rejects_missing_complainer_email(self):
        self._login()

        response = self.client.post(
            "/api/hint-complaint",
            json={
                "quizId": 77,
                "hintDifficulty": 3,
                "message": "Need follow-up",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("complainerEmail is required", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
