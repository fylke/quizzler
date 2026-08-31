"""Integration coverage for adding a second standard quiz type."""

import os
import unittest

os.environ.setdefault("QUIZ_DATABASE_URL", "sqlite:///:memory:")

from backend import app
from backend.models import QuizIdentity, User, db
from backend.quiz_adapters import (
    StandardQuizAdapter,
    register_quiz_adapter,
    unregister_quiz_adapter,
)
from backend.quiz_types import QUIZ_TYPES, QuizType


class City(db.Model):
    __tablename__ = "test_cities"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    hint1 = db.Column(db.String(256), nullable=False)
    hint2 = db.Column(db.String(256), nullable=False)
    hint3 = db.Column(db.String(256), nullable=False)
    hint4 = db.Column(db.String(256), nullable=False)
    hint5 = db.Column(db.String(256), nullable=False)
    correct_answers = db.Column(db.JSON, nullable=False)


class CityQuizResult(db.Model):
    __tablename__ = "test_city_quiz_result"

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    city_id = db.Column(db.Integer, db.ForeignKey("test_cities.id"), primary_key=True)
    hint_difficulty = db.Column(db.Integer, nullable=False, default=5)
    remaining_guesses = db.Column(db.Integer, nullable=False, default=3)
    ongoing = db.Column(db.Boolean, nullable=False, default=True)


class GuestCityQuizResult(db.Model):
    __tablename__ = "test_guest_city_quiz_result"

    guest_session_id = db.Column(
        db.Integer,
        db.ForeignKey("guest_session.id"),
        primary_key=True,
    )
    city_id = db.Column(db.Integer, db.ForeignKey("test_cities.id"), primary_key=True)
    hint_difficulty = db.Column(db.Integer, nullable=False, default=5)
    remaining_guesses = db.Column(db.Integer, nullable=False, default=3)
    ongoing = db.Column(db.Boolean, nullable=False, default=True)


