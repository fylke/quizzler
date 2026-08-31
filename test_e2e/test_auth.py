"""End-to-end tests for authentication flows."""

import pytest
from playwright.sync_api import Page, expect


@pytest.fixture(autouse=True)
def setup(clean_db):
    """Ensure a clean database for each test."""


def _open_login_screen(page: Page, base_url: str) -> None:
    """Navigate to login UI from the default status-first landing screen."""
    page.goto(base_url, wait_until="networkidle")
    expect(page.locator("#statusLoginLink")).to_be_visible()
    page.click("#statusLoginLink")
    expect(page.locator("#welcomeScreen")).not_to_have_class(".*\\bhidden\\b.*")


def test_status_screen_loads_with_login_link(page: Page, base_url: str):
    """The status screen is shown first in guest mode, with a login icon link."""
    page.goto(base_url)

    expect(page.locator("#statusScreen")).to_be_visible(timeout=5000)
    expect(page.locator("#guestRestrictionsStatus")).to_be_hidden(timeout=5000)
    expect(page.locator("#statusLoginLink")).to_be_visible()


def test_register_new_user(page: Page, base_url: str):
    """A new user can register and is taken to the status screen."""
    _open_login_screen(page, base_url)

    # Switch to register mode
    page.click("#switchToRegister a")

    # Fill in registration form
    page.fill("#email", "test@example.com")
    page.fill("#password", "password123")
    page.click("#authButton")

    # Should navigate to status screen
    expect(page.locator("#statusScreen")).to_be_visible(timeout=5000)
    expect(page.locator("#guestRestrictionsStatus")).to_be_hidden()


def test_continue_as_guest_shows_status_and_restrictions(page: Page, base_url: str):
    """Guest mode is default and shows restrictions on the stats screen."""
    page.goto(base_url)

    expect(page.locator("#statusScreen")).to_be_visible(timeout=5000)
    page.click("#statsBtn")
    expect(page.locator("#statsScreen")).to_be_visible(timeout=5000)
    expect(page.locator("#guestRestrictionsStatus")).to_be_visible()
    expect(page.locator("#guestRestrictionsStatus a")).to_have_text("create an account")


def test_guest_upgrade_to_registered_user_hides_guest_banner(page: Page, base_url: str):
    """The guest-mode banner should disappear on stats after upgrading to an authenticated user."""
    page.goto(base_url)

    expect(page.locator("#statusScreen")).to_be_visible(timeout=5000)
    page.click("#statsBtn")
    expect(page.locator("#statsScreen")).to_be_visible(timeout=5000)
    expect(page.locator("#guestRestrictionsStatus")).to_be_visible()

    page.click("#guestRestrictionsStatus a")
    expect(page.locator("#welcomeScreen")).not_to_have_class(".*\\bhidden\\b.*")

    expect(page.locator("#authButton")).to_have_text("Create Account")
    page.fill("#email", "guest-upgrade@example.com")
    page.fill("#password", "password123")
    page.click("#authButton")

    expect(page.locator("#statusScreen")).to_be_visible(timeout=5000)
    page.click("#statsBtn")
    expect(page.locator("#statsScreen")).to_be_visible(timeout=5000)
    expect(page.locator("#guestRestrictionsStatus")).to_be_hidden()


def test_login_with_invalid_credentials(page: Page, base_url: str):
    """Login with wrong credentials should show an error."""
    _open_login_screen(page, base_url)

    page.fill("#email", "nonexistent@example.com")
    page.fill("#password", "wrongpassword")
    page.click("#authButton")

    # Should remain on the welcome screen (quiz screen should not appear)
    expect(page.locator("#quizScreen")).to_be_hidden()
    expect(page.locator("#welcomeScreen")).not_to_have_class(".*\\bhidden\\b.*")


def test_toggle_between_login_and_register(page: Page, base_url: str):
    """User can switch between login and register modes."""
    _open_login_screen(page, base_url)

    # Initially in login mode
    expect(page.locator("#switchToRegister")).to_be_visible()
    expect(page.locator("#authButton")).to_have_text("Log In")

    # Switch to register
    page.click("#switchToRegister a")
    expect(page.locator("#switchToLogin")).to_be_visible()
    expect(page.locator("#authButton")).to_have_text("Create Account")

    # Switch back to login
    page.click("#switchToLogin a")
    expect(page.locator("#switchToRegister")).to_be_visible()
    expect(page.locator("#authButton")).to_have_text("Log In")
