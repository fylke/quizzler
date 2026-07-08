"""End-to-end tests for wrong guess animation feedback.

Validates Requirements: 1.1, 2.1, 3.1, 3.2, 5.1, 5.2, 5.3
"""

import re

import pytest
from playwright.sync_api import Page, expect


@pytest.fixture(autouse=True)
def setup(clean_db):
    """Ensure a clean database for each test."""


def _register_and_start(page: Page, base_url: str):
    """Register a user and navigate to the quiz screen."""
    page.goto(base_url)
    page.click("#statusLoginLink")
    expect(page.locator("#welcomeScreen")).to_be_visible(timeout=5000)
    page.click("#switchToRegister a")
    page.fill("#name", "Tester")
    page.fill("#email", "tester@test.com")
    page.fill("#password", "password123")
    page.click("#authButton")
    expect(page.locator("#statusScreen")).to_be_visible(timeout=5000)

    quiz_type_button = page.locator(".quiz-type-btn").first
    expect(quiz_type_button).to_be_visible(timeout=5000)
    quiz_type_button.click()

    expect(page.locator("#quizScreen")).to_be_visible(timeout=5000)
    expect(page.locator("#hint")).not_to_be_empty(timeout=5000)


def test_wrong_answer_adds_animation_classes(page: Page, base_url: str):
    """Submit wrong answer → quiz screen has .wrong-guess-shake and .wrong-guess-glow classes."""
    _register_and_start(page, base_url)

    page.fill("#answerInput", "London")
    page.click("text=Submit Answer")

    quiz_screen = page.locator("#quizScreen")
    # Animation classes should be applied to the quiz screen after wrong answer
    expect(quiz_screen).to_have_class(re.compile(r"wrong-guess-shake"), timeout=3000)
    expect(quiz_screen).to_have_class(re.compile(r"wrong-guess-glow"), timeout=3000)


def test_empty_input_animates_without_alert(page: Page, base_url: str):
    """Submit empty input → animation plays on quiz screen, no alert dialog appears."""
    _register_and_start(page, base_url)

    # Track if any dialog (alert) appears
    dialog_appeared = []
    page.on("dialog", lambda dialog: (dialog_appeared.append(True), dialog.dismiss()))

    # Clear input and submit
    page.fill("#answerInput", "")
    page.click("text=Submit Answer")

    quiz_screen = page.locator("#quizScreen")
    # Animation classes should be applied to quiz screen
    expect(quiz_screen).to_have_class(re.compile(r"wrong-guess-shake"), timeout=3000)
    expect(quiz_screen).to_have_class(re.compile(r"wrong-guess-glow"), timeout=3000)

    # No alert dialog should have appeared
    assert len(dialog_appeared) == 0, "Alert dialog appeared but should not have"


def test_animation_ends_classes_removed_input_usable(page: Page, base_url: str):
    """Animation ends → classes removed from quiz screen, input usable."""
    _register_and_start(page, base_url)

    page.fill("#answerInput", "London")
    page.click("text=Submit Answer")

    quiz_screen = page.locator("#quizScreen")
    # Verify animation starts
    expect(quiz_screen).to_have_class(re.compile(r"wrong-guess-shake"), timeout=3000)

    # Wait for animation to complete (600ms animation + 1000ms fallback + buffer)
    page.wait_for_timeout(1500)

    # Classes should be removed after animation ends
    expect(quiz_screen).not_to_have_class(re.compile(r"wrong-guess-shake"), timeout=3000)
    expect(quiz_screen).not_to_have_class(re.compile(r"wrong-guess-glow"), timeout=3000)

    # Input should still be usable
    input_el = page.locator("#answerInput")
    expect(input_el).to_be_enabled()
    page.fill("#answerInput", "test typing")
    assert page.locator("#answerInput").input_value() == "test typing"


def test_reduced_motion_static_border_only(page: Page, base_url: str):
    """With prefers-reduced-motion emulated → static red border on quiz screen only, no motion classes."""
    # Emulate reduced motion BEFORE navigating
    page.emulate_media(reduced_motion="reduce")

    _register_and_start(page, base_url)

    page.fill("#answerInput", "London")
    page.click("text=Submit Answer")

    quiz_screen = page.locator("#quizScreen")

    # Should have static class instead of animation classes
    expect(quiz_screen).to_have_class(re.compile(r"wrong-guess-static"), timeout=3000)

    # Should NOT have motion-based animation classes
    expect(quiz_screen).not_to_have_class(re.compile(r"wrong-guess-shake"))
    expect(quiz_screen).not_to_have_class(re.compile(r"wrong-guess-glow"))