class MultiQuizTypeTestCase(unittest.TestCase):
    quiz_type = QuizType(
        identifier="cities",
        display_name="Cities",
        rules_file="countries.md",
        source_table="test_cities",
        public_code="y",
        adapter="cities",
    )

    @classmethod
    def setUpClass(cls):
        register_quiz_adapter(
            StandardQuizAdapter(
                identifier="cities",
                question_model=City,
                user_result_model=CityQuizResult,
                guest_result_model=GuestCityQuizResult,
                result_source_field="city_id",
            )
        )
        QUIZ_TYPES.append(cls.quiz_type)

    @classmethod
    def tearDownClass(cls):
        QUIZ_TYPES.remove(cls.quiz_type)
        unregister_quiz_adapter("cities")

    def setUp(self):
        app.testing = True
        self.client = app.test_client()
        with app.app_context():
            db.drop_all()
            db.create_all()
            city = City(
                id=1,
                name="Oslo",
                hint1="Capital of Norway",
                hint2="On the Oslofjord",
                hint3="Hosts the Nobel Peace Prize",
                hint4="A Nordic capital",
                hint5="Its name starts with O",
                correct_answers=["oslo"],
            )
            user = User(
                email="types@example.com",
                password_hash="unused",
                is_admin=True,
            )
            db.session.add_all([city, user])
            db.session.commit()
            self.user_id = user.id

        with self.client.session_transaction() as session:
            session["user_id"] = self.user_id
            session["csrf_token"] = "multi-type-csrf"
        self.csrf_headers = {"X-CSRF-Token": "multi-type-csrf"}

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_second_type_uses_shared_random_hint_and_answer_routes(self):
        response = self.client.get("/api/quiz?type=cities")
        self.assertEqual(response.status_code, 200)
        quiz = response.get_json()
        self.assertEqual(quiz["quizType"], "cities")
        self.assertEqual(quiz["id"], 1)
        self.assertTrue(quiz["guid"])
        self.assertEqual(quiz["images"][0], "/media/cities/1/5a.jpg")

        hint = self.client.get("/api/hint")
        self.assertEqual(hint.status_code, 200)
        self.assertEqual(hint.get_json()["hintDifficulty"], 4)

        answer = self.client.post("/api/check-answer", json={"answer": "oslo"})
        self.assertEqual(answer.status_code, 200)
        self.assertTrue(answer.get_json()["correct"])

        with app.app_context():
            result = CityQuizResult.query.filter_by(
                user_id=self.user_id,
                city_id=1,
            ).one()
            self.assertFalse(result.ongoing)

    def test_second_type_guid_reopens_same_question(self):
        quiz = self.client.get("/api/quiz?type=cities").get_json()

        response = self.client.get(f"/api/quiz/{quiz['guid']}")

        self.assertEqual(response.status_code, 200)
        reopened = response.get_json()
        self.assertEqual(reopened["quizType"], "cities")
        self.assertEqual(reopened["id"], 1)

    def test_second_type_guest_progress_migrates_and_contributes_to_stats(self):
        with self.client.session_transaction() as session:
            session.pop("user_id", None)
        self.assertEqual(self.client.post("/api/guest-session").status_code, 200)

        self.client.get("/api/quiz?type=cities")
        answer = self.client.post("/api/check-answer", json={"answer": "oslo"})
        self.assertTrue(answer.get_json()["correct"])

        guest_stats = self.client.get("/api/stats").get_json()
        self.assertEqual(guest_stats["quizzesCompleted"], 1)
        self.assertEqual(guest_stats["cumulativeScore"], 15)

        registration = self.client.post(
            "/api/register",
            json={
                "email": "city-guest@example.com",
                "password": "password123",
            },
        )
        self.assertEqual(registration.status_code, 200)

        with app.app_context():
            migrated_user = User.query.filter_by(email="city-guest@example.com").one()
            result = CityQuizResult.query.filter_by(
                user_id=migrated_user.id,
                city_id=1,
            ).one()
            self.assertFalse(result.ongoing)
            self.assertEqual(GuestCityQuizResult.query.count(), 0)

    def test_second_type_uses_shared_admin_crud(self):
        payload = {
            "name": "Bergen",
            "hints": ["h1", "h2", "h3", "h4", "h5"],
            "correct_answers": ["Bergen", " bergen "],
        }
        created = self.client.post(
            "/api/admin/quiz-types/cities/questions",
            json=payload,
            headers=self.csrf_headers,
        )
        self.assertEqual(created.status_code, 201)
        created_data = created.get_json()

        listed = self.client.get("/api/admin/quiz-types/cities/questions").get_json()
        self.assertEqual(listed["count"], 2)
        self.assertEqual(
            [item["name"] for item in listed["questions"]], ["Oslo", "Bergen"]
        )

        source_id = created_data["id"]
        payload["name"] = "Updated Bergen"
        updated = self.client.put(
            f"/api/admin/quiz-types/cities/questions/{source_id}",
            json=payload,
            headers=self.csrf_headers,
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["correct_answers"], ["bergen", "bergen"])

        with app.app_context():
            db.session.add(
                CityQuizResult(
                    user_id=self.user_id,
                    city_id=source_id,
                    ongoing=False,
                )
            )
            db.session.commit()

        deleted = self.client.delete(
            f"/api/admin/quiz-types/cities/questions/{source_id}",
            headers=self.csrf_headers,
        )
        self.assertEqual(deleted.status_code, 200)

        with app.app_context():
            self.assertIsNone(db.session.get(City, source_id))
            self.assertIsNone(CityQuizResult.query.filter_by(city_id=source_id).first())
            self.assertIsNone(db.session.get(QuizIdentity, created_data["guid"]))

    def test_second_type_uses_shared_seed_pipeline(self):
        from scripts.seed_db import seed

        with app.app_context():
            City.query.delete()
            db.session.commit()

        seed(
            destinations=[],
            quiz_data={
                "cities": [
                    {
                        "id": 7,
                        "name": "Stockholm",
                        "hint1": "h1",
                        "hint2": "h2",
                        "hint3": "h3",
                        "hint4": "h4",
                        "hint5": "h5",
                        "correct_answers": ["Stockholm"],
                    }
                ]
            },
        )

        with app.app_context():
            city = db.session.get(City, 7)
            self.assertIsNotNone(city)
            self.assertEqual(city.correct_answers, ["stockholm"])
            identity = QuizIdentity.query.filter_by(
                quiz_type="cities",
                source_id=7,
            ).one()
            self.assertTrue(identity.guid)


if __name__ == "__main__":
    unittest.main()
