"""Property-based tests for the forgot-password feature.

Feature: forgot-password
Uses Hypothesis with in-memory SQLite — never sends real email.
"""

import email
import hashlib
import os
import re
import unittest
from email.header import decode_header
from unittest.mock import MagicMock, patch

os.environ.setdefault("QUIZ_DATABASE_URL", "sqlite:///:memory:")

from hypothesis import given, settings
from hypothesis import strategies as st

from backend import app
from backend.email_service import send_password_reset_email
from backend.models import PasswordResetToken, User, db
from backend.reset_tokens import consume_token, generate_token, validate_token

# URL-safe base64 alphabet: A-Z, a-z, 0-9, '-', '_'
_URL_SAFE_RE = re.compile(r"^[A-Za-z0-9\-_]+$")


# ---------------------------------------------------------------------------
# Property 1: Token uniqueness and entropy
# Feature: forgot-password, Property 1: Token uniqueness and entropy
# Validates: Requirements 1.1, 2.6
# ---------------------------------------------------------------------------


class PropertyTestTokenUniquenessAndEntropy(unittest.TestCase):
    """Property 1: Token uniqueness and entropy.

    For any two independently generated reset tokens, the raw token strings
    SHALL be distinct, and each token SHALL be URL-safe and at least 43
    characters long (``secrets.token_urlsafe(32)`` encodes 32 bytes of entropy
    as base64url, yielding 43 characters — well above the ≥128-bit requirement).

    **Validates: Requirements 1.1, 2.6**
    """

    def setUp(self):
        app.testing = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        self.ctx = app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    @settings(max_examples=8, deadline=5000)
    @given(st.data())
    def test_token_uniqueness_and_entropy(self, data):
        """Generate 10 tokens; assert all distinct, URL-safe, and len >= 43.

        # Feature: forgot-password, Property 1: Token uniqueness and entropy
        **Validates: Requirements 1.1, 2.6**

        Note: ``secrets.token_urlsafe(32)`` produces 43-character raw tokens
        (32 bytes of entropy base64url-encoded). The ≥43 char assertion validates
        that the implementation uses at least 32 bytes (≥256 bits) of entropy,
        satisfying Requirements 1.1 and 2.6.
        """
        # Reset DB each run to avoid UNIQUE constraint conflicts across hypothesis examples
        db.drop_all()
        db.create_all()

        user = User(
            email="testtoken@example.com",
            password_hash="placeholder_hash",
        )
        db.session.add(user)
        db.session.commit()

        tokens = []
        for _ in range(10):
            raw = generate_token(user)
            tokens.append(raw)

        # All 10 tokens must be distinct
        self.assertEqual(len(set(tokens)), 10, "Tokens must all be unique")

        for token in tokens:
            # Each token must be URL-safe (only A-Z, a-z, 0-9, '-', '_')
            self.assertRegex(
                token,
                _URL_SAFE_RE,
                f"Token is not URL-safe: {token!r}",
            )
            # Each token must be at least 43 characters long
            # (secrets.token_urlsafe(32) encodes 32 bytes → 43 base64url chars)
            self.assertGreaterEqual(
                len(token),
                43,
                f"Token too short ({len(token)} chars): {token!r}",
            )


def _make_user(suffix: str = "") -> User:
    """Create and persist a test user, returning the committed User instance."""
    user = User(
        email=f"testuser{suffix}@example.com",
        password_hash="placeholder_hash",
    )
    db.session.add(user)
    db.session.commit()
    return user


# ---------------------------------------------------------------------------
# Property 2: New token invalidates all prior unused tokens
# Feature: forgot-password, Property 2: New token invalidates all prior unused tokens
# Validates: Requirements 1.3, 2.7
# ---------------------------------------------------------------------------


