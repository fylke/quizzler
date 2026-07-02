"""Email service for Quizzler.

Sends transactional emails (password reset) via SMTP. All configuration is
read from environment variables at call time so that tests can freely set
and override them without module-level side effects.
"""

import os
import smtplib
from email.mime.text import MIMEText


class EmailServiceError(Exception):
    """Raised when the email service fails to send a message."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _load_smtp_config() -> tuple[str, int, str, str, str, bool]:
    """Return validated SMTP config or raise EmailServiceError."""
    # --- Read and validate SMTP configuration at call time ---
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port_raw = os.environ.get("SMTP_PORT", "")
    smtp_username = os.environ.get("SMTP_USERNAME", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    from_address = os.environ.get("SMTP_FROM_ADDRESS", "")
    use_tls_raw = os.environ.get("SMTP_USE_TLS", "")

    if not smtp_host:
        raise EmailServiceError("SMTP_HOST is missing or empty")
    if not smtp_port_raw:
        raise EmailServiceError("SMTP_PORT is missing or empty")
    if not smtp_username:
        raise EmailServiceError("SMTP_USERNAME is missing or empty")
    if not smtp_password:
        raise EmailServiceError("SMTP_PASSWORD is missing or empty")
    if not from_address:
        raise EmailServiceError("SMTP_FROM_ADDRESS is missing or empty")

    try:
        smtp_port = int(smtp_port_raw)
    except ValueError:
        raise EmailServiceError(f"SMTP_PORT must be an integer, got: {smtp_port_raw!r}")

    if not (1 <= smtp_port <= 65535):
        raise EmailServiceError(
            f"SMTP_PORT must be between 1 and 65535, got: {smtp_port}"
        )

    use_tls = use_tls_raw.strip().lower() == "true"
    return smtp_host, smtp_port, smtp_username, smtp_password, from_address, use_tls


def _send_email(to_address: str, subject: str, body: str) -> None:
    """Send one plain-text email using configured SMTP settings."""
    (
        smtp_host,
        smtp_port,
        smtp_username,
        smtp_password,
        from_address,
        use_tls,
    ) = _load_smtp_config()

    message = MIMEText(body, "plain")
    message["Subject"] = subject
    message["From"] = from_address
    message["To"] = to_address

    try:
        if use_tls:
            smtp_conn = smtplib.SMTP_SSL(smtp_host, smtp_port)
        else:
            smtp_conn = smtplib.SMTP(smtp_host, smtp_port, timeout=10)

        with smtp_conn as smtp:
            smtp.login(smtp_username, smtp_password)
            smtp.sendmail(from_address, to_address, message.as_string())
    except smtplib.SMTPException as exc:
        raise EmailServiceError(f"SMTP error while sending email: {exc}") from exc


def send_password_reset_email(to_address: str, reset_url: str) -> None:
    """Send a password reset email. Raises EmailServiceError on failure."""

    # --- Build the email message ---
    subject = "Quizzler \u2014 Password Reset Request"
    body = (
        f"You requested a password reset for your Quizzler account.\n\n"
        f"Click the link below to set a new password:\n\n"
        f"{reset_url}\n\n"
        f"This link expires in 15 minutes.\n\n"
        f"If you did not request a password reset, you can safely ignore this email."
    )

    _send_email(to_address, subject, body)


def send_hint_complaint_email(
    admin_address: str,
    reporter_email: str,
    reporter_name: str,
    quiz_id: int,
    hint_difficulty: int,
    hint_text: str,
    message: str,
) -> None:
    """Send a hint complaint email to the admin mailbox."""

    if not admin_address:
        raise EmailServiceError("ADMIN_EMAIL is missing or empty")

    subject = f"Quizzler - Hint complaint for quiz {quiz_id}"
    body = (
        "A user submitted a hint complaint.\n\n"
        f"Reporter name: {reporter_name}\n"
        f"Reporter email (for follow-up): {reporter_email}\n"
        f"Quiz ID: {quiz_id}\n"
        f"Hint level: {hint_difficulty}\n"
        f"Hint text: {hint_text}\n\n"
        "Complaint message:\n"
        f"{message}\n"
    )

    _send_email(admin_address, subject, body)
