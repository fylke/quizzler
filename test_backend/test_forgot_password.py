import unittest
from datetime import UTC, datetime, timedelta

from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from backend import app
from backend.models import PasswordResetToken, User, db


class TestPasswordResetTokenSchema(unittest.TestCase):
    """Verify PasswordResetToken table columns, uniqueness constraint, and FK relationship.

    Requirements: 1.2, 2.5
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

    def test_password_reset_token_table_has_correct_columns(self):
        """PasswordResetToken table has columns: id, user_id, token_hash, created_at, expires_at, consumed."""
        inspector = inspect(db.engine)
        columns = {col["name"] for col in inspector.get_columns("password_reset_token")}
        expected = {
            "id",
            "user_id",
            "token_hash",
            "created_at",
            "expires_at",
            "consumed",
        }
        self.assertEqual(expected, columns)

    def test_token_hash_has_uniqueness_constraint(self):
        """Inserting two tokens with the same token_hash raises IntegrityError."""
        user = User(email="test@example.com", password_hash="hash123")
        db.session.add(user)
        db.session.commit()

        now = datetime.now(UTC).replace(tzinfo=None)
        duplicate_hash = "abcdef1234567890" * 4  # 64 chars
        token1 = PasswordResetToken(
            user_id=user.id,
            token_hash=duplicate_hash,
            created_at=now,
            expires_at=now + timedelta(minutes=15),
            consumed=False,
        )
        token2 = PasswordResetToken(
            user_id=user.id,
            token_hash=duplicate_hash,  # same hash — must be rejected
            created_at=now,
            expires_at=now + timedelta(minutes=15),
            consumed=False,
        )
        db.session.add(token1)
        db.session.commit()

        db.session.add(token2)
        with self.assertRaises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_user_id_foreign_key_relationship(self):
        """Can access token.user via the FK relationship."""
        user = User(email="fk@example.com", password_hash="hash123")
        db.session.add(user)
        db.session.commit()

        now = datetime.now(UTC).replace(tzinfo=None)
        token = PasswordResetToken(
            user_id=user.id,
            token_hash="a" * 64,
            created_at=now,
            expires_at=now + timedelta(minutes=15),
            consumed=False,
        )
        db.session.add(token)
        db.session.commit()

        loaded_token = PasswordResetToken.query.first()
        self.assertIsNotNone(loaded_token.user)
        self.assertEqual(loaded_token.user.id, user.id)
        self.assertEqual(loaded_token.user.email, "fk@example.com")

    def test_reset_tokens_cascade_delete_with_user(self):
        """Deleting a user cascades to delete their reset tokens."""
        user = User(email="cascade@example.com", password_hash="hash123")
        db.session.add(user)
        db.session.commit()

        now = datetime.now(UTC).replace(tzinfo=None)
        token = PasswordResetToken(
            user_id=user.id,
            token_hash="b" * 64,
            created_at=now,
            expires_at=now + timedelta(minutes=15),
            consumed=False,
        )
        db.session.add(token)
        db.session.commit()

        user_id = user.id
        db.session.delete(user)
        db.session.commit()

        self.assertIsNone(PasswordResetToken.query.filter_by(user_id=user_id).first())


class TestUserPasswordChangedAt(unittest.TestCase):
    """Verify password_changed_at column exists on User and is nullable.

    Requirements: 1.2, 2.5
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

    def test_password_changed_at_column_exists(self):
        """User table has a password_changed_at column."""
        inspector = inspect(db.engine)
        columns = {col["name"] for col in inspector.get_columns("user")}
        self.assertIn("password_changed_at", columns)

    def test_password_changed_at_is_nullable_and_defaults_to_none(self):
        """password_changed_at defaults to None for new users."""
        user = User(email="new@example.com", password_hash="hash123")
        db.session.add(user)
        db.session.commit()

        loaded = User.query.filter_by(email="new@example.com").first()
        self.assertIsNone(loaded.password_changed_at)

    def test_password_changed_at_can_be_set(self):
        """password_changed_at can be updated to a datetime value."""
        user = User(email="reset@example.com", password_hash="hash123")
        db.session.add(user)
        db.session.commit()

        now = datetime.now(UTC).replace(tzinfo=None)
        user.password_changed_at = now
        db.session.commit()

        loaded = User.query.filter_by(email="reset@example.com").first()
        self.assertIsNotNone(loaded.password_changed_at)
        self.assertEqual(loaded.password_changed_at, now)


