"""Property-based tests for status screen statistics using Hypothesis."""

import unittest

from hypothesis import given, settings
from hypothesis import strategies as st

from backend.stats import compute_stats

# --- Strategies for generating quiz result dicts ---

quiz_result_st = st.fixed_dictionaries(
    {
        "hint_difficulty": st.integers(min_value=1, max_value=5),
        "remaining_guesses": st.integers(min_value=0, max_value=3),
        "destination_id": st.integers(min_value=1, max_value=10000),
    }
)


# Feature: status-screen-stats, Property 1: Score computation correctness
class PropertyTestScoreComputation(unittest.TestCase):
    """Property 1: Score computation correctness.

    For any non-empty list of completed quiz results (each with hint_difficulty
    in [1,5] and remaining_guesses in [0,3]), the cumulative score SHALL equal
    the sum of (hint_difficulty × remaining_guesses) for all results, and the
    average score SHALL equal round(cumulative_score / count, 1).

    **Validates: Requirements 1.1, 1.4, 5.3**
    """

    @settings(max_examples=8, deadline=5000)
    @given(
        results=st.lists(
            quiz_result_st,
            min_size=1,
            max_size=30,
        )
    )
    def test_score_computation_correctness(self, results):
        """Cumulative score equals sum of individual scores and average is correctly rounded."""
        stats = compute_stats(results)

        expected_cumulative = sum(
            r["hint_difficulty"] * r["remaining_guesses"] for r in results
        )
        expected_average = round(expected_cumulative / len(results), 1)

        self.assertEqual(stats["cumulativeScore"], expected_cumulative)
        self.assertEqual(stats["averageScore"], expected_average)


# Feature: status-screen-stats, Property 2: Best score is the maximum individual score
class PropertyTestBestScore(unittest.TestCase):
    """Property 2: Best score is the maximum individual score.

    For any non-empty list of completed quiz results, the best score SHALL equal
    the maximum value of (hint_difficulty × remaining_guesses) among all results.

    **Validates: Requirements 1.5, 5.3**
    """

    @settings(max_examples=8, deadline=5000)
    @given(
        results=st.lists(
            quiz_result_st,
            min_size=1,
            max_size=30,
        )
    )
    def test_best_score_is_maximum(self, results):
        """Best score equals max(hint_difficulty * remaining_guesses)."""
        stats = compute_stats(results)

        expected_best = max(
            r["hint_difficulty"] * r["remaining_guesses"] for r in results
        )

        self.assertEqual(stats["bestScore"], expected_best)


# Feature: status-screen-stats, Property 3: Accuracy rate formula
class PropertyTestAccuracyRate(unittest.TestCase):
    """Property 3: Accuracy rate formula.

    For any non-empty list of completed quiz results, the accuracy rate SHALL
    equal round((count of results where remaining_guesses > 0) / total count × 100),
    and the result SHALL be an integer between 0 and 100 inclusive.

    **Validates: Requirements 1.6, 5.3**
    """

    @settings(max_examples=8, deadline=5000)
    @given(
        results=st.lists(
            quiz_result_st,
            min_size=1,
            max_size=30,
        )
    )
    def test_accuracy_rate_formula(self, results):
        """Accuracy rate equals rounded percentage of successful results."""
        stats = compute_stats(results)

        successful = sum(1 for r in results if r["remaining_guesses"] > 0)
        expected_accuracy = round(successful / len(results) * 100)

        self.assertEqual(stats["accuracyRate"], expected_accuracy)
        self.assertIsInstance(stats["accuracyRate"], int)
        self.assertGreaterEqual(stats["accuracyRate"], 0)
        self.assertLessEqual(stats["accuracyRate"], 100)


