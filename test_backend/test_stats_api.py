"""Unit tests and property-based tests for the /api/stats endpoint."""

import unittest

from hypothesis import given, settings
from hypothesis import strategies as st

from backend import app
from backend.models import Destination, QuizResult, User, db
from backend.stats import compute_stats
from test_backend.support import (
    add_destination,
    add_user,
    cleanup_database,
    configure_test_app,
    login_client_as,
    reset_database,
)

# Minimal destination fixture for creating quiz results
SAMPLE_DESTINATIONS = [
    {
        "id": 1,
        "name": "tokyo",
        "hint1": "H1",
        "hint2": "H2",
        "hint3": "H3",
        "hint4": "H4",
        "hint5": "H5",
        "correct_answers": ["tokyo, japan"],
    },
    {
        "id": 2,
        "name": "paris",
        "hint1": "H1",
        "hint2": "H2",
        "hint3": "H3",
        "hint4": "H4",
        "hint5": "H5",
        "correct_answers": ["paris, france"],
    },
    {
        "id": 3,
        "name": "new york",
        "hint1": "H1",
        "hint2": "H2",
        "hint3": "H3",
        "hint4": "H4",
        "hint5": "H5",
        "correct_answers": ["new york, usa"],
    },
    {
        "id": 4,
        "name": "sydney",
        "hint1": "H1",
        "hint2": "H2",
        "hint3": "H3",
        "hint4": "H4",
        "hint5": "H5",
        "correct_answers": ["sydney, australia"],
    },
    {
        "id": 5,
        "name": "rome",
        "hint1": "H1",
        "hint2": "H2",
        "hint3": "H3",
        "hint4": "H4",
        "hint5": "H5",
        "correct_answers": ["rome, italy"],
    },
]


