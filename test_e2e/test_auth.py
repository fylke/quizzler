"""End-to-end tests for authentication flows."""

import pytest
from playwright.sync_api import Page, expect


@pytest.fixture(autouse=True)
def setup(clean_db):
    """Ensure a clean database for each test."""


def test_welcome_screen_loads(page: Page, base_url: str):
    """The welcome screen should display login form elements."""
    page.goto(base_url)

    expect(page.locator("#authHeading")).to_be_visible()
    expect(page.locator("#email")).to_be_visible()
    expect(page.locator("#password")).to_be_visible()
    expect(page.locator("#authButton")).to_have_text("Log In")


def test_register_new_user(page: Page, base_url: str):
    """A new user can register and is taken to the status screen."""
    page.goto(base_url)

    # Switch to register mode
    page.click("#switchToRegister a")
    expect(page.locator("#name")).to_be_visible()

    # Fill in registration form
    page.fill("#name", "Test User")
    page.fill("#email", "test@example.com")
    page.fill("#password", "password123")
    page.click("#authButton")

    # Should navigate to status screen
    expect(page.locator("#statusScreen")).to_be_visible(timeout=5000)
    expect(page.locator("#guestRestrictionsStatus")).to_be_hidden()


def test_continue_as_guest_shows_status_and_restrictions(page: Page, base_url: str):
    """Guest mode can be entered from the welcome screen and shows restrictions."""
    page.goto(base_url)

    page.click("#guestButton")

    expect(page.locator("#statusScreen")).to_be_visible(timeout=5000)
    expect(page.locator("#guestRestrictionsStatus")).to_be_visible()
    expect(page.locator("#guestUpgradeBtn")).to_be_visible()


def test_guest_upgrade_to_registered_user_hides_guest_banner(page: Page, base_url: str):
    """The guest-mode banner should disappear after upgrading to an authenticated user."""
    page.goto(base_url)

    page.click("#guestButton")
    expect(page.locator("#statusScreen")).to_be_visible(timeout=5000)
    expect(page.locator("#guestRestrictionsStatus")).to_be_visible()

    page.click("#guestUpgradeBtn")
    expect(page.locator("#welcomeScreen")).to_be_visible(timeout=5000)

    page.click("#switchToRegister a")
    page.fill("#name", "Guest Upgrade User")
    page.fill("#email", "guest-upgrade@example.com")
    page.fill("#password", "password123")
    page.click("#authButton")

    expect(page.locator("#statusScreen")).to_be_visible(timeout=5000)
    expect(page.locator("#guestRestrictionsStatus")).to_be_hidden()


def test_login_with_invalid_credentials(page: Page, base_url: str):
    """Login with wrong credentials should show an error."""
    page.goto(base_url)

    page.fill("#email", "nonexistent@example.com")
    page.fill("#password", "wrongpassword")
    page.click("#authButton")

    # Should remain on the welcome screen (quiz screen should not appear)
    expect(page.locator("#quizScreen")).to_be_hidden()
    expect(page.locator("#welcomeScreen")).to_be_visible()


def test_toggle_between_login_and_register(page: Page, base_url: str):
    """User can switch between login and register modes."""
    page.goto(base_url)

    # Initially in login mode - name field has .hidden class
    expect(page.locator("#name")).to_have_class("hidden")
    expect(page.locator("#switchToRegister")).to_be_visible()

    # Switch to register
    page.click("#switchToRegister a")
    expect(page.locator("#name")).not_to_have_class("hidden")
    expect(page.locator("#switchToLogin")).to_be_visible()

    # Switch back to login
    page.click("#switchToLogin a")
    expect(page.locator("#name")).to_have_class("hidden")
