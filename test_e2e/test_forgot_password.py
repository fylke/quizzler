"""End-to-end tests for the forgot-password flow."""

import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from playwright.sync_api import Page, expect
from werkzeug.security import generate_password_hash

from backend import app
from backend.models import PasswordResetToken, User, db

# A known raw token we'll seed into the DB for valid-token tests
_RAW_TOKEN = "test-valid-token-for-e2e-abcdef1234567890"
_TOKEN_HASH = hashlib.sha256(_RAW_TOKEN.encode()).hexdigest()

pytestmark = pytest.mark.usefixtures("clean_db")


def _open_login_screen(page: Page, base_url: str) -> None:
    """Start from status page and open login UI via the top-right icon."""
    page.goto(base_url, wait_until="networkidle")
    expect(page.locator("#statusLoginLink")).to_be_visible()
    page.click("#statusLoginLink")
    expect(page.locator("#welcomeScreen")).not_to_have_class(".*\\bhidden\\b.*")
    expect(page.locator("#forgotPasswordLink")).to_be_visible()


@pytest.fixture(autouse=True)
def clear_reset_tokens():
    """Ensure a clean database for each test (including reset tokens)."""
    with app.app_context():
        PasswordResetToken.query.delete()
        db.session.commit()
    yield


@pytest.fixture(autouse=True)
def mock_email_service():
    """Mock the email service so e2e tests don't need real SMTP."""
    with patch("backend.routes_auth.send_password_reset_email") as mock_send:
        yield mock_send