if __name__ == "__main__":
    unittest.main()


import os
import smtplib
from unittest.mock import MagicMock, patch

from werkzeug.security import check_password_hash, generate_password_hash

from backend.email_service import EmailServiceError, send_password_reset_email


class TestEmailService(unittest.TestCase):
    """Unit tests for Email_Service (send_password_reset_email).

    Requirements: 4.1, 4.2, 4.3, 4.5, 4.6
    """

    SMTP_ENV = {
        "SMTP_HOST": "mail.example.com",
        "SMTP_PORT": "587",
        "SMTP_USERNAME": "user@example.com",
        "SMTP_PASSWORD": "s3cret",
        "SMTP_FROM_ADDRESS": "noreply@example.com",
    }

    @patch.dict(os.environ, SMTP_ENV, clear=False)
    @patch("backend.email_service.smtplib.SMTP")
    def test_smtp_success_path(self, mock_smtp_class):
        """SMTP success: sendmail called with correct from/to; body contains reset URL and '15 minutes'."""
        mock_conn = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        reset_url = "http://localhost:5000/reset-password?token=abc123"
        send_password_reset_email("user@example.com", reset_url)

        mock_smtp_class.assert_called_once_with("mail.example.com", 587, timeout=10)
        mock_conn.sendmail.assert_called_once()
        call_args = mock_conn.sendmail.call_args[0]
        self.assertEqual(call_args[0], "noreply@example.com")
        self.assertEqual(call_args[1], "user@example.com")
        body = call_args[2]
        self.assertIn(reset_url, body)
        self.assertIn("15 minutes", body)

    @patch.dict(
        os.environ, {k: v for k, v in SMTP_ENV.items() if k != "SMTP_HOST"}, clear=True
    )
    def test_missing_smtp_host_raises_error(self):
        """Missing SMTP_HOST raises EmailServiceError with 'SMTP_HOST' in reason."""
        with self.assertRaises(EmailServiceError) as ctx:
            send_password_reset_email("user@example.com", "http://example.com/reset")
        self.assertIn("SMTP_HOST", ctx.exception.reason)

    @patch.dict(
        os.environ, {k: v for k, v in SMTP_ENV.items() if k != "SMTP_PORT"}, clear=True
    )
    def test_missing_smtp_port_raises_error(self):
        """Missing SMTP_PORT raises EmailServiceError with 'SMTP_PORT' in reason."""
        with self.assertRaises(EmailServiceError) as ctx:
            send_password_reset_email("user@example.com", "http://example.com/reset")
        self.assertIn("SMTP_PORT", ctx.exception.reason)

    @patch.dict(
        os.environ,
        {k: v for k, v in SMTP_ENV.items() if k != "SMTP_USERNAME"},
        clear=True,
    )
    def test_missing_smtp_username_raises_error(self):
        """Missing SMTP_USERNAME raises EmailServiceError with 'SMTP_USERNAME' in reason."""
        with self.assertRaises(EmailServiceError) as ctx:
            send_password_reset_email("user@example.com", "http://example.com/reset")
        self.assertIn("SMTP_USERNAME", ctx.exception.reason)

    @patch.dict(
        os.environ,
        {k: v for k, v in SMTP_ENV.items() if k != "SMTP_PASSWORD"},
        clear=True,
    )
    def test_missing_smtp_password_raises_error(self):
        """Missing SMTP_PASSWORD raises EmailServiceError with 'SMTP_PASSWORD' in reason."""
        with self.assertRaises(EmailServiceError) as ctx:
            send_password_reset_email("user@example.com", "http://example.com/reset")
        self.assertIn("SMTP_PASSWORD", ctx.exception.reason)

    @patch.dict(
        os.environ,
        {k: v for k, v in SMTP_ENV.items() if k != "SMTP_FROM_ADDRESS"},
        clear=True,
    )
    def test_missing_smtp_from_address_raises_error(self):
        """Missing SMTP_FROM_ADDRESS raises EmailServiceError with 'SMTP_FROM_ADDRESS' in reason."""
        with self.assertRaises(EmailServiceError) as ctx:
            send_password_reset_email("user@example.com", "http://example.com/reset")
        self.assertIn("SMTP_FROM_ADDRESS", ctx.exception.reason)

    @patch.dict(os.environ, SMTP_ENV, clear=False)
    @patch("backend.email_service.smtplib.SMTP")
    def test_smtp_delivery_rejection_raises_error(self, mock_smtp_class):
        """SMTPException during send is caught and re-raised as EmailServiceError."""
        mock_conn = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.sendmail.side_effect = smtplib.SMTPException("Recipient rejected")

        with self.assertRaises(EmailServiceError) as ctx:
            send_password_reset_email("user@example.com", "http://example.com/reset")
        self.assertIn("SMTP", ctx.exception.reason)

    @patch.dict(os.environ, {**SMTP_ENV, "SMTP_USE_TLS": "true"}, clear=False)
    @patch("backend.email_service.smtplib.SMTP_SSL")
    @patch("backend.email_service.smtplib.SMTP")
    def test_tls_path_uses_smtp_ssl(self, mock_smtp_class, mock_smtp_ssl_class):
        """When SMTP_USE_TLS=true, smtplib.SMTP_SSL is used instead of smtplib.SMTP."""
        mock_conn = MagicMock()
        mock_smtp_ssl_class.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_smtp_ssl_class.return_value.__exit__ = MagicMock(return_value=False)

        send_password_reset_email(
            "user@example.com", "http://example.com/reset?token=xyz"
        )

        mock_smtp_ssl_class.assert_called_once_with("mail.example.com", 587)
        mock_smtp_class.assert_not_called()
        mock_conn.sendmail.assert_called_once()


