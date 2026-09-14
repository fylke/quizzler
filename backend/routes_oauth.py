from urllib.parse import quote_plus

from flask import Blueprint, current_app, redirect, request, session, url_for

from backend.auth import (
    get_current_guest_session,
    login_user_session,
    migrate_guest_session_to_user,
)
from backend.models import OAuthAccount, User, db
from backend.oauth import (
    OAuthError,
    build_authorization_url,
    exchange_code_and_get_user_info,
    generate_oauth_state,
    get_configured_providers,
    is_provider_configured,
)

oauth_bp = Blueprint("oauth_bp", __name__)


@oauth_bp.route("/api/auth/providers", methods=["GET"])
def list_providers():
    """List enabled OAuth providers."""
    return {"providers": get_configured_providers()}


@oauth_bp.route("/api/auth/oauth/<provider>/login", methods=["GET"])
def oauth_login(provider):
    """Initiate OAuth flow by building authorization URL and setting state token."""
    provider = provider.lower()
    if not is_provider_configured(provider):
        current_app.logger.warning(
            "Attempted OAuth login with unconfigured provider: %s", provider
        )
        return redirect(
            "/?error=" + quote_plus(f"OAuth provider '{provider}' is not configured")
        )

    state = generate_oauth_state()
    session["oauth_state"] = state
    session["oauth_provider"] = provider

    redirect_uri = url_for("oauth_bp.oauth_callback", provider=provider, _external=True)

    try:
        auth_url = build_authorization_url(provider, redirect_uri, state)
    except OAuthError as exc:
        return redirect("/?error=" + quote_plus(str(exc)))

    return redirect(auth_url)


@oauth_bp.route("/api/auth/oauth/<provider>/callback", methods=["GET"])
def oauth_callback(provider):
    """Handle OAuth redirect callback from provider."""
    provider = provider.lower()

    # Handle provider-initiated error params
    error_param = request.args.get("error")
    if error_param:
        error_desc = request.args.get("error_description", error_param)
        return redirect("/?error=" + quote_plus(f"OAuth error: {error_desc}"))

    code = request.args.get("code")
    state = request.args.get("state")
    expected_state = session.pop("oauth_state", None)
    expected_provider = session.pop("oauth_provider", None)

    if not state or not expected_state or state != expected_state:
        return redirect(
            "/?error=" + quote_plus("Invalid or missing OAuth state parameter")
        )

    if expected_provider and expected_provider != provider:
        return redirect(
            "/?error=" + quote_plus("OAuth provider mismatch during callback")
        )

    if not code:
        return redirect("/?error=" + quote_plus("Missing OAuth authorization code"))

    redirect_uri = url_for("oauth_bp.oauth_callback", provider=provider, _external=True)

    try:
        user_info = exchange_code_and_get_user_info(provider, code, redirect_uri)
    except OAuthError as exc:
        return redirect("/?error=" + quote_plus(str(exc)))

    provider_name = user_info["provider"]
    provider_user_id = user_info["provider_user_id"]
    email = user_info["email"]

    # 1. Lookup existing linked OAuth account
    oauth_account = OAuthAccount.query.filter_by(
        provider=provider_name, provider_user_id=provider_user_id
    ).first()

    if oauth_account:
        user = oauth_account.user
    else:
        # 2. Check if user with matching email already exists (automatic account linking)
        user = User.query.filter_by(email=email).first()

        if not user:
            # 3. Create new user account if no matching email
            user = User(email=email, password_hash=None, is_admin=False)
            db.session.add(user)
            db.session.flush()

        # Link provider account to user
        oauth_account = OAuthAccount(
            user_id=user.id,
            provider=provider_name,
            provider_user_id=provider_user_id,
        )
        db.session.add(oauth_account)
        db.session.commit()

    # Migrate guest session if active
    guest_session = get_current_guest_session()
    if guest_session:
        migrate_guest_session_to_user(user, guest_session)

    # Establish authenticated session
    login_user_session(user)

    return redirect("/")