# Feature: status-screen-stats, Property 4: Current streak counts consecutive recent successes
class PropertyTestCurrentStreak(unittest.TestCase):
    """Property 4: Current streak counts consecutive recent successes.

    For any list of completed quiz results with unique destination_ids, when
    sorted by descending destination_id, the current streak SHALL equal the count
    of consecutive results from the front where remaining_guesses > 0, stopping
    at the first result where remaining_guesses equals 0.

    **Validates: Requirements 1.7, 5.3**
    """

    @settings(max_examples=8, deadline=5000)
    @given(
        results=st.lists(
            quiz_result_st,
            min_size=1,
            max_size=30,
            unique_by=lambda r: r["destination_id"],
        )
    )
    def test_current_streak_consecutive_successes(self, results):
        """Current streak counts consecutive successes from front of desc-sorted list."""
        stats = compute_stats(results)

        sorted_results = sorted(
            results, key=lambda r: r["destination_id"], reverse=True
        )
        expected_streak = 0
        for r in sorted_results:
            if r["remaining_guesses"] > 0:
                expected_streak += 1
            else:
                break

        self.assertEqual(stats["currentStreak"], expected_streak)


# Feature: status-screen-stats, Property 5: Ongoing records are excluded from statistics
class PropertyTestOngoingExcluded(unittest.TestCase):
    """Property 5: Ongoing records are excluded from statistics.

    For any mixed list of quiz results (some ongoing=True, some ongoing=False),
    computing stats on only the ongoing=False subset produces correct results.
    This validates the filtering contract that the caller must apply before
    passing records to compute_stats.

    **Validates: Requirements 5.1, 5.2**
    """

    @settings(max_examples=8, deadline=5000)
    @given(
        results=st.lists(
            st.tuples(
                quiz_result_st,
                st.booleans(),  # ongoing flag
            ),
            min_size=0,
            max_size=30,
        )
    )
    def test_ongoing_records_excluded(self, results):
        """Stats from filtering ongoing=False equal stats from compute_stats on that subset."""
        # Build the full mixed list with ongoing flags
        all_records = []
        for result_dict, ongoing in results:
            record = dict(result_dict)
            record["ongoing"] = ongoing
            all_records.append(record)

        # Filter to only completed (ongoing=False) records, as the API route does
        completed = [r for r in all_records if not r["ongoing"]]

        # Strip the ongoing key before passing to compute_stats (it doesn't expect it)
        completed_for_stats = [
            {
                "hint_difficulty": r["hint_difficulty"],
                "remaining_guesses": r["remaining_guesses"],
                "destination_id": r["destination_id"],
            }
            for r in completed
        ]

        # Compute stats on the filtered subset
        stats = compute_stats(completed_for_stats)

        # Independently verify the stats are correctly computed from the completed subset
        if not completed_for_stats:
            self.assertEqual(stats["cumulativeScore"], 0)
            self.assertEqual(stats["quizzesCompleted"], 0)
            self.assertEqual(stats["averageScore"], 0)
            self.assertEqual(stats["bestScore"], 0)
            self.assertEqual(stats["accuracyRate"], 0)
            self.assertEqual(stats["currentStreak"], 0)
        else:
            scores = [
                r["hint_difficulty"] * r["remaining_guesses"]
                for r in completed_for_stats
            ]
            expected_cumulative = sum(scores)
            expected_count = len(completed_for_stats)
            expected_average = round(expected_cumulative / expected_count, 1)
            expected_best = max(scores)
            successful = sum(
                1 for r in completed_for_stats if r["remaining_guesses"] > 0
            )
            expected_accuracy = round(successful / expected_count * 100)

            # Current streak: sort by descending destination_id, count consecutive successes
            sorted_completed = sorted(
                completed_for_stats, key=lambda r: r["destination_id"], reverse=True
            )
            expected_streak = 0
            for r in sorted_completed:
                if r["remaining_guesses"] > 0:
                    expected_streak += 1
                else:
                    break

            self.assertEqual(stats["cumulativeScore"], expected_cumulative)
            self.assertEqual(stats["quizzesCompleted"], expected_count)
            self.assertEqual(stats["averageScore"], expected_average)
            self.assertEqual(stats["bestScore"], expected_best)
            self.assertEqual(stats["accuracyRate"], expected_accuracy)
            self.assertEqual(stats["currentStreak"], expected_streak)


if __name__ == "__main__":
    unittest.main()
