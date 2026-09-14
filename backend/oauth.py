import os
import secrets
from urllib.parse import urlencode

import requests


class OAuthError(Exception):
    """Exception raised during OAuth flow operations."""

    pass


def get_configured_providers():
    """Return a list of provider names that have valid client configurations."""
    providers = []

    if os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET"):
        providers.append("google")

    if os.environ.get("GITHUB_CLIENT_ID") and os.environ.get("GITHUB_CLIENT_SECRET"):
        providers.append("github")

    oidc_configured = (
        os.environ.get("OIDC_CLIENT_ID")
        and os.environ.get("OIDC_CLIENT_SECRET")
        and (
            os.environ.get("OIDC_DISCOVERY_URL")
            or (
                os.environ.get("OIDC_AUTH_URL")
                and os.environ.get("OIDC_TOKEN_URL")
                and os.environ.get("OIDC_USERINFO_URL")
            )
        )
    )
    if oidc_configured:
        providers.append("oidc")

    return providers


def is_provider_configured(provider: str) -> bool:
    """Check if a specific provider is configured in environment variables."""
    return provider in get_configured_providers()


def generate_oauth_state() -> str:
    """Generate a secure random state string for OAuth CSRF protection."""
    return secrets.token_urlsafe(32)


def _get_oidc_endpoints():
    """Fetch OIDC endpoints from discovery URL or environment fallback."""
    discovery_url = os.environ.get("OIDC_DISCOVERY_URL")
    if discovery_url:
        resp = requests.get(discovery_url, timeout=10)
        if resp.status_code != 200:
            raise OAuthError(
                f"Failed to fetch OIDC discovery document: HTTP {resp.status_code}"
            )
        data = resp.json()
        return {
            "auth_url": data.get("authorization_endpoint"),
            "token_url": data.get("token_endpoint"),
            "userinfo_url": data.get("userinfo_endpoint"),
        }

    return {
        "auth_url": os.environ.get("OIDC_AUTH_URL"),
        "token_url": os.environ.get("OIDC_TOKEN_URL"),
        "userinfo_url": os.environ.get("OIDC_USERINFO_URL"),
    }


def build_authorization_url(provider: str, redirect_uri: str, state: str) -> str:
    """Construct authorization redirect URL for the given provider."""
    provider = provider.lower()

    if provider == "google":
        client_id = os.environ.get("GOOGLE_CLIENT_ID")
        if not client_id:
            raise OAuthError("Google OAuth client ID is not configured")
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "prompt": "select_account",
        }
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    elif provider == "github":
        client_id = os.environ.get("GITHUB_CLIENT_ID")
        if not client_id:
            raise OAuthError("GitHub OAuth client ID is not configured")
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "read:user user:email",
            "state": state,
        }
        return f"https://github.com/login/oauth/authorize?{urlencode(params)}"

    elif provider == "oidc":
        client_id = os.environ.get("OIDC_CLIENT_ID")
        if not client_id:
            raise OAuthError("Generic OIDC client ID is not configured")
        endpoints = _get_oidc_endpoints()
        auth_url = endpoints.get("auth_url")
        if not auth_url:
            raise OAuthError("Generic OIDC authorization endpoint missing")
        scope = os.environ.get("OIDC_SCOPES", "openid email profile")
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scope,
            "state": state,
        }
        return f"{auth_url}?{urlencode(params)}"

    else:
        raise OAuthError(f"Unsupported OAuth provider: {provider}")


