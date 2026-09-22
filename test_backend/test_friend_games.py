import unittest
from hashlib import sha256

from backend import app
from backend.friend_games import MAX_QUESTION_COUNT
from backend.models import FriendGame, db
from test_backend.support import (
    add_destination,
    cleanup_database,
    ensure_public_quiz_id,
    reset_database,
)


class FriendGamesApiTestCase(unittest.TestCase):
    def setUp(self):
        app.testing = True
        reset_database()
        with app.app_context():
            for index in range(1, 12):
                add_destination(
                    destination_id=index,
                    name=f"Country {index}",
                    correct_answers=[f"country {index}"],
                )
            db.session.commit()
        self.organizer = app.test_client()
        self.friend = app.test_client()
        self._start_guest(self.organizer)
        self._start_guest(self.friend)

    def tearDown(self):
        cleanup_database()

    @staticmethod
    def _start_guest(client):
        response = client.post("/api/guest-session")
        assert response.status_code == 200

    @staticmethod
    def _csrf(client):
        response = client.get("/api/friend-games/csrf")
        assert response.status_code == 200
        return response.get_json()["csrfToken"]

    def _post(self, client, path, payload):
        return client.post(
            path,
            json=payload,
            headers={"X-CSRF-Token": self._csrf(client)},
        )

    def test_guest_organizer_and_friend_share_ordered_game_and_results(self):
        response = self._post(
            self.organizer,
            "/api/friend-games",
            {"questionCount": 2, "displayName": "Organizer"},
        )
        self.assertEqual(response.status_code, 201)
        created = response.get_json()
        token = created["token"]
        self.assertTrue(created["url"].endswith(token))

        join_response = self._post(
            self.friend,
            f"/api/friend-games/{token}/join",
            {"displayName": "Friend"},
        )
        self.assertEqual(join_response.status_code, 200)
        friend_state = join_response.get_json()
        self.assertEqual(friend_state["question"]["position"], 0)
        self.assertEqual(len(friend_state["leaderboard"]), 2)

        organizer_state = self.organizer.get(
            f"/api/friend-games/{token}/state"
        ).get_json()
        self.assertEqual(organizer_state["question"]["position"], 0)
        self.assertEqual(
            organizer_state["question"]["questionCount"],
            friend_state["question"]["questionCount"],
        )

        with app.app_context():
            game = FriendGame.query.filter_by(
                token_hash=sha256(token.encode()).hexdigest()
            ).one()
            first_source_id = game.questions[0].source_id

        answer_response = self._post(
            self.organizer,
            f"/api/friend-games/{token}/answer",
            {"position": 0, "answer": f"country {first_source_id}"},
        )
        self.assertEqual(answer_response.status_code, 200)
        self.assertEqual(answer_response.get_json()["points"], 15)
        self.assertEqual(answer_response.get_json()["question"]["position"], 1)

        friend_results = self.friend.get(f"/api/friend-games/{token}/results")
        self.assertEqual(friend_results.status_code, 200)
        rows = friend_results.get_json()["leaderboard"]
        organizer_row = next(row for row in rows if row["displayName"] == "Organizer")
        self.assertEqual(organizer_row["score"], 15)
        self.assertEqual(organizer_row["completedQuestions"], 1)

    def test_question_count_is_bounded(self):
        for count in (0, MAX_QUESTION_COUNT + 1):
            response = self._post(
                self.organizer,
                "/api/friend-games",
                {"questionCount": count, "displayName": "Organizer"},
            )
            self.assertEqual(response.status_code, 400)

    def test_game_excludes_quizzes_already_taken_by_organizer(self):
        with app.app_context():
            completed_quiz_guid = ensure_public_quiz_id("countries", 1)
            db.session.commit()

        quiz_response = self.organizer.get(f"/api/quiz/{completed_quiz_guid}")
        self.assertEqual(quiz_response.status_code, 200)
        answer_response = self.organizer.post(
            "/api/check-answer", json={"answer": "country 1"}
        )
        self.assertEqual(answer_response.status_code, 200)
        self.assertTrue(answer_response.get_json()["correct"])

        response = self._post(
            self.organizer,
            "/api/friend-games",
            {"questionCount": 10, "displayName": "Organizer"},
        )
        self.assertEqual(response.status_code, 201)
        token = response.get_json()["token"]

        with app.app_context():
            game = FriendGame.query.filter_by(
                token_hash=sha256(token.encode()).hexdigest()
            ).one()
            selected_source_ids = {question.source_id for question in game.questions}

        self.assertNotIn(1, selected_source_ids)
        self.assertEqual(len(selected_source_ids), 10)

    def test_specific_quizzes_include_existing_results_for_each_participant(self):
        with app.app_context():
            quiz_one_guid = ensure_public_quiz_id("countries", 1)
            quiz_two_guid = ensure_public_quiz_id("countries", 2)
            db.session.commit()

        organizer_quiz = self.organizer.get(f"/api/quiz/{quiz_one_guid}")
        self.assertEqual(organizer_quiz.status_code, 200)
        organizer_answer = self.organizer.post(
            "/api/check-answer", json={"answer": "country 1"}
        )
        self.assertTrue(organizer_answer.get_json()["correct"])

        friend_quiz = self.friend.get(f"/api/quiz/{quiz_two_guid}")
        self.assertEqual(friend_quiz.status_code, 200)
        friend_answer = self.friend.post(
            "/api/check-answer", json={"answer": "country 2"}
        )
        self.assertTrue(friend_answer.get_json()["correct"])

        response = self._post(
            self.organizer,
            "/api/friend-games",
            {"quizIds": [1, 2], "displayName": "Organizer"},
        )
        self.assertEqual(response.status_code, 201)
        token = response.get_json()["token"]

        organizer_state = self.organizer.get(
            f"/api/friend-games/{token}/state"
        ).get_json()
        self.assertEqual(organizer_state["question"]["position"], 1)
        organizer_row = next(
            row
            for row in organizer_state["leaderboard"]
            if row["displayName"] == "Organizer"
        )
        self.assertEqual(organizer_row["score"], 15)
        self.assertEqual(organizer_row["completedQuestions"], 1)

        join_response = self._post(
            self.friend,
            f"/api/friend-games/{token}/join",
            {"displayName": "Friend"},
        )
        self.assertEqual(join_response.status_code, 200)
        friend_state = join_response.get_json()
        self.assertEqual(friend_state["question"]["position"], 0)
        friend_row = next(
            row for row in friend_state["leaderboard"] if row["displayName"] == "Friend"
        )
        self.assertEqual(friend_row["score"], 15)
        self.assertEqual(friend_row["completedQuestions"], 1)

    def test_unjoined_participant_cannot_read_results(self):
        response = self._post(
            self.organizer,
            "/api/friend-games",
            {"questionCount": 1, "displayName": "Organizer"},
        )
        token = response.get_json()["token"]
        self.assertEqual(
            self.friend.get(f"/api/friend-games/{token}/results").status_code,
            403,
        )


if __name__ == "__main__":
    unittest.main()
