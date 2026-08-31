"""End-to-end tests for the admin panel."""

import pytest
from playwright.sync_api import Page, expect
from werkzeug.security import generate_password_hash

pytestmark = pytest.mark.usefixtures("clean_db")


@pytest.fixture()
def admin_page(clean_db, page: Page, base_url: str):
    """Register a user, make them admin, log in as admin."""
    from backend import app
    from backend.models import User, db

    # Create admin user directly in DB
    with app.app_context():
        user = User(
            email="admin@test.com",
            password_hash=generate_password_hash("adminpass123"),
            is_admin=True,
        )
        db.session.add(user)
        db.session.commit()

    # Login via UI
    page.goto(base_url)
    page.click("#statusLoginLink")
    expect(page.locator("#welcomeScreen")).to_be_visible(timeout=5000)
    page.fill("#email", "admin@test.com")
    page.fill("#password", "adminpass123")
    page.click("#authButton")
    expect(page.locator("#statusScreen")).to_be_visible(timeout=5000)

    return page


@pytest.fixture()
def regular_page(clean_db, page: Page, base_url: str):
    """Register a regular (non-admin) user and log in."""
    from backend import app
    from backend.models import User, db

    with app.app_context():
        user = User(
            email="regular@test.com",
            password_hash=generate_password_hash("password123"),
            is_admin=False,
        )
        db.session.add(user)
        db.session.commit()

    page.goto(base_url)
    page.click("#statusLoginLink")
    expect(page.locator("#welcomeScreen")).to_be_visible(timeout=5000)
    page.fill("#email", "regular@test.com")
    page.fill("#password", "password123")
    page.click("#authButton")
    expect(page.locator("#statusScreen")).to_be_visible(timeout=5000)

    return page


def test_admin_link_visible_for_admin_user(admin_page: Page):
    """Admin user sees the 'Admin Panel' button on the status screen."""
    admin_link = admin_page.locator("#adminLink")
    expect(admin_link).to_be_visible()
    expect(admin_link).to_have_attribute("aria-label", "Admin panel")


def test_admin_link_hidden_for_regular_user(regular_page: Page):
    """Regular user does NOT see the admin link."""
    admin_link = regular_page.locator("#adminLink")
    expect(admin_link).to_be_hidden()


def test_navigate_to_admin_screen(admin_page: Page):
    """Clicking admin link shows admin screen with header and destination list."""
    admin_page.click("#adminLink")
    expect(admin_page.locator("#adminScreen")).to_be_visible(timeout=3000)
    expect(admin_page.locator("#adminScreen h1")).to_have_text(
        "🔧 Admin: Quiz Management"
    )


def test_admin_screen_shows_destination_list(admin_page: Page):
    """Admin screen lists the seeded 'Paris' destination."""
    admin_page.click("#adminLink")
    expect(admin_page.locator("#adminScreen")).to_be_visible(timeout=3000)

    # Wait for destination list to load
    dest_item = admin_page.locator(".admin-dest-name")
    expect(dest_item.first).to_be_visible(timeout=3000)
    expect(dest_item.first).to_have_text("Paris")


def test_admin_screen_shows_destination_count(admin_page: Page):
    """Shows 'Total destinations: 1'."""
    admin_page.click("#adminLink")
    expect(admin_page.locator("#adminScreen")).to_be_visible(timeout=3000)

    count_el = admin_page.locator("#adminDestCount")
    expect(count_el).to_have_text("Total destinations: 1", timeout=3000)


def test_back_to_status_button(admin_page: Page):
    """Clicking 'Back to Main' returns to status screen."""
    admin_page.click("#adminLink")
    expect(admin_page.locator("#adminScreen")).to_be_visible(timeout=3000)

    admin_page.locator("#adminScreen button", has_text="Back to Main").click()
    expect(admin_page.locator("#statusScreen")).to_be_visible(timeout=3000)
    expect(admin_page.locator("#adminScreen")).to_be_hidden()


