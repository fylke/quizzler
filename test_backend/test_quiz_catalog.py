"""Tests for globally unique quiz identities."""

import os
import unittest

os.environ.setdefault("QUIZ_DATABASE_URL", "sqlite:///:memory:")

from backend import app
from backend.models import Destination, QuizIdentity, db
from backend.quiz_catalog import (
    get_or_create_quiz_identity,
    public_quiz_id,
    resolve_quiz_id,
    synchronize_quiz_identities,
)


class QuizCatalogTestCase(unittest.TestCase):
    def setUp(self):
        app.testing = True
        with app.app_context():
            db.drop_all()
            db.create_all()
            db.session.add_all(
                [
                    self._destination(1, "Paris"),
                    self._destination(2, "Tokyo"),
                ]
            )
            db.session.commit()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    @staticmethod
    def _destination(destination_id, name):
        return Destination(
            id=destination_id,
            name=name,
            hint1="Hint 1",
            hint2="Hint 2",
            hint3="Hint 3",
            hint4="Hint 4",
            hint5="Hint 5",
            correct_answers=[name.lower()],
        )

    def test_synchronize_backfills_once_with_uuid_v4_values(self):
        with app.app_context():
            self.assertEqual(synchronize_quiz_identities(), 2)
            db.session.commit()

            identities = QuizIdentity.query.order_by(QuizIdentity.source_id).all()
            self.assertEqual(len(identities), 2)
            self.assertEqual(
                [
                    public_quiz_id("countries", identity.source_id)
                    for identity in identities
                ],
                ["c1", "c2"],
            )

            self.assertEqual(synchronize_quiz_identities(), 0)
            db.session.commit()
            self.assertEqual(QuizIdentity.query.count(), 2)

    def test_get_or_create_preserves_source_identity(self):
        with app.app_context():
            first = get_or_create_quiz_identity("countries", 1)
            db.session.commit()
            guid = first.guid

            second = get_or_create_quiz_identity("countries", 1)
            self.assertEqual(second.guid, guid)
            self.assertEqual(resolve_quiz_id("c1").source_id, 1)
            self.assertEqual(public_quiz_id("countries", 1), "c1")
            self.assertIsNone(resolve_quiz_id(guid))
            self.assertIsNone(resolve_quiz_id("not-a-quiz-id"))


if __name__ == "__main__":
    unittest.main()