@pytest.fixture()
def seeded_user():
    """Create a test user and return their info."""
    with app.app_context():
        user = User(
            email="resetuser@example.com",
            password_hash=generate_password_hash("oldpassword123"),
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    return {"id": user_id, "email": "resetuser@example.com"}


@pytest.fixture()
def seeded_valid_token(seeded_user):
    """Seed a valid (non-expired, non-consumed) reset token into the DB."""
    with app.app_context():
        now = datetime.now(UTC).replace(tzinfo=None)
        token = PasswordResetToken(
            user_id=seeded_user["id"],
            token_hash=_TOKEN_HASH,
            created_at=now,
            expires_at=now + timedelta(minutes=15),
            consumed=False,
        )
        db.session.add(token)
        db.session.commit()
    return _RAW_TOKEN


# ── Modal Tests (Login Page) ────────────────────────────────────────────


def test_forgot_password_link_visible(page: Page, base_url: str):
    """The 'Forgot password?' link is visible on the login screen."""
    _open_login_screen(page, base_url)
    link = page.locator("#forgotPasswordLink")
    expect(link).to_be_visible()
    expect(link).to_have_text("Forgot password?")


def test_clicking_link_opens_modal_without_navigation(page: Page, base_url: str):
    """Clicking the link opens the modal without navigating away (URL unchanged)."""
    _open_login_screen(page, base_url)
    url_before = page.url

    page.click("#forgotPasswordLink")

    modal = page.locator("#forgotPasswordModal")
    expect(modal).to_be_visible()
    assert page.url == url_before


def test_submit_empty_email_shows_inline_error(page: Page, base_url: str):
    """Submitting an empty email shows inline error, no network request made."""
    _open_login_screen(page, base_url)
    page.click("#forgotPasswordLink")

    # Track network requests to /api/forgot-password
    requests_made = []
    page.on(
        "request",
        lambda req: (
            requests_made.append(req.url) if "forgot-password" in req.url else None
        ),
    )

    # Submit with empty email
    page.click("#forgotPasswordSubmitBtn")

    # Error should be visible
    error = page.locator("#resetEmailError")
    expect(error).not_to_be_empty()

    # No network request should have been made
    assert len(requests_made) == 0


def test_submit_valid_email_shows_confirmation(page: Page, base_url: str, seeded_user):
    """Submitting a valid email shows the confirmation message inside the modal."""
    _open_login_screen(page, base_url)
    page.click("#forgotPasswordLink")

    page.fill("#resetEmail", seeded_user["email"])
    page.click("#forgotPasswordSubmitBtn")

    # Confirmation message should appear
    confirmation = page.locator("#forgotPasswordConfirmation")
    expect(confirmation).to_be_visible(timeout=5000)
    expect(confirmation).to_contain_text("reset link has been sent")


def test_escape_key_closes_modal_and_returns_focus(page: Page, base_url: str):
    """Escape key closes the modal and returns focus to the 'Forgot password?' link."""
    _open_login_screen(page, base_url)
    page.click("#forgotPasswordLink")

    modal = page.locator("#forgotPasswordModal")
    expect(modal).to_be_visible()

    # Press Escape
    page.keyboard.press("Escape")

    expect(modal).to_be_hidden()

    # Focus should return to the forgot password link
    focused_id = page.evaluate("document.activeElement.id")
    assert focused_id == "forgotPasswordLink"


def test_tab_focus_trap_within_modal(page: Page, base_url: str):
    """Tab key traps focus within the modal (last element wraps to first)."""
    _open_login_screen(page, base_url)
    page.click("#forgotPasswordLink")

    # Focus starts on #resetEmail
    focused_id = page.evaluate("document.activeElement.id")
    assert focused_id == "resetEmail"

    # Tab to Submit button
    page.keyboard.press("Tab")
    focused_id = page.evaluate("document.activeElement.id")
    assert focused_id == "forgotPasswordSubmitBtn"

    # Tab to Cancel button
    page.keyboard.press("Tab")
    focused_id = page.evaluate("document.activeElement.id")
    assert focused_id == "forgotPasswordCancelBtn"

    # Tab from last element should wrap to first (resetEmail)
    page.keyboard.press("Tab")
    focused_id = page.evaluate("document.activeElement.id")
    assert focused_id == "resetEmail"


# ── Reset Password Page Tests ────────────────────────────────────────────


def test_invalid_token_shows_error_with_link_back(page: Page, base_url: str):
    """Navigating to /reset-password?token=invalid shows the error message with a link back."""
    page.goto(f"{base_url}/reset-password?token=invalidtoken123")

    error_state = page.locator("#errorState")
    expect(error_state).to_be_visible(timeout=5000)
    expect(error_state).to_contain_text("no longer valid")

    # Should have a link back (to request a new email)
    link_back = error_state.locator("a[href='/']")
    expect(link_back).to_be_visible()


def test_valid_token_shows_password_form(page: Page, base_url: str, seeded_valid_token):
    """Navigating to /reset-password?token=<valid> shows the new-password form."""
    page.goto(f"{base_url}/reset-password?token={seeded_valid_token}")

    form_state = page.locator("#formState")
    expect(form_state).to_be_visible(timeout=5000)

    # Should have new password and confirm password inputs
    expect(page.locator("#newPassword")).to_be_visible()
    expect(page.locator("#confirmPassword")).to_be_visible()


def test_mismatched_passwords_shows_inline_error(
    page: Page, base_url: str, seeded_valid_token
):
    """Submitting mismatched passwords on the reset form shows the inline error."""
    page.goto(f"{base_url}/reset-password?token={seeded_valid_token}")

    form_state = page.locator("#formState")
    expect(form_state).to_be_visible(timeout=5000)

    page.fill("#newPassword", "newpassword123")
    page.fill("#confirmPassword", "differentpassword")

    # Submit the form
    page.click('#formState button[type="submit"]')

    # Inline error should show
    error = page.locator("#resetFormError")
    expect(error).to_contain_text("do not match")


def test_successful_reset_shows_success_and_login_link(
    page: Page, base_url: str, seeded_valid_token
):
    """Successfully resetting password shows success message and login link."""
    page.goto(f"{base_url}/reset-password?token={seeded_valid_token}")

    form_state = page.locator("#formState")
    expect(form_state).to_be_visible(timeout=5000)

    page.fill("#newPassword", "mynewpassword123")
    page.fill("#confirmPassword", "mynewpassword123")

    # Submit the form
    page.click('#formState button[type="submit"]')

    # Success message should appear
    success_state = page.locator("#successState")
    expect(success_state).to_be_visible(timeout=5000)
    expect(success_state).to_contain_text("password has been reset")

    # Should have a link to login
    login_link = success_state.locator("a[href='/']")
    expect(login_link).to_be_visible()
    expect(login_link).to_contain_text("login")
