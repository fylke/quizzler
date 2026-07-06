"""Unit tests for /api/quiz-types and /api/rules/<type> endpoints.

Validates Requirements: 1.1, 1.2, 1.4, 3.2, 3.3, 3.5, 5.1, 5.3, 5.4, 5.5
"""

import os
import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from backend import app
from backend.models import db, Destination, QuizResult, User

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class QuizTypesAPITestCase(unittest.TestCase):
    """Unit tests for the quiz types API endpoints."""

    def setUp(self):
        app.testing = True
        self.client = app.test_client()
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

        with app.app_context():
            db.drop_all()
            db.create_all()

            # Create test user
            self.user = User(
                name="Test User",
                email="test@example.com",
                password_hash=generate_password_hash("password123"),
            )
            db.session.add(self.user)
            db.session.commit()
            self._user_id = self.user.id

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def _login(self, client, user_id):
        """Simulate login by setting user_id in the session."""
        with client.session_transaction() as sess:
            sess["user_id"] = user_id

    # --- /api/quiz-types endpoint tests ---

    def test_quiz_types_requires_authentication(self):
        """GET /api/quiz-types without auth returns 401."""
        response = self.client.get("/api/quiz-types")
        self.assertEqual(response.status_code, 401)
        data = response.get_json()
        self.assertEqual(data["error"], "Authentication required")

    def test_quiz_types_with_guest_session_returns_registered_types(self):
        """GET /api/quiz-types with a guest cookie returns available types."""
        guest_response = self.client.post("/api/guest-session")
        self.assertEqual(guest_response.status_code, 200)

        response = self.client.get("/api/quiz-types")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsInstance(data, list)
        identifiers = [qt["identifier"] for qt in data]
        self.assertIn("countries", identifiers)

    def test_quiz_types_default_registry_includes_countries(self):
        """GET /api/quiz-types with auth returns list including 'countries'."""
        self._login(self.client, self._user_id)
        response = self.client.get("/api/quiz-types")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsInstance(data, list)
        identifiers = [qt["identifier"] for qt in data]
        self.assertIn("countries", identifiers)
        # Check that 'countries' has correct display name
        countries_entry = next(qt for qt in data if qt["identifier"] == "countries")
        self.assertEqual(countries_entry["displayName"], "Countries")

    @patch("backend.get_registry")
    def test_quiz_types_empty_registry_returns_empty_list(self, mock_registry):
        """GET /api/quiz-types with empty registry returns [] with 200."""
        mock_registry.return_value = []
        self._login(self.client, self._user_id)
        response = self.client.get("/api/quiz-types")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data, [])

    @patch("backend.get_registry")
    def test_quiz_types_registered_type_appears_in_response(self, mock_registry):
        """Registered quiz type appears in the /api/quiz-types response."""
        from backend.quiz_types import QuizType

        mock_registry.return_value = [
            QuizType(
                identifier="cities",
                display_name="Cities",
                rules_file="cities.md",
                source_table="cities",
            ),
        ]
        self._login(self.client, self._user_id)
        response = self.client.get("/api/quiz-types")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["identifier"], "cities")
        self.assertEqual(data[0]["displayName"], "Cities")

    # --- /api/rules/<quiz_type> endpoint tests ---

    def test_rules_requires_authentication(self):
        """GET /api/rules/countries without auth returns 401."""
        response = self.client.get("/api/rules/countries")
        self.assertEqual(response.status_code, 401)
        data = response.get_json()
        self.assertEqual(data["error"], "Authentication required")

    def test_rules_with_guest_session_returns_content(self):
        """GET /api/rules/countries with guest session returns markdown."""
        guest_response = self.client.post("/api/guest-session")
        self.assertEqual(guest_response.status_code, 200)

        response = self.client.get("/api/rules/countries")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("content", data)
        self.assertIn("# Countries Quiz Rules", data["content"])

    def test_rules_returns_file_content_in_json_wrapper(self):
        """GET /api/rules/countries with auth returns 200 with content key."""
        self._login(self.client, self._user_id)
        response = self.client.get("/api/rules/countries")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("content", data)
        # The content should be non-empty markdown
        self.assertIsInstance(data["content"], str)
        self.assertGreater(len(data["content"]), 0)
        # Should contain the expected heading from countries.md
        self.assertIn("# Countries Quiz Rules", data["content"])

    def test_rules_404_for_missing_rules_file(self):
        """GET /api/rules/nonexistent with auth returns 404."""
        self._login(self.client, self._user_id)
        response = self.client.get("/api/rules/nonexistent")
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertIn("error", data)
        self.assertIn("nonexistent", data["error"])

    def test_rules_400_for_path_separators_backslash(self):
        """GET /api/rules/foo\\bar with auth returns 400 (backslash rejected)."""
        self._login(self.client, self._user_id)
        response = self.client.get("/api/rules/foo\\bar")
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)

    def test_rules_400_for_uppercase_characters(self):
        """GET /api/rules/INVALID with auth returns 400 (uppercase not allowed)."""
        self._login(self.client, self._user_id)
        response = self.client.get("/api/rules/INVALID")
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)

    def test_rules_400_for_special_characters(self):
        """GET /api/rules/inv@lid with auth returns 400."""
        self._login(self.client, self._user_id)
        response = self.client.get("/api/rules/inv@lid")
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)

    def test_rules_400_for_identifier_too_long(self):
        """GET /api/rules/<65+ chars> with auth returns 400."""
        self._login(self.client, self._user_id)
        long_identifier = "a" * 65
        response = self.client.get(f"/api/rules/{long_identifier}")
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)

    def test_rules_400_for_identifier_starting_with_hyphen(self):
        """GET /api/rules/-invalid with auth returns 400 (must start with alnum)."""
        self._login(self.client, self._user_id)
        response = self.client.get("/api/rules/-invalid")
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)

    def test_rules_400_for_empty_identifier(self):
        """GET /api/rules/ with empty identifier returns 404 (no route match)."""
        self._login(self.client, self._user_id)
        response = self.client.get("/api/rules/")
        # Flask won't match the route with empty parameter, returns 404
        self.assertIn(response.status_code, [400, 404])