def test_add_destination_form(admin_page: Page):
    """Clicking 'Add New Destination' shows the form with correct fields."""
    admin_page.click("#adminLink")
    expect(admin_page.locator("#adminScreen")).to_be_visible(timeout=3000)

    admin_page.locator("button", has_text="Add New Destination").click()
    expect(admin_page.locator("#adminForm")).to_be_visible()
    expect(admin_page.locator("#adminFormTitle")).to_have_text("Add New Destination")

    # Verify form fields exist
    expect(admin_page.locator("#adminDestName")).to_be_visible()
    expect(admin_page.locator("#adminHint1")).to_be_visible()
    expect(admin_page.locator("#adminHint2")).to_be_visible()
    expect(admin_page.locator("#adminHint3")).to_be_visible()
    expect(admin_page.locator("#adminHint4")).to_be_visible()
    expect(admin_page.locator("#adminHint5")).to_be_visible()


def test_create_destination(admin_page: Page):
    """Fill out form, submit, see success message and new destination in list."""
    admin_page.click("#adminLink")
    expect(admin_page.locator("#adminScreen")).to_be_visible(timeout=3000)

    admin_page.locator("button", has_text="Add New Destination").click()
    expect(admin_page.locator("#adminForm")).to_be_visible()

    # Fill out the form
    admin_page.fill("#adminDestName", "Tokyo")
    admin_page.fill("#adminHint1", "This city hosted the 2020 Olympics")
    admin_page.fill("#adminHint2", "It is the capital of Japan")
    admin_page.fill("#adminHint3", "Famous for cherry blossoms")
    admin_page.fill("#adminHint4", "Has a famous crossing in Shibuya")
    admin_page.fill("#adminHint5", "Known for sushi and ramen")

    # Fill in image URLs (2 already exist by default)
    image_inputs = admin_page.locator("#adminImagesContainer input")
    image_inputs.nth(0).fill("https://example.com/tokyo1.jpg")
    image_inputs.nth(1).fill("https://example.com/tokyo2.jpg")

    # Fill in correct answer
    answer_inputs = admin_page.locator("#adminAnswersContainer input")
    answer_inputs.nth(0).fill("Tokyo")

    # Submit
    admin_page.locator("#adminForm button", has_text="Save").click()

    # Verify success message
    expect(admin_page.locator("#adminSuccess")).to_be_visible(timeout=3000)
    expect(admin_page.locator("#adminSuccess")).to_have_text(
        "Destination created successfully"
    )

    # Verify new destination appears in list
    expect(admin_page.locator("#adminDestCount")).to_have_text(
        "Total destinations: 2", timeout=3000
    )
    dest_names = admin_page.locator(".admin-dest-name")
    expect(dest_names.nth(1)).to_have_text("Tokyo")

    # Clean up: delete the created destination so it doesn't affect other tests
    admin_page.locator(".admin-dest-item").nth(1).locator(
        "button", has_text="Delete"
    ).click()
    expect(admin_page.locator("#adminDeleteDialog")).to_be_visible()
    admin_page.locator("#adminDeleteConfirmBtn").click()
    expect(admin_page.locator("#adminDestCount")).to_have_text(
        "Total destinations: 1", timeout=3000
    )


def test_edit_destination(admin_page: Page):
    """Click Edit on a destination, form populates, submit changes, verify updated."""
    admin_page.click("#adminLink")
    expect(admin_page.locator("#adminScreen")).to_be_visible(timeout=3000)

    # Wait for destination list to load
    expect(admin_page.locator(".admin-dest-item").first).to_be_visible(timeout=3000)

    # Click Edit on Paris
    admin_page.locator(".admin-dest-item").first.locator(
        "button", has_text="Edit"
    ).click()
    expect(admin_page.locator("#adminForm")).to_be_visible(timeout=3000)
    expect(admin_page.locator("#adminFormTitle")).to_have_text("Edit Destination")

    # Verify form is populated with existing data
    expect(admin_page.locator("#adminDestName")).to_have_value("Paris")

    # Change the name
    admin_page.fill("#adminDestName", "Paris Updated")
    image_inputs = admin_page.locator("#adminImagesContainer input")
    image_inputs.nth(0).fill("https://example.com/paris1.jpg")
    image_inputs.nth(1).fill("https://example.com/paris2.jpg")

    # Submit
    admin_page.locator("#adminForm button", has_text="Save").click()

    # Verify success message
    expect(admin_page.locator("#adminSuccess")).to_be_visible(timeout=3000)
    expect(admin_page.locator("#adminSuccess")).to_have_text(
        "Destination updated successfully"
    )

    # Verify updated destination in list
    dest_names = admin_page.locator(".admin-dest-name")
    expect(dest_names.first).to_have_text("Paris Updated", timeout=3000)

    # Restore original name so other tests are not affected
    admin_page.locator(".admin-dest-item").first.locator(
        "button", has_text="Edit"
    ).click()
    expect(admin_page.locator("#adminForm")).to_be_visible(timeout=3000)
    admin_page.fill("#adminDestName", "Paris")
    image_inputs = admin_page.locator("#adminImagesContainer input")
    image_inputs.nth(0).fill("https://example.com/paris1.jpg")
    image_inputs.nth(1).fill("https://example.com/paris2.jpg")
    admin_page.locator("#adminForm button", has_text="Save").click()
    expect(admin_page.locator("#adminSuccess")).to_be_visible(timeout=3000)


