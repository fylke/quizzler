"""Property-based tests for database URI resolution precedence.

Feature: postgresql-migration, Property 2: Database URI Resolution Precedence

Validates: Requirements 4.1, 4.2, 4.3
"""

import unittest

from hypothesis import given, settings
from hypothesis import strategies as st

from backend import resolve_database_uri

# --- Strategies ---
# Each env var can be: None (unset), empty string, or a non-empty URI string.
uri_state_st = st.one_of(st.none(), st.just(""), st.text(min_size=1))

# A default path is always a non-empty string representing a file path.
default_path_st = st.text(min_size=1)


class TestUriResolutionPrecedence(unittest.TestCase):
    """Property 2: Database URI Resolution Precedence.

    For any combination of QUIZ_DATABASE_URL and DATABASE_URL environment
    variable states (set/non-empty, set/empty, unset), the application SHALL
    resolve the database URI according to the precedence chain:
    QUIZ_DATABASE_URL (if non-empty) > DATABASE_URL (if non-empty) >
    sqlite:///default_path.

    **Validates: Requirements 4.1, 4.2, 4.3**
    """

    @settings(max_examples=8)
    @given(
        quiz_db_url=uri_state_st,
        database_url=uri_state_st,
        default_path=default_path_st,
    )
    def test_precedence_chain(self, quiz_db_url, database_url, default_path):
        """The resolved URI follows the precedence chain for any input combination."""
        result = resolve_database_uri(
            quiz_db_url=quiz_db_url,
            database_url=database_url,
            default_path=default_path,
        )

        # Determine expected result per the precedence chain
        if quiz_db_url:  # non-empty and not None
            expected = quiz_db_url
        elif database_url:  # non-empty and not None
            expected = database_url
        else:
            expected = f"sqlite:///{default_path}"

        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
