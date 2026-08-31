import unittest

from sqlalchemy.exc import IntegrityError

from backend import app
from backend.models import Destination, QuizResult, User, db


class DatabaseModelTestCase(unittest.TestCase):
    def setUp(self):
        app.testing = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

        with app.app_context():
            db.drop_all()
            db.create_all()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_destination_model_can_be_created_and_retrieved(self):
        with app.app_context():
            destination = Destination(
                name="Testopolis",
                hint1="Hint 1",
                hint2="Hint 2",
                hint3="Hint 3",
                hint4="Hint 4",
                hint5="Hint 5",
                correct_answers=["testopolis"],
            )
            db.session.add(destination)
            db.session.commit()

            self.assertIsNotNone(destination.id)

            loaded = Destination.query.filter_by(name="Testopolis").first()
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.hint1, "Hint 1")
            self.assertEqual(loaded.correct_answers, ["testopolis"])

    def test_quiz_result_links_user_and_destination(self):
        with app.app_context():
            user = User(email="quiz@user.test", password_hash="hash123")
            destination = Destination(
                name="Relationville",
                hint1="H1",
                hint2="H2",
                hint3="H3",
                hint4="H4",
                hint5="H5",
                correct_answers=["relationville"],
            )
            db.session.add_all([user, destination])
            db.session.commit()

            quiz_result = QuizResult(
                user_id=user.id,
                destination_id=destination.id,
                hint_difficulty=4,
                remaining_guesses=2,
                ongoing=True,
            )
            db.session.add(quiz_result)
            db.session.commit()

            loaded_result = QuizResult.query.first()
            self.assertIsNotNone(loaded_result)
            self.assertEqual(loaded_result.user.id, user.id)
            self.assertEqual(loaded_result.country.id, destination.id)
            self.assertEqual(loaded_result.user.email, "quiz@user.test")
            self.assertEqual(loaded_result.country.name, "Relationville")
            self.assertEqual(user.results[0].country.name, "Relationville")
            self.assertEqual(destination.results[0].user.email, "quiz@user.test")

    def test_quiz_result_is_removed_when_user_is_deleted(self):
        with app.app_context():
            user = User(email="cascade@user.test", password_hash="hash123")
            destination = Destination(
                name="Cascade City",
                hint1="H1",
                hint2="H2",
                hint3="H3",
                hint4="H4",
                hint5="H5",
                correct_answers=["cascade city"],
            )
            db.session.add_all([user, destination])
            db.session.commit()

            quiz_result = QuizResult(
                user=user,
                country=destination,
                hint_difficulty=5,
                remaining_guesses=1,
                ongoing=False,
            )
            db.session.add(quiz_result)
            db.session.commit()

            user_id = user.id
            db.session.delete(user)
            db.session.commit()

            self.assertIsNone(db.session.get(User, user_id))
            self.assertIsNone(QuizResult.query.filter_by(user_id=user_id).first())
            self.assertIsNotNone(db.session.get(Destination, destination.id))

    def test_user_email_must_be_unique(self):
        with app.app_context():
            user1 = User(email="unique@example.test", password_hash="hash123")
            user2 = User(email="unique@example.test", password_hash="hash456")
            db.session.add(user1)
            db.session.commit()

            db.session.add(user2)
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()


if __name__ == "__main__":
    unittest.main()
