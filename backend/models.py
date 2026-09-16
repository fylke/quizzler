from datetime import UTC, datetime

from flask_sqlalchemy import SQLAlchemy

# Shared SQLAlchemy instance used by the app and tests
# Flask-SQLAlchemy will bind this to the Flask app in src/main/__init__.py

db = SQLAlchemy()


class QuizIdentity(db.Model):
    __tablename__ = "quiz_identity"
    __table_args__ = (
        db.UniqueConstraint(
            "quiz_type",
            "source_id",
            name="uq_quiz_identity_source",
        ),
    )

    guid = db.Column(db.String(36), primary_key=True)
    quiz_type = db.Column(db.String(64), nullable=False, index=True)
    source_id = db.Column(db.Integer, nullable=False)


class Destination(db.Model):
    __tablename__ = "countries"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    hint1 = db.Column(db.String(256), nullable=False)
    hint1_source = db.Column(db.String(512), nullable=True)
    hint2 = db.Column(db.String(256), nullable=False)
    hint2_source = db.Column(db.String(512), nullable=True)
    hint3 = db.Column(db.String(256), nullable=False)
    hint3_source = db.Column(db.String(512), nullable=True)
    hint4 = db.Column(db.String(256), nullable=False)
    hint4_source = db.Column(db.String(512), nullable=True)
    hint5 = db.Column(db.String(256), nullable=False)
    hint5_source = db.Column(db.String(512), nullable=True)
    correct_answers = db.Column(db.JSON, nullable=False)

    results = db.relationship(
        "QuizResult", back_populates="country", cascade="all, delete-orphan"
    )


class User(db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    password_hash = db.Column(db.String(256), nullable=True)
    email = db.Column(db.String(128), nullable=False, unique=True)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    password_changed_at = db.Column(db.DateTime, nullable=True, default=None)

    results = db.relationship(
        "QuizResult", back_populates="user", cascade="all, delete-orphan"
    )
    oauth_accounts = db.relationship(
        "OAuthAccount", back_populates="user", cascade="all, delete-orphan"
    )


class OAuthAccount(db.Model):
    __tablename__ = "oauth_account"
    __table_args__ = (
        db.UniqueConstraint(
            "provider",
            "provider_user_id",
            name="uq_oauth_provider_user_id",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )
    provider = db.Column(db.String(64), nullable=False)
    provider_user_id = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: _utcnow_naive())

    user = db.relationship("User", back_populates="oauth_accounts")


class QuizResult(db.Model):
    __tablename__ = "quiz_result"

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    destination_id = db.Column(
        db.Integer, db.ForeignKey("countries.id"), primary_key=True
    )
    hint_difficulty = db.Column(db.Integer, nullable=False, default=5)
    remaining_guesses = db.Column(db.Integer, nullable=False, default=3)
    ongoing = db.Column(db.Boolean, nullable=False, default=True)

    user = db.relationship("User", back_populates="results")
    country = db.relationship("Destination", back_populates="results")


def _utcnow_naive() -> datetime:
    """Return current UTC time as a naive datetime for DB storage."""
    return datetime.now(UTC).replace(tzinfo=None)


class HintSourceReview(db.Model):
    __tablename__ = "hint_source_review"
    __table_args__ = (
        db.UniqueConstraint(
            "quiz_type",
            "source_id",
            "hint_difficulty",
            name="uq_hint_source_review_item",
        ),
        db.Index(
            "ix_hint_source_review_queue",
            "quiz_type",
            "reviewed",
            "source_id",
            "hint_difficulty",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    quiz_type = db.Column(db.String(64), nullable=False)
    source_id = db.Column(db.Integer, nullable=False)
    hint_difficulty = db.Column(db.Integer, nullable=False)
    reviewed = db.Column(db.Boolean, nullable=False, default=False)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    reviewed_by = db.relationship("User", backref="hint_source_reviews")


class GuestSession(db.Model):
    __tablename__ = "guest_session"

    id = db.Column(db.Integer, primary_key=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow_naive)

    results = db.relationship(
        "GuestQuizResult", back_populates="guest_session", cascade="all, delete-orphan"
    )


class GuestQuizResult(db.Model):
    __tablename__ = "guest_quiz_result"

    guest_session_id = db.Column(
        db.Integer,
        db.ForeignKey("guest_session.id"),
        primary_key=True,
    )
    destination_id = db.Column(
        db.Integer, db.ForeignKey("countries.id"), primary_key=True
    )
    hint_difficulty = db.Column(db.Integer, nullable=False, default=5)
    remaining_guesses = db.Column(db.Integer, nullable=False, default=3)
    ongoing = db.Column(db.Boolean, nullable=False, default=True)

    guest_session = db.relationship("GuestSession", back_populates="results")
    country = db.relationship("Destination")


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_token"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    consumed = db.Column(db.Boolean, nullable=False, default=False)

    user = db.relationship(
        "User", backref=db.backref("reset_tokens", cascade="all, delete-orphan")
    )


class AppSetting(db.Model):
    __tablename__ = "app_settings"

    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.String(512), nullable=True)


def get_app_setting(key: str, default: str | None = None) -> str | None:
    """Retrieve an application setting value by key."""
    setting = AppSetting.query.filter_by(key=key).first()
    return (
        setting.value if setting is not None and setting.value is not None else default
    )


def set_app_setting(key: str, value: str | None) -> None:
    """Set or remove an application setting."""
    setting = AppSetting.query.filter_by(key=key).first()
    if setting is None:
        if value is not None:
            setting = AppSetting(key=key, value=value)
            db.session.add(setting)
    else:
        if value is None:
            db.session.delete(setting)
        else:
            setting.value = value


def get_background_settings() -> dict[str, str | None]:
    """Return dictionary of configured background image paths."""
    return {
        "portrait": get_app_setting("background_portrait"),
        "landscape": get_app_setting("background_landscape"),
    }