@settings(max_examples=8, deadline=5000)
@given(k=st.integers(min_value=2, max_value=5))
def test_new_token_invalidates_prior_tokens(k: int) -> None:
    """For any user and k ∈ [2, 5] sequential token generations, only the last
    token passes validate_token(); all prior tokens return None.

    # Feature: forgot-password, Property 2: New token invalidates all prior unused tokens
    Validates: Requirements 1.3, 2.7
    """
    with app.app_context():
        db.drop_all()
        db.create_all()

        user = _make_user()

        # Generate k tokens sequentially, collecting each raw token
        raw_tokens = []
        for _ in range(k):
            raw = generate_token(user)
            raw_tokens.append(raw)

        # Only the last token should be valid
        last_token = raw_tokens[-1]
        prior_tokens = raw_tokens[:-1]

        # The last token must pass validation (return a non-None record)
        assert (
            validate_token(last_token) is not None
        ), f"Expected the last of {k} tokens to be valid, but validate_token() returned None"

        # All prior tokens must be invalidated (return None)
        for i, raw in enumerate(prior_tokens):
            assert validate_token(raw) is None, (
                f"Expected token {i + 1} of {k} (not the last) to be invalidated, "
                f"but validate_token() returned a record"
            )

        db.session.remove()


# ---------------------------------------------------------------------------
# Property 3: Consumed token is rejected on reuse
# Feature: forgot-password, Property 3: Consumed token is rejected on reuse
# Validates: Requirements 2.2, 2.3, 3.7
# ---------------------------------------------------------------------------


@settings(max_examples=8, deadline=5000)
@given(new_password=st.text(min_size=8, max_size=128))
def test_consumed_token_rejected_on_reuse(new_password: str) -> None:
    """A token that has been consumed via consume_token() SHALL be rejected
    on any subsequent validate_token() call — returning None.

    # Feature: forgot-password, Property 3: Consumed token is rejected on reuse
    **Validates: Requirements 2.2, 2.3, 3.7**
    """
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()

        user = _make_user()

        # Step 1: Generate a token
        raw_token = generate_token(user)

        # Step 2: Validate it — must succeed
        record = validate_token(raw_token)
        assert (
            record is not None
        ), "Expected freshly generated token to be valid, but validate_token() returned None"

        # Step 3: Consume the token with a new password
        consume_token(record, new_password)

        # Step 4: Validate the same raw token again — must be rejected (None)
        result = validate_token(raw_token)
        assert result is None, (
            "Expected consumed token to be rejected on reuse, "
            "but validate_token() returned a record instead of None"
        )

        db.session.remove()


# ---------------------------------------------------------------------------
# Property 4: Token hash stored, not plaintext
# Feature: forgot-password, Property 4: Token hash stored, not plaintext
# Validates: Requirements 2.5
# ---------------------------------------------------------------------------


@settings(max_examples=8, deadline=5000)
@given(st.integers(min_value=1, max_value=1))
def test_token_hash_stored_not_plaintext(_dummy: int) -> None:
    """For any generated reset token, the value stored in the token_hash column
    SHALL NOT equal the raw token string, and SHALL equal the hex-encoded
    SHA-256 digest of the raw token.

    # Feature: forgot-password, Property 4: Token hash stored, not plaintext
    **Validates: Requirements 2.5**
    """
    with app.app_context():
        db.drop_all()
        db.create_all()

        user = _make_user()

        # Generate a token and get the raw string
        raw = generate_token(user)

        # Query the stored record from the database
        record = PasswordResetToken.query.filter_by(user_id=user.id).first()
        assert (
            record is not None
        ), "Expected a PasswordResetToken record to be stored for the user"

        # The stored token_hash must NOT be the plaintext raw token
        assert (
            record.token_hash != raw
        ), "token_hash must not equal the raw token — plaintext must never be stored"

        # The stored token_hash must equal sha256(raw).hexdigest()
        expected_hash = hashlib.sha256(raw.encode()).hexdigest()
        assert record.token_hash == expected_hash, (
            f"token_hash mismatch: expected sha256(raw)={expected_hash!r}, "
            f"got {record.token_hash!r}"
        )

        db.session.remove()


# ---------------------------------------------------------------------------
# Property 7: Email body contains required elements
# Feature: forgot-password, Property 7: Email body contains required elements
# Validates: Requirements 4.4
# ---------------------------------------------------------------------------