def test_delete_destination_with_confirmation(admin_page: Page):
    """Click Delete, confirmation dialog appears with name, confirm deletes it."""
    from backend import app as flask_app
    from backend.models import Destination
    from backend.models import db as flask_db

    admin_page.click("#adminLink")
    expect(admin_page.locator("#adminScreen")).to_be_visible(timeout=3000)

    # Wait for destination list to load
    expect(admin_page.locator(".admin-dest-item").first).to_be_visible(timeout=3000)

    # Get the current destination name and count for assertions
    dest_name = admin_page.locator(".admin-dest-name").first.inner_text()
    count_text = admin_page.locator("#adminDestCount").inner_text()
    initial_count = int(count_text.split(": ")[1])

    # Click Delete on the first destination
    admin_page.locator(".admin-dest-item").first.locator(
        "button", has_text="Delete"
    ).click()

    # Verify confirmation dialog shows the destination name
    dialog = admin_page.locator("#adminDeleteDialog")
    expect(dialog).to_be_visible()
    expect(admin_page.locator("#adminDeleteName")).to_have_text(dest_name)

    # Confirm deletion
    admin_page.locator("#adminDeleteConfirmBtn").click()

    # Verify destination is removed
    expect(admin_page.locator("#adminSuccess")).to_be_visible(timeout=3000)
    expect(admin_page.locator("#adminSuccess")).to_have_text(
        "Destination deleted successfully"
    )
    expected_count = initial_count - 1
    expect(admin_page.locator("#adminDestCount")).to_have_text(
        f"Total destinations: {expected_count}", timeout=3000
    )

    # Restore the seeded destination so other tests are not affected
    with flask_app.app_context():
        if not flask_db.session.get(Destination, 1):
            dest = Destination(
                id=1,
                name="Paris",
                hint1="This city is famous for a tower built in 1889.",
                hint2="It's the capital of France.",
                hint3="Known as the City of Light.",
                hint4="Home to the Louvre museum.",
                hint5="Located on the Seine river.",
                correct_answers=["paris", "paris, france"],
            )
            flask_db.session.add(dest)
            flask_db.session.commit()


def test_delete_destination_cancel(admin_page: Page):
    """Click Delete, cancel in dialog, destination remains."""
    admin_page.click("#adminLink")
    expect(admin_page.locator("#adminScreen")).to_be_visible(timeout=3000)

    # Wait for destination list to load
    expect(admin_page.locator(".admin-dest-item").first).to_be_visible(timeout=3000)

    # Get the current destination name for assertion
    dest_name = admin_page.locator(".admin-dest-name").first.inner_text()

    # Click Delete on the first destination
    admin_page.locator(".admin-dest-item").first.locator(
        "button", has_text="Delete"
    ).click()

    # Verify confirmation dialog
    dialog = admin_page.locator("#adminDeleteDialog")
    expect(dialog).to_be_visible()

    # Cancel deletion
    admin_page.locator("#adminDeleteDialog button", has_text="Cancel").click()

    # Dialog should close
    expect(dialog).to_be_hidden()

    # Destination should still be in the list
    expect(admin_page.locator(".admin-dest-name").first).to_have_text(dest_name)


def test_create_destination_validation_error(admin_page: Page):
    """Submit empty form, error message shown."""
    admin_page.click("#adminLink")
    expect(admin_page.locator("#adminScreen")).to_be_visible(timeout=3000)

    admin_page.locator("button", has_text="Add New Destination").click()
    expect(admin_page.locator("#adminForm")).to_be_visible()

    # Clear the name field and submit without filling required fields
    admin_page.fill("#adminDestName", "")

    # Submit
    admin_page.locator("#adminForm button", has_text="Save").click()

    # Should show error
    expect(admin_page.locator("#adminError")).to_be_visible(timeout=3000)