def exchange_code_and_get_user_info(
    provider: str, code: str, redirect_uri: str
) -> dict:
    """Exchange authorization code for tokens and retrieve user profile info."""
    provider = provider.lower()

    if provider == "google":
        client_id = os.environ.get("GOOGLE_CLIENT_ID")
        client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise OAuthError("Google OAuth credentials not configured")

        token_resp = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
            timeout=10,
        )
        if token_resp.status_code != 200:
            raise OAuthError(f"Google token exchange failed: {token_resp.text}")

        token_data = token_resp.json()
        access_token = token_data.get("access_token")

        user_resp = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if user_resp.status_code != 200:
            raise OAuthError(f"Failed to fetch Google user info: {user_resp.text}")

        user_data = user_resp.json()
        provider_user_id = str(user_data.get("sub", ""))
        email = user_data.get("email", "").strip().lower()
        email_verified = user_data.get("email_verified", True)

        if not provider_user_id:
            raise OAuthError("Missing provider user ID from Google")
        if not email:
            raise OAuthError("No email address returned from Google account")
        if not email_verified:
            raise OAuthError("Google email address is not verified")

        return {
            "provider": "google",
            "provider_user_id": provider_user_id,
            "email": email,
        }

    elif provider == "github":
        client_id = os.environ.get("GITHUB_CLIENT_ID")
        client_secret = os.environ.get("GITHUB_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise OAuthError("GitHub OAuth credentials not configured")

        token_resp = requests.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
            timeout=10,
        )
        if token_resp.status_code != 200:
            raise OAuthError(f"GitHub token exchange failed: {token_resp.text}")

        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            error_desc = token_data.get("error_description", token_resp.text)
            raise OAuthError(f"GitHub token response error: {error_desc}")

        user_resp = requests.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            timeout=10,
        )
        if user_resp.status_code != 200:
            raise OAuthError(f"Failed to fetch GitHub user profile: {user_resp.text}")

        user_data = user_resp.json()
        provider_user_id = str(user_data.get("id", ""))
        email = user_data.get("email")

        # GitHub user object email might be None if private; query /user/emails
        if not email:
            emails_resp = requests.get(
                "https://api.github.com/user/emails",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
                timeout=10,
            )
            if emails_resp.status_code == 200:
                emails_list = emails_resp.json()
                primary_verified = [
                    e for e in emails_list if e.get("primary") and e.get("verified")
                ]
                verified = [e for e in emails_list if e.get("verified")]

                if primary_verified:
                    email = primary_verified[0].get("email")
                elif verified:
                    email = verified[0].get("email")

        if email:
            email = email.strip().lower()

        if not provider_user_id:
            raise OAuthError("Missing provider user ID from GitHub")
        if not email:
            raise OAuthError("No verified email address found on GitHub account")

        return {
            "provider": "github",
            "provider_user_id": provider_user_id,
            "email": email,
        }

    elif provider == "oidc":
        client_id = os.environ.get("OIDC_CLIENT_ID")
        client_secret = os.environ.get("OIDC_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise OAuthError("Generic OIDC credentials not configured")

        endpoints = _get_oidc_endpoints()
        token_url = endpoints.get("token_url")
        userinfo_url = endpoints.get("userinfo_url")

        if not token_url or not userinfo_url:
            raise OAuthError("OIDC token or userinfo endpoint is missing")

        token_resp = requests.post(
            token_url,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
            timeout=10,
        )
        if token_resp.status_code != 200:
            raise OAuthError(f"OIDC token exchange failed: {token_resp.text}")

        token_data = token_resp.json()
        access_token = token_data.get("access_token")

        user_resp = requests.get(
            userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if user_resp.status_code != 200:
            raise OAuthError(f"Failed to fetch OIDC userinfo: {user_resp.text}")

        user_data = user_resp.json()
        provider_user_id = str(user_data.get("sub") or user_data.get("id") or "")
        email = str(user_data.get("email") or "").strip().lower()
        email_verified = user_data.get("email_verified", True)

        if not provider_user_id:
            raise OAuthError("Missing sub/user ID from OIDC userinfo response")
        if not email:
            raise OAuthError("No email address returned from OIDC userinfo response")
        if not email_verified:
            raise OAuthError("OIDC email address is not verified")

        return {
            "provider": "oidc",
            "provider_user_id": provider_user_id,
            "email": email,
        }

    else:
        raise OAuthError(f"Unsupported provider: {provider}")