@settings(max_examples=8, deadline=5000)
@given(
    token=st.text(
        min_size=1,
        max_size=50,
        alphabet=st.characters(whitelist_categories=("L", "N")),
    ),
    base_url=st.from_regex(r"https?://[a-z0-9]+\.[a-z]+", fullmatch=True),
)
def test_email_body_contains_required_elements(token: str, base_url: str) -> None:
    """For any (raw token, reset base URL) pair, the email constructed by
    Email_Service SHALL have a subject containing the phrase "password reset",
    SHALL contain the reset URL with the token, and SHALL contain "15 minutes".

    # Feature: forgot-password, Property 7: Email body contains required elements
    **Validates: Requirements 4.4**
    """
    reset_url = f"{base_url}/reset-password?token={token}"
    to_address = "user@example.com"

    # Set required SMTP env vars so send_password_reset_email doesn't raise
    # EmailServiceError for missing config
    env_vars = {
        "SMTP_HOST": "localhost",
        "SMTP_PORT": "587",
        "SMTP_USERNAME": "testuser",
        "SMTP_PASSWORD": "testpass",
        "SMTP_FROM_ADDRESS": "noreply@example.com",
    }

    with patch.dict(os.environ, env_vars, clear=False):
        with patch("backend.email_service.smtplib.SMTP") as mock_smtp:
            # Set up mock so sendmail captures the email
            mock_instance = MagicMock()
            mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_instance)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

            send_password_reset_email(to_address, reset_url)

            # Extract the email message from the sendmail call
            mock_instance.sendmail.assert_called_once()
            call_args = mock_instance.sendmail.call_args
            raw_message = call_args[0][2]  # Third positional arg is the message string

            # Parse the raw MIME message to properly decode subject and body
            msg = email.message_from_string(raw_message)

            # Decode subject header (handles Q-encoding and B-encoding)
            subject_parts = decode_header(msg["Subject"])
            subject = "".join(
                part.decode(charset or "utf-8") if isinstance(part, bytes) else part
                for part, charset in subject_parts
            )

            # Decode body payload
            body = msg.get_payload(decode=True).decode("utf-8")

            # Subject must contain "password reset" (case-insensitive)
            assert (
                "password reset" in subject.lower()
            ), f"Expected subject to contain 'password reset', got: {subject!r}"

            # Body must contain the reset URL (which includes the token)
            assert reset_url in body, (
                f"Expected body to contain reset URL {reset_url!r}, "
                f"got body:\n{body}"
            )

            # Body must contain "15 minutes"
            assert (
                "15 minutes" in body
            ), f"Expected body to contain '15 minutes', got body:\n{body}"


# ---------------------------------------------------------------------------
# Property 6: Password reset hash correctness
# Feature: forgot-password, Property 6: Password reset hash correctness
# Validates: Requirements 3.1
# ---------------------------------------------------------------------------


from werkzeug.security import check_password_hash

# ---------------------------------------------------------------------------
# Property 5: Password length boundary enforcement
# Feature: forgot-password, Property 5: Password length boundary enforcement
# Validates: Requirements 3.3, 3.4, 3.6
# ---------------------------------------------------------------------------


@settings(max_examples=8, deadline=5000)
@given(password=st.text(min_size=0, max_size=7))
def test_password_too_short_returns_400(password: str) -> None:
    """For any string with length < 8, submitting it as the new password to
    POST /api/reset-password SHALL return a 400 response.

    # Feature: forgot-password, Property 5: Password length boundary enforcement
    **Validates: Requirements 3.3, 3.4, 3.6**
    """
    with app.app_context():
        db.drop_all()
        db.create_all()

        user = _make_user()
        raw_token = generate_token(user)

        with app.test_client() as client:
            resp = client.post(
                "/api/reset-password",
                json={"token": raw_token, "password": password},
            )
            assert resp.status_code == 400, (
                f"Expected 400 for password of length {len(password)}, "
                f"got {resp.status_code}"
            )

        db.session.remove()