class StatsAPITestCase(unittest.TestCase):
    """Unit tests for the /api/stats endpoint (Task 2.2)."""

    def setUp(self):
        self.client = configure_test_app()
        reset_database()

        with app.app_context():
            for d in SAMPLE_DESTINATIONS:
                add_destination(
                    destination_id=d["id"],
                    name=d["name"],
                    hints=[d[f"hint{index}"] for index in range(1, 6)],
                    correct_answers=d["correct_answers"],
                )

            self.user = add_user(
                email="stats@example.com",
                password="password123",
            )
            db.session.commit()
            self._user_id = self.user.id

    def tearDown(self):
        cleanup_database()

    def _login(self, client, user_id):
        """Simulate login by setting user_id in the session."""
        login_client_as(client, user_id)

    def test_unauthenticated_returns_401(self):
        """Unauthenticated request to /api/stats returns 401."""
        client = app.test_client()
        response = client.get("/api/stats")
        self.assertEqual(response.status_code, 401)
        data = response.get_json()
        self.assertEqual(data["error"], "Authentication required")

    def test_guest_session_can_fetch_zero_stats(self):
        """Guest session can access /api/stats and gets all-zero metrics initially."""
        guest_response = self.client.post("/api/guest-session")
        self.assertEqual(guest_response.status_code, 200)

        response = self.client.get("/api/stats")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["cumulativeScore"], 0)
        self.assertEqual(data["quizzesCompleted"], 0)
        self.assertEqual(data["averageScore"], 0)
        self.assertEqual(data["bestScore"], 0)
        self.assertEqual(data["accuracyRate"], 0)
        self.assertEqual(data["currentStreak"], 0)
        self.assertEqual(data["quizzesOngoing"], 0)

    def test_zero_completed_quizzes_returns_all_zeros(self):
        """Authenticated user with no completed quizzes gets all-zero stats."""
        self._login(self.client, self._user_id)
        response = self.client.get("/api/stats")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["cumulativeScore"], 0)
        self.assertEqual(data["quizzesCompleted"], 0)
        self.assertEqual(data["averageScore"], 0)
        self.assertEqual(data["bestScore"], 0)
        self.assertEqual(data["accuracyRate"], 0)
        self.assertEqual(data["currentStreak"], 0)
        self.assertEqual(data["quizzesOngoing"], 0)

    def test_completed_quizzes_returns_correct_stats(self):
        """Authenticated user with completed quizzes gets correct computed stats."""
        with app.app_context():
            # Create completed quiz results
            # Result 1: hint_difficulty=5, remaining_guesses=3 -> score=15
            r1 = QuizResult(
                user_id=self._user_id,
                destination_id=1,
                hint_difficulty=5,
                remaining_guesses=3,
                ongoing=False,
            )
            # Result 2: hint_difficulty=3, remaining_guesses=2 -> score=6
            r2 = QuizResult(
                user_id=self._user_id,
                destination_id=2,
                hint_difficulty=3,
                remaining_guesses=2,
                ongoing=False,
            )
            # Result 3: hint_difficulty=4, remaining_guesses=0 -> score=0 (failed)
            r3 = QuizResult(
                user_id=self._user_id,
                destination_id=3,
                hint_difficulty=4,
                remaining_guesses=0,
                ongoing=False,
            )
            db.session.add_all([r1, r2, r3])
            db.session.commit()

        self._login(self.client, self._user_id)
        response = self.client.get("/api/stats")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        # cumulativeScore = 15 + 6 + 0 = 21
        self.assertEqual(data["cumulativeScore"], 21)
        # quizzesCompleted = 3
        self.assertEqual(data["quizzesCompleted"], 3)
        # averageScore = round(21/3, 1) = 7.0
        self.assertEqual(data["averageScore"], 7.0)
        # bestScore = 15
        self.assertEqual(data["bestScore"], 15)
        # accuracyRate = round(2/3 * 100) = 67
        self.assertEqual(data["accuracyRate"], 67)
        # currentStreak: sorted by desc destination_id -> dest 3 (guesses=0) -> streak stops = 0
        self.assertEqual(data["currentStreak"], 0)
        self.assertEqual(data["quizzesOngoing"], 0)

    def test_data_isolation_between_users(self):
        """User A only sees their own stats, not user B's."""
        with app.app_context():
            user_b = add_user(
                email="userb@example.com",
                password="password123",
            )
            db.session.commit()
            user_b_id = user_b.id

            # User A: one completed quiz -> score = 5*3 = 15
            r_a = QuizResult(
                user_id=self._user_id,
                destination_id=1,
                hint_difficulty=5,
                remaining_guesses=3,
                ongoing=False,
            )
            # User B: one completed quiz -> score = 2*1 = 2
            r_b = QuizResult(
                user_id=user_b_id,
                destination_id=2,
                hint_difficulty=2,
                remaining_guesses=1,
                ongoing=False,
            )
            db.session.add_all([r_a, r_b])
            db.session.commit()

        # Check user A stats
        self._login(self.client, self._user_id)
        response = self.client.get("/api/stats")
        self.assertEqual(response.status_code, 200)
        data_a = response.get_json()
        self.assertEqual(data_a["cumulativeScore"], 15)
        self.assertEqual(data_a["quizzesCompleted"], 1)
        self.assertEqual(data_a["bestScore"], 15)

        # Check user B stats with a fresh client
        client_b = app.test_client()
        self._login(client_b, user_b_id)
        response_b = client_b.get("/api/stats")
        self.assertEqual(response_b.status_code, 200)
        data_b = response_b.get_json()
        self.assertEqual(data_b["cumulativeScore"], 2)
        self.assertEqual(data_b["quizzesCompleted"], 1)
        self.assertEqual(data_b["bestScore"], 2)

    def test_ongoing_quizzes_excluded_but_counted(self):
        """Ongoing quizzes are excluded from stats but counted in quizzesOngoing."""
        with app.app_context():
            # Completed quiz: score = 4*2 = 8
            r_completed = QuizResult(
                user_id=self._user_id,
                destination_id=1,
                hint_difficulty=4,
                remaining_guesses=2,
                ongoing=False,
            )
            # Ongoing quiz (should not contribute to stats)
            r_ongoing = QuizResult(
                user_id=self._user_id,
                destination_id=2,
                hint_difficulty=5,
                remaining_guesses=3,
                ongoing=True,
            )
            db.session.add_all([r_completed, r_ongoing])
            db.session.commit()

        self._login(self.client, self._user_id)
        response = self.client.get("/api/stats")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        # Only the completed quiz contributes to stats
        self.assertEqual(data["cumulativeScore"], 8)
        self.assertEqual(data["quizzesCompleted"], 1)
        self.assertEqual(data["averageScore"], 8.0)
        self.assertEqual(data["bestScore"], 8)
        self.assertEqual(data["accuracyRate"], 100)
        self.assertEqual(data["currentStreak"], 1)
        # Ongoing quiz is counted separately
        self.assertEqual(data["quizzesOngoing"], 1)


