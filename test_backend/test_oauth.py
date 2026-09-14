import os
import unittest
from unittest.mock import MagicMock, patch

from backend import app
from backend.models import OAuthAccount, User, db
from backend.oauth import OAuthError, exchange_code_and_get_user_info


class OAuthTestCase(unittest.TestCase):
    def setUp(self):
        app.testing = True
        self.client = app.test_client()
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

        self.env_patcher = patch.dict(os.environ, {}, clear=True)
        self.env_patcher.start()

        with app.app_context():
            db.drop_all()
            db.create_all()

    def tearDown(self):
        self.env_patcher.stop()
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_list_providers_empty(self):
        response = self.client.get("/api/auth/providers")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"providers": []})

    def test_list_providers_configured(self):
        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "g_client",
                "GOOGLE_CLIENT_SECRET": "g_secret",
                "GITHUB_CLIENT_ID": "gh_client",
                "GITHUB_CLIENT_SECRET": "gh_secret",
            },
        ):
            response = self.client.get("/api/auth/providers")
            self.assertEqual(response.status_code, 200)
            providers = response.get_json()["providers"]
            self.assertIn("google", providers)
            self.assertIn("github", providers)

    def test_oauth_login_unconfigured_provider(self):
        response = self.client.get("/api/auth/oauth/google/login")
        self.assertEqual(response.status_code, 302)
        self.assertIn("error=", response.headers["Location"])

    def test_oauth_login_google_configured(self):
        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "test_google_id",
                "GOOGLE_CLIENT_SECRET": "test_google_secret",
            },
        ):
            response = self.client.get("/api/auth/oauth/google/login")
            self.assertEqual(response.status_code, 302)
            location = response.headers["Location"]
            self.assertIn("https://accounts.google.com/o/oauth2/v2/auth", location)
            self.assertIn("client_id=test_google_id", location)
            self.assertIn("scope=openid+email+profile", location)

            with self.client.session_transaction() as sess:
                self.assertIn("oauth_state", sess)
                self.assertEqual(sess["oauth_provider"], "google")

    def test_oauth_login_github_configured(self):
        with patch.dict(
            os.environ,
            {
                "GITHUB_CLIENT_ID": "test_github_id",
                "GITHUB_CLIENT_SECRET": "test_github_secret",
            },
        ):
            response = self.client.get("/api/auth/oauth/github/login")
            self.assertEqual(response.status_code, 302)
            location = response.headers["Location"]
            self.assertIn("https://github.com/login/oauth/authorize", location)
            self.assertIn("client_id=test_github_id", location)

    def test_oauth_login_oidc_configured(self):
        with patch.dict(
            os.environ,
            {
                "OIDC_CLIENT_ID": "test_oidc_id",
                "OIDC_CLIENT_SECRET": "test_oidc_secret",
                "OIDC_AUTH_URL": "https://sso.example.com/auth",
                "OIDC_TOKEN_URL": "https://sso.example.com/token",
                "OIDC_USERINFO_URL": "https://sso.example.com/userinfo",
            },
        ):
            response = self.client.get("/api/auth/oauth/oidc/login")
            self.assertEqual(response.status_code, 302)
            location = response.headers["Location"]
            self.assertIn("https://sso.example.com/auth", location)
            self.assertIn("client_id=test_oidc_id", location)

    def test_oauth_callback_provider_error(self):
        response = self.client.get(
            "/api/auth/oauth/google/callback?error=access_denied&error_description=User+denied"
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("User+denied", response.headers["Location"])

    def test_oauth_callback_invalid_state(self):
        with self.client.session_transaction() as sess:
            sess["oauth_state"] = "valid_state"
            sess["oauth_provider"] = "google"

        response = self.client.get(
            "/api/auth/oauth/google/callback?code=abc&state=wrong_state"
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("Invalid+or+missing", response.headers["Location"])

    @patch("backend.routes_oauth.exchange_code_and_get_user_info")
    def test_oauth_callback_creates_new_user(self, mock_exchange):
        mock_exchange.return_value = {
            "provider": "google",
            "provider_user_id": "google_12345",
            "email": "newuser@example.com",
        }

        with self.client.session_transaction() as sess:
            sess["oauth_state"] = "valid_state"
            sess["oauth_provider"] = "google"

        response = self.client.get(
            "/api/auth/oauth/google/callback?code=testcode&state=valid_state"
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/")

        with app.app_context():
            user = User.query.filter_by(email="newuser@example.com").first()
            self.assertIsNotNone(user)
            self.assertIsNone(user.password_hash)

            oauth_acc = OAuthAccount.query.filter_by(user_id=user.id).first()
            self.assertIsNotNone(oauth_acc)
            self.assertEqual(oauth_acc.provider, "google")
            self.assertEqual(oauth_acc.provider_user_id, "google_12345")

        with self.client.session_transaction() as sess:
            self.assertIn("user_id", sess)

    @patch("backend.routes_oauth.exchange_code_and_get_user_info")
    def test_oauth_callback_links_existing_email_account(self, mock_exchange):
        with app.app_context():
            existing_user = User(
                email="existing@example.com",
                password_hash="somehash",
            )
            db.session.add(existing_user)
            db.session.commit()
            existing_id = existing_user.id

        mock_exchange.return_value = {
            "provider": "github",
            "provider_user_id": "github_777",
            "email": "existing@example.com",
        }

        with self.client.session_transaction() as sess:
            sess["oauth_state"] = "valid_state"
            sess["oauth_provider"] = "github"

        response = self.client.get(
            "/api/auth/oauth/github/callback?code=testcode&state=valid_state"
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/")

        with app.app_context():
            # Ensure no duplicate User was created
            users = User.query.filter_by(email="existing@example.com").all()
            self.assertEqual(len(users), 1)

            # Ensure OAuthAccount is linked to existing user
            oauth_acc = OAuthAccount.query.filter_by(
                provider="github", provider_user_id="github_777"
            ).first()
            self.assertIsNotNone(oauth_acc)
            self.assertEqual(oauth_acc.user_id, existing_id)

    @patch("backend.routes_oauth.exchange_code_and_get_user_info")
    def test_oauth_callback_guest_session_migration(self, mock_exchange):
        # 1. Create guest session via endpoint
        guest_resp = self.client.post("/api/guest-session")
        self.assertEqual(guest_resp.status_code, 200)

        mock_exchange.return_value = {
            "provider": "google",
            "provider_user_id": "google_guest_migrator",
            "email": "migrated_guest@example.com",
        }

        with self.client.session_transaction() as sess:
            sess["oauth_state"] = "valid_state"
            sess["oauth_provider"] = "google"

        response = self.client.get(
            "/api/auth/oauth/google/callback?code=testcode&state=valid_state"
        )
        self.assertEqual(response.status_code, 302)

        with app.app_context():
            user = User.query.filter_by(email="migrated_guest@example.com").first()
            self.assertIsNotNone(user)
            from backend.models import GuestSession

            self.assertEqual(GuestSession.query.count(), 0)

    @patch("requests.get")
    @patch("requests.post")
    def test_exchange_code_google_success(self, mock_post, mock_get):
        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = {"access_token": "mock_google_at"}
        mock_post.return_value = token_response

        userinfo_response = MagicMock()
        userinfo_response.status_code = 200
        userinfo_response.json.return_value = {
            "sub": "google_sub_100",
            "email": "GoogleUser@example.com",
            "email_verified": True,
        }
        mock_get.return_value = userinfo_response

        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "g_id",
                "GOOGLE_CLIENT_SECRET": "g_secret",
            },
        ):
            res = exchange_code_and_get_user_info(
                "google", "test_code", "http://localhost/callback"
            )
            self.assertEqual(res["provider"], "google")
            self.assertEqual(res["provider_user_id"], "google_sub_100")
            self.assertEqual(res["email"], "googleuser@example.com")

    @patch("requests.get")
    @patch("requests.post")
    def test_exchange_code_github_user_email_fallback(self, mock_post, mock_get):
        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = {"access_token": "mock_github_at"}
        mock_post.return_value = token_response

        # User profile response with null email
        user_response = MagicMock()
        user_response.status_code = 200
        user_response.json.return_value = {"id": 123456, "email": None}

        # Emails endpoint response
        emails_response = MagicMock()
        emails_response.status_code = 200
        emails_response.json.return_value = [
            {"email": "secondary@example.com", "primary": False, "verified": True},
            {"email": "primary@example.com", "primary": True, "verified": True},
        ]

        mock_get.side_effect = [user_response, emails_response]

        with patch.dict(
            os.environ,
            {
                "GITHUB_CLIENT_ID": "gh_id",
                "GITHUB_CLIENT_SECRET": "gh_secret",
            },
        ):
            res = exchange_code_and_get_user_info(
                "github", "test_code", "http://localhost/callback"
            )
            self.assertEqual(res["provider"], "github")
            self.assertEqual(res["provider_user_id"], "123456")
            self.assertEqual(res["email"], "primary@example.com")