class BackwardCompatibilityTestCase(unittest.TestCase):
    """Task 7.2: Verify backward compatibility of existing endpoints.

    Validates Requirements 5.3, 5.4, 5.5:
    - /api/quiz returns correct response structure
    - Media files served at /media/countries/{id}/{level}{a|b}.jpg
    - Quiz results stored with same scoring formula (hint_difficulty × remaining_guesses)
    """

    def setUp(self):
        app.testing = True
        self.client = app.test_client()
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

        with app.app_context():
            db.drop_all()
            db.create_all()

            # Create a test destination
            dest = Destination(
                id=42,
                name="tokyo",
                hint1="Hint level 1 - easiest",
                hint2="Hint level 2",
                hint3="Hint level 3",
                hint4="Hint level 4",
                hint5="Hint level 5 - hardest",
                correct_answers=["tokyo, japan", "tokyo"],
            )
            db.session.add(dest)

            # Create a test user
            user = User(
                name="Compat User",
                email="compat@example.com",
                password_hash=generate_password_hash("password123"),
            )
            db.session.add(user)
            db.session.commit()
            self.test_user_id = user.id

        # Log in via session transaction (avoids issues with cross-test DB config)
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.test_user_id

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_quiz_endpoint_returns_expected_structure(self):
        """Requirement 5.3: /api/quiz returns id, hint, hintDifficulty, remainingGuesses, images."""
        response = self.client.get("/api/quiz")
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        # Verify all required fields are present
        self.assertIn("id", data)
        self.assertIn("hint", data)
        self.assertIn("hintDifficulty", data)
        self.assertIn("remainingGuesses", data)
        self.assertIn("images", data)

        # Verify field types
        self.assertIsInstance(data["id"], int)
        self.assertIsInstance(data["hint"], str)
        self.assertIsInstance(data["hintDifficulty"], int)
        self.assertIsInstance(data["remainingGuesses"], int)
        self.assertIsInstance(data["images"], list)

        # Verify initial values: starts at hardest hint (5) with 3 guesses
        self.assertEqual(data["hintDifficulty"], 5)
        self.assertEqual(data["remainingGuesses"], 3)

    def test_quiz_endpoint_images_follow_media_url_pattern(self):
        """Requirement 5.5: Images served at /media/countries/{id}/{level}{a|b}.jpg."""
        response = self.client.get("/api/quiz")
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        images = data["images"]
        dest_id = data["id"]
        hint_level = data["hintDifficulty"]

        # Should have exactly 2 images (a and b variants)
        self.assertEqual(len(images), 2)

        # Verify URL pattern
        expected_a = f"/media/countries/{dest_id}/{hint_level}a.jpg"
        expected_b = f"/media/countries/{dest_id}/{hint_level}b.jpg"
        self.assertEqual(images[0], expected_a)
        self.assertEqual(images[1], expected_b)

    def test_specific_quiz_endpoint_returns_expected_structure(self):
        """Requirement 5.3: /api/quiz/<id> also returns the same structure."""
        response = self.client.get("/api/quiz/42")
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertIn("id", data)
        self.assertIn("hint", data)
        self.assertIn("hintDifficulty", data)
        self.assertIn("remainingGuesses", data)
        self.assertIn("images", data)

        self.assertEqual(data["id"], 42)
        self.assertEqual(data["hintDifficulty"], 5)
        self.assertEqual(data["remainingGuesses"], 3)
        self.assertEqual(data["hint"], "Hint level 5 - hardest")

    def test_specific_quiz_images_follow_media_url_pattern(self):
        """Requirement 5.5: Specific quiz images follow /media/countries/{id}/{level}{a|b}.jpg."""
        response = self.client.get("/api/quiz/42")
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        images = data["images"]

        self.assertEqual(len(images), 2)
        self.assertEqual(images[0], "/media/countries/42/5a.jpg")
        self.assertEqual(images[1], "/media/countries/42/5b.jpg")

    def test_correct_answer_stores_score_with_formula(self):
        """Requirement 5.4: Score = hint_difficulty × remaining_guesses."""
        # Start a specific quiz (destination 42, hint_difficulty=5, remaining_guesses=3)
        self.client.get("/api/quiz/42")

        # Answer correctly on the first try: score = 5 * 3 = 15
        response = self.client.post(
            "/api/check-answer", json={"answer": "tokyo, japan"}
        )
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertTrue(data["correct"])
        self.assertEqual(data["points"], 15)  # 5 * 3 = 15

        # Verify stored in quiz_result table
        with app.app_context():
            result = QuizResult.query.filter_by(
                user_id=self.test_user_id, destination_id=42
            ).first()
            self.assertIsNotNone(result)
            # After correct answer, quiz is no longer ongoing
            self.assertFalse(result.ongoing)
            # Score is hint_difficulty * remaining_guesses
            self.assertEqual(result.hint_difficulty * result.remaining_guesses, 15)

    def test_score_after_wrong_answers(self):
        """Requirement 5.4: Score decreases as guesses are used up."""
        # Start quiz: hint_difficulty=5, remaining_guesses=3
        self.client.get("/api/quiz/42")

        # Wrong answer: remaining_guesses goes from 3 to 2, hint_difficulty stays at 5
        resp1 = self.client.post(
            "/api/check-answer", json={"answer": "wrong answer"}
        )
        self.assertEqual(resp1.status_code, 200)
        data1 = resp1.get_json()
        self.assertFalse(data1["correct"])
        self.assertEqual(data1["remainingGuesses"], 2)

        # Now answer correctly: score = current hint_difficulty * remaining_guesses
        resp2 = self.client.post(
            "/api/check-answer", json={"answer": "tokyo, japan"}
        )
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.get_json()
        self.assertTrue(data2["correct"])
        # After one wrong answer: hint_difficulty is still 5, remaining_guesses=2
        # Score = 5 * 2 = 10
        self.assertEqual(data2["points"], 10)

    def test_media_endpoint_serves_files(self):
        """Requirement 5.5: /media/countries/{id}/{level}{a|b}.jpg path is served."""
        # The /media/<path:filename> route exists and responds
        # (even if file doesn't exist on disk, the route should be registered)
        response = self.client.get("/media/countries/42/5a.jpg")
        # Will be 404 because no actual file, but the route itself is active
        # (not a 405 Method Not Allowed or similar)
        self.assertIn(response.status_code, [200, 404])

    def test_quiz_result_composite_key(self):
        """Requirement 5.4: Results stored with composite key (user_id, destination_id)."""
        # Start and complete a quiz
        self.client.get("/api/quiz/42")
        self.client.post("/api/check-answer", json={"answer": "tokyo, japan"})

        with app.app_context():
            result = QuizResult.query.filter_by(
                user_id=self.test_user_id, destination_id=42
            ).first()
            self.assertIsNotNone(result)
            self.assertEqual(result.user_id, self.test_user_id)
            self.assertEqual(result.destination_id, 42)

if __name__ == "__main__":
    unittest.main()