# Feature: status-screen-stats, Property 6: Data isolation between users
class PropertyTestDataIsolation(unittest.TestCase):
    """Property 6: Data isolation between users.

    For any two distinct users each with their own quiz results, the statistics
    returned for user A SHALL be identical to computing statistics from only
    user A's records, unaffected by user B's records.

    **Validates: Requirements 4.2**
    """

    def setUp(self):
        configure_test_app()
        reset_database()

    def tearDown(self):
        cleanup_database()

    @settings(max_examples=8, deadline=10000)
    @given(
        user_a_results=st.lists(
            st.fixed_dictionaries(
                {
                    "hint_difficulty": st.integers(min_value=1, max_value=5),
                    "remaining_guesses": st.integers(min_value=0, max_value=3),
                    "destination_id": st.integers(min_value=1, max_value=50),
                }
            ),
            min_size=0,
            max_size=10,
            unique_by=lambda r: r["destination_id"],
        ),
        user_b_results=st.lists(
            st.fixed_dictionaries(
                {
                    "hint_difficulty": st.integers(min_value=1, max_value=5),
                    "remaining_guesses": st.integers(min_value=0, max_value=3),
                    "destination_id": st.integers(min_value=51, max_value=100),
                }
            ),
            min_size=0,
            max_size=10,
            unique_by=lambda r: r["destination_id"],
        ),
    )
    def test_user_a_stats_unaffected_by_user_b(self, user_a_results, user_b_results):
        """Stats for user A match computing stats from only user A's records."""
        with app.app_context():
            reset_database()

            # Create destinations for all destination_ids used
            all_dest_ids = set()
            for r in user_a_results:
                all_dest_ids.add(r["destination_id"])
            for r in user_b_results:
                all_dest_ids.add(r["destination_id"])

            for did in all_dest_ids:
                add_destination(
                    destination_id=did,
                    name=f"dest_{did}",
                    hints=["H1", "H2", "H3", "H4", "H5"],
                    correct_answers=["answer"],
                )

            user_a = add_user(email="usera@test.com", password="pass123a")
            user_b = add_user(email="userb@test.com", password="pass123b")
            db.session.commit()

            # Insert quiz results for user A (all completed)
            for r in user_a_results:
                qr = QuizResult(
                    user_id=user_a.id,
                    destination_id=r["destination_id"],
                    hint_difficulty=r["hint_difficulty"],
                    remaining_guesses=r["remaining_guesses"],
                    ongoing=False,
                )
                db.session.add(qr)

            # Insert quiz results for user B (all completed)
            for r in user_b_results:
                qr = QuizResult(
                    user_id=user_b.id,
                    destination_id=r["destination_id"],
                    hint_difficulty=r["hint_difficulty"],
                    remaining_guesses=r["remaining_guesses"],
                    ongoing=False,
                )
                db.session.add(qr)

            db.session.commit()

            # Call the API as user A
            client = app.test_client()
            login_client_as(client, user_a.id)

            response = client.get("/api/stats")
            self.assertEqual(response.status_code, 200)
            api_stats = response.get_json()

            # Compute expected stats from only user A's records
            expected_stats = compute_stats(user_a_results)

            # Verify they match
            self.assertEqual(
                api_stats["cumulativeScore"], expected_stats["cumulativeScore"]
            )
            self.assertEqual(
                api_stats["quizzesCompleted"], expected_stats["quizzesCompleted"]
            )
            self.assertEqual(api_stats["averageScore"], expected_stats["averageScore"])
            self.assertEqual(api_stats["bestScore"], expected_stats["bestScore"])
            self.assertEqual(api_stats["accuracyRate"], expected_stats["accuracyRate"])
            self.assertEqual(
                api_stats["currentStreak"], expected_stats["currentStreak"]
            )
            self.assertEqual(api_stats["quizzesOngoing"], 0)


if __name__ == "__main__":
    unittest.main()