class TestForgotPasswordAPIRoutes(unittest.TestCase):
    """Unit tests for forgot-password and reset-password API routes.

    Requirements: 1.4, 1.5, 1.6, 1.7, 2.1, 2.2, 2.4, 3.1, 3.2, 3.3, 3.5, 4.3
    """

    SMTP_ENV = {
        "SMTP_HOST": "mail.example.com",
        "SMTP_PORT": "587",
        "SMTP_USERNAME": "user@example.com",
        "SMTP_PASSWORD": "s3cret",
        "SMTP_FROM_ADDRESS": "noreply@example.com",
    }

    def setUp(self):
        app.testing = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        self.ctx = app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()

        # Create a test user with a known password
        self.test_email = "testuser@example.com"
        self.test_password = "oldpassword123"
        self.user = User(
            email=self.test_email,
            password_hash=generate_password_hash(self.test_password),
        )
        db.session.add(self.user)
        db.session.commit()

        self.client = app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    # --- POST /api/forgot-password ---

    @patch.dict(os.environ, SMTP_ENV, clear=False)
    @patch("backend.email_service.smtplib.SMTP")
    def test_forgot_password_happy_path_registered_email(self, mock_smtp_class):
        """Registered email: token generated, email sent, 200 response."""
        mock_conn = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        resp = self.client.post(
            "/api/forgot-password",
            json={"email": self.test_email},
            content_type="application/json",
        )

        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("message", data)
        self.assertIn("reset link has been sent", data["message"])

        # Verify a token was created for the user
        token_record = PasswordResetToken.query.filter_by(user_id=self.user.id).first()
        self.assertIsNotNone(token_record)
        self.assertFalse(token_record.consumed)

        # Verify email was sent
        mock_conn.sendmail.assert_called_once()

    @patch.dict(os.environ, SMTP_ENV, clear=False)
    @patch("backend.email_service.smtplib.SMTP")
    def test_forgot_password_unknown_email_same_200_no_token(self, mock_smtp_class):
        """Unknown email: same 200 response, no token generated, no email sent."""
        mock_conn = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        resp = self.client.post(
            "/api/forgot-password",
            json={"email": "nonexistent@example.com"},
            content_type="application/json",
        )

        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("message", data)
        self.assertIn("reset link has been sent", data["message"])

        # No token should exist
        token_record = PasswordResetToken.query.first()
        self.assertIsNone(token_record)

        # No email sent
        mock_conn.sendmail.assert_not_called()

    def test_forgot_password_invalid_email_format_returns_400(self):
        """Invalid email format returns 400 with error message."""
        resp = self.client.post(
            "/api/forgot-password",
            json={"email": "not-an-email"},
            content_type="application/json",
        )

        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("error", data)
        self.assertIn("Invalid email format", data["error"])

    def test_forgot_password_empty_email_returns_400(self):
        """Empty email returns 400 with error message."""
        resp = self.client.post(
            "/api/forgot-password",
            json={"email": ""},
            content_type="application/json",
        )

        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("error", data)
        self.assertIn("Email is required", data["error"])

    def test_forgot_password_missing_email_field_returns_400(self):
        """Missing email field returns 400."""
        resp = self.client.post(
            "/api/forgot-password",
            json={},
            content_type="application/json",
        )

        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("error", data)
        self.assertIn("Email is required", data["error"])

    # --- GET /api/reset-password/validate ---

    def test_validate_token_valid(self):
        """Valid token returns {"valid": true}."""
        from backend.reset_tokens import generate_token

        raw_token = generate_token(self.user)

        resp = self.client.get(f"/api/reset-password/validate?token={raw_token}")

        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["valid"])

    def test_validate_token_expired(self):
        """Expired token returns 400."""
        import hashlib

        raw = "expiredtoken123"
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        now = datetime.now(UTC).replace(tzinfo=None)
        token_record = PasswordResetToken(
            user_id=self.user.id,
            token_hash=token_hash,
            created_at=now - timedelta(minutes=30),
            expires_at=now - timedelta(minutes=15),  # expired
            consumed=False,
        )
        db.session.add(token_record)
        db.session.commit()

        resp = self.client.get(f"/api/reset-password/validate?token={raw}")

        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("error", data)
        self.assertIn("Invalid or expired", data["error"])

    def test_validate_token_consumed(self):
        """Consumed token returns 400."""
        import hashlib

        raw = "consumedtoken456"
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        now = datetime.now(UTC).replace(tzinfo=None)
        token_record = PasswordResetToken(
            user_id=self.user.id,
            token_hash=token_hash,
            created_at=now,
            expires_at=now + timedelta(minutes=15),
            consumed=True,
        )
        db.session.add(token_record)
        db.session.commit()

        resp = self.client.get(f"/api/reset-password/validate?token={raw}")

        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("error", data)
        self.assertIn("Invalid or expired", data["error"])

    def test_validate_token_unknown(self):
        """Unknown token returns 400."""
        resp = self.client.get("/api/reset-password/validate?token=totallyunknowntoken")

        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("error", data)
        self.assertIn("Invalid or expired", data["error"])

    # --- POST /api/reset-password ---

    def test_reset_password_happy_path(self):
        """Happy path: password updated, token consumed, 200 response."""
        from backend.reset_tokens import generate_token

        raw_token = generate_token(self.user)
        new_password = "newsecurepassword99"

        resp = self.client.post(
            "/api/reset-password",
            json={"token": raw_token, "password": new_password},
            content_type="application/json",
        )

        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("message", data)
        self.assertIn("password has been reset", data["message"])

        # Verify password was updated
        db.session.refresh(self.user)
        self.assertTrue(check_password_hash(self.user.password_hash, new_password))

        # Verify token was consumed
        token_record = PasswordResetToken.query.filter_by(user_id=self.user.id).first()
        self.assertTrue(token_record.consumed)

    def test_reset_password_expired_token(self):
        """Expired token returns 400."""
        import hashlib

        raw = "expiredresettoken"
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        now = datetime.now(UTC).replace(tzinfo=None)
        token_record = PasswordResetToken(
            user_id=self.user.id,
            token_hash=token_hash,
            created_at=now - timedelta(minutes=30),
            expires_at=now - timedelta(minutes=15),
            consumed=False,
        )
        db.session.add(token_record)
        db.session.commit()

        resp = self.client.post(
            "/api/reset-password",
            json={"token": raw, "password": "validpassword123"},
            content_type="application/json",
        )

        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("Invalid or expired", data["error"])

    def test_reset_password_consumed_token(self):
        """Consumed token returns 400."""
        import hashlib

        raw = "alreadyusedtoken"
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        now = datetime.now(UTC).replace(tzinfo=None)
        token_record = PasswordResetToken(
            user_id=self.user.id,
            token_hash=token_hash,
            created_at=now,
            expires_at=now + timedelta(minutes=15),
            consumed=True,
        )
        db.session.add(token_record)
        db.session.commit()

        resp = self.client.post(
            "/api/reset-password",
            json={"token": raw, "password": "validpassword123"},
            content_type="application/json",
        )

        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("Invalid or expired", data["error"])

    def test_reset_password_unknown_token(self):
        """Unknown token returns 400."""
        resp = self.client.post(
            "/api/reset-password",
            json={"token": "unknowntoken999", "password": "validpassword123"},
            content_type="application/json",
        )

        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("Invalid or expired", data["error"])

    def test_reset_password_too_short(self):
        """Password shorter than 8 characters returns 400."""
        from backend.reset_tokens import generate_token

        raw_token = generate_token(self.user)

        resp = self.client.post(
            "/api/reset-password",
            json={"token": raw_token, "password": "short"},
            content_type="application/json",
        )

        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("between 8 and 128", data["error"])

    def test_reset_password_too_long(self):
        """Password longer than 128 characters returns 400."""
        from backend.reset_tokens import generate_token

        raw_token = generate_token(self.user)

        resp = self.client.post(
            "/api/reset-password",
            json={"token": raw_token, "password": "a" * 129},
            content_type="application/json",
        )

        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("between 8 and 128", data["error"])

    def test_reset_password_missing_token(self):
        """Missing token field returns 400."""
        resp = self.client.post(
            "/api/reset-password",
            json={"password": "validpassword123"},
            content_type="application/json",
        )

        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("Token is required", data["error"])

    def test_reset_password_missing_password(self):
        """Missing password field returns 400."""
        from backend.reset_tokens import generate_token

        raw_token = generate_token(self.user)

        resp = self.client.post(
            "/api/reset-password",
            json={"token": raw_token},
            content_type="application/json",
        )

        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("Password is required", data["error"])

    # --- Session invalidation ---

    def test_session_invalidation_after_password_reset(self):
        """Session created before reset is rejected after reset (get_current_user returns None)."""
        from backend.reset_tokens import generate_token

        # Log in to establish a session
        login_resp = self.client.post(
            "/api/login",
            json={"email": self.test_email, "password": self.test_password},
            content_type="application/json",
        )
        self.assertEqual(login_resp.status_code, 200)

        # Verify we are authenticated
        me_resp = self.client.get("/api/me")
        self.assertEqual(me_resp.status_code, 200)

        # Reset the password (simulating the reset flow)
        raw_token = generate_token(self.user)
        new_password = "newpasswordafter"
        reset_resp = self.client.post(
            "/api/reset-password",
            json={"token": raw_token, "password": new_password},
            content_type="application/json",
        )
        self.assertEqual(reset_resp.status_code, 200)

        # The old session should now be invalid — get_current_user returns None
        me_resp2 = self.client.get("/api/me")
        self.assertEqual(me_resp2.status_code, 401)

    # --- SMTP failure ---

    @patch.dict(os.environ, SMTP_ENV, clear=False)
    @patch("backend.email_service.smtplib.SMTP")
    def test_smtp_failure_returns_500(self, mock_smtp_class):
        """SMTP failure returns 500 and error is logged."""
        mock_conn = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.sendmail.side_effect = smtplib.SMTPException("Connection timed out")

        with self.assertLogs("backend", level="ERROR") as log_ctx:
            resp = self.client.post(
                "/api/forgot-password",
                json={"email": self.test_email},
                content_type="application/json",
            )

        self.assertEqual(resp.status_code, 500)
        data = resp.get_json()
        self.assertIn("error", data)
        self.assertIn("Failed to send reset email", data["error"])

        # Verify error was logged
        self.assertTrue(
            any("Failed to send reset email" in msg for msg in log_ctx.output)
        )
