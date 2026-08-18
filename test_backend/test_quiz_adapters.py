"""Tests for quiz-type gameplay adapter registration."""

import unittest

from backend.quiz_adapters import CountriesQuizAdapter, get_quiz_adapter
from backend.quiz_types import QuizType, get_quiz_type, validate_registry


class QuizAdapterRegistryTestCase(unittest.TestCase):
    def test_countries_adapter_is_registered(self):
        adapter = get_quiz_adapter("countries")
        self.assertIsInstance(adapter, CountriesQuizAdapter)
        self.assertEqual(get_quiz_type("countries").adapter, adapter.identifier)

    def test_registry_rejects_quiz_type_without_adapter(self):
        quiz_type = QuizType(
            identifier="cities",
            display_name="Cities",
            rules_file="countries.md",
            source_table="cities",
        )

        errors = validate_registry([quiz_type])

        self.assertIn("Quiz adapter not found for 'cities': cities", errors)


if __name__ == "__main__":
    unittest.main()
