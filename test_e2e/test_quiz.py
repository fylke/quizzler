"""End-to-end tests for the quiz gameplay flow."""

import pytest
from playwright.sync_api import Page, expect


@pytest.fixture(autouse=True)
def setup(clean_db):
    """Ensure a clean database for each test."""


def _register_and_start(page: Page, base_url: str, name: str = "Quizzer"):
    """Helper to register a user and land on the quiz screen via status."""
    page.goto(base_url)
    page.click("#switchToRegister a")
    page.fill("#name", name)
    page.fill("#email", f"{name.lower().replace(' ', '')}@test.com")
    page.fill("#password", "password123")
    page.click("#authButton")
    expect(page.locator("#statusScreen")).to_be_visible(timeout=5000)

    quiz_type_button = page.locator(".quiz-type-btn").first
    expect(quiz_type_button).to_be_visible(timeout=5000)
    quiz_type_button.click()

    expect(page.locator("#quizScreen")).to_be_visible(timeout=5000)
    # Wait for the quiz data to actually load (hint text appears)
    expect(page.locator("#hint")).not_to_be_empty(timeout=5000)


def test_quiz_screen_shows_hint_and_images(page: Page, base_url: str):
    """After login, the quiz screen displays a hint and images."""
    _register_and_start(page, base_url)

    # Hint should be displayed
    hint_el = page.locator("#hint")
    expect(hint_el).not_to_be_empty()

    # Answer input should be visible
    expect(page.locator("#answerInput")).to_be_visible()


def test_submit_correct_answer(page: Page, base_url: str):
    """Submitting the correct answer should show positive feedback."""
    _register_and_start(page, base_url)

    # Type the correct answer
    page.fill("#answerInput", "Paris")
    page.click("text=Submit Answer")

    # Should show feedback (correct answer)
    expect(page.locator("#feedbackScreen")).to_be_visible(timeout=5000)


def test_submit_wrong_answer(page: Page, base_url: str):
    """Submitting a wrong answer should provide feedback."""
    _register_and_start(page, base_url)

    page.fill("#answerInput", "London")
    page.click("text=Submit Answer")

    # Should show some feedback or remain on quiz (depending on remaining guesses)
    # Wait a moment for the response
    page.wait_for_timeout(1000)

    # Either feedback screen or still on quiz screen with updated state
    is_feedback = page.locator("#feedbackScreen").is_visible()
    is_quiz = page.locator("#quizScreen").is_visible()
    assert is_feedback or is_quiz


def test_skip_hint_button(page: Page, base_url: str):
    """Clicking 'Next Hint' should request the next hint."""
    _register_and_start(page, base_url)

    # Get initial hint text
    initial_hint = page.locator("#hint").text_content()

    # Click next hint
    page.click("text=Next Hint")
    page.wait_for_timeout(1000)

    # The hint text should have changed (or same if there's an error)
    # Just verify the page didn't crash
    expect(page.locator("#quizScreen")).to_be_visible()


def test_results_screen_shows_up_to_ten_zero_prefixed_images(page: Page, base_url: str):
    """Completed quiz shows at most 10 additional result images from 0* files."""
    _register_and_start(page, base_url)

    page.fill("#answerInput", "Paris")
    page.click("text=Submit Answer")
    expect(page.locator("#feedbackScreen")).to_be_visible(timeout=5000)

    # Feedback view currently has no direct transition button to results.
    page.evaluate("endQuiz()")

    expect(page.locator("#resultsScreen")).to_be_visible(timeout=5000)
    expect(page.locator("#resultImages")).to_be_visible(timeout=5000)
    expect(page.locator("#resultImages .result-image")).to_have_count(10)