@settings(max_examples=8, deadline=5000)
@given(password=st.text(min_size=129, max_size=200))
def test_password_too_long_returns_400(password: str) -> None:
    """For any string with length > 128, submitting it as the new password to
    POST /api/reset-password SHALL return a 400 response.

    # Feature: forgot-password, Property 5: Password length boundary enforcement
    **Validates: Requirements 3.3, 3.4, 3.6**
    """
    with app.app_context():
        db.drop_all()
        db.create_all()

        user = _make_user()
        raw_token = generate_token(user)

        with app.test_client() as client:
            resp = client.post(
                "/api/reset-password",
                json={"token": raw_token, "password": password},
            )
            assert resp.status_code == 400, (
                f"Expected 400 for password of length {len(password)}, "
                f"got {resp.status_code}"
            )

        db.session.remove()


@settings(max_examples=8, deadline=5000)
@given(password=st.text(min_size=8, max_size=128))
def test_password_valid_length_returns_200(password: str) -> None:
    """For any string with length between 8 and 128 inclusive, submitting it as
    the new password to POST /api/reset-password with a valid token SHALL return
    a 200 response.

    # Feature: forgot-password, Property 5: Password length boundary enforcement
    **Validates: Requirements 3.3, 3.4, 3.6**
    """
    with app.app_context():
        db.drop_all()
        db.create_all()

        user = _make_user()
        raw_token = generate_token(user)

        with app.test_client() as client:
            resp = client.post(
                "/api/reset-password",
                json={"token": raw_token, "password": password},
            )
            assert resp.status_code == 200, (
                f"Expected 200 for password of length {len(password)}, "
                f"got {resp.status_code}. Response: {resp.get_json()}"
            )

        db.session.remove()


@settings(max_examples=8, deadline=5000)
@given(new_password=st.text(min_size=8, max_size=128))
def test_password_reset_hash_correctness(new_password: str) -> None:
    """For any new password string of valid length (8–128 characters), after a
    successful password reset the stored password_hash on the user record SHALL
    satisfy check_password_hash(user.password_hash, new_password) == True.

    # Feature: forgot-password, Property 6: Password reset hash correctness
    **Validates: Requirements 3.1**
    """
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()

        # Step 1: Create a user in fresh in-memory SQLite
        user = _make_user()

        # Step 2: Generate a token for the user
        raw_token = generate_token(user)

        # Step 3: Validate the token to get the record
        record = validate_token(raw_token)
        assert (
            record is not None
        ), "Expected freshly generated token to be valid, but validate_token() returned None"

        # Step 4: Consume the token with the hypothesis-generated password
        consume_token(record, new_password)

        # Step 5: Reload the user from DB and verify password hash correctness
        reloaded_user = db.session.get(User, user.id)
        assert reloaded_user is not None, "User should exist in the database"
        assert check_password_hash(reloaded_user.password_hash, new_password), (
            f"check_password_hash(user.password_hash, new_password) should be True "
            f"after password reset, but was False for password: {new_password!r}"
        )

        db.session.remove()


# ---------------------------------------------------------------------------
# Property 8: Invalid email format returns 400
# Feature: forgot-password, Property 8: Invalid email format returns 400
# Validates: Requirements 1.6, 1.7
# ---------------------------------------------------------------------------


@settings(max_examples=8, deadline=5000)
@given(
    invalid_email=st.one_of(
        st.just(""),
        st.text(max_size=50).filter(lambda s: "@" not in s),
    )
)
def test_invalid_email_format_returns_400(invalid_email: str) -> None:
    """For any string that is not a valid email address (no @ sign or empty
    string), submitting it to POST /api/forgot-password SHALL return a 400
    response with an "error" key in the JSON body.

    # Feature: forgot-password, Property 8: Invalid email format returns 400
    **Validates: Requirements 1.6, 1.7**
    """
    app.testing = True
    with app.test_client() as client:
        response = client.post(
            "/api/forgot-password",
            json={"email": invalid_email},
            content_type="application/json",
        )

        assert response.status_code == 400, (
            f"Expected 400 for invalid email {invalid_email!r}, "
            f"got {response.status_code}"
        )

        data = response.get_json()
        assert data is not None, "Expected JSON response body"
        assert "error" in data, (
            f"Expected 'error' key in response JSON for invalid email "
            f"{invalid_email!r}, got keys: {list(data.keys())}"
        )
