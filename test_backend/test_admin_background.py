import io
import shutil
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

from backend import app
from backend.models import User, db, get_background_settings


class AdminBackgroundAPITestCase(unittest.TestCase):
    """Tests for the admin background image settings API endpoints."""

    def setUp(self):
        app.testing = True
        self.client = app.test_client()
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

        self.temp_media_dir = tempfile.mkdtemp()
        app.config["MEDIA_DIR"] = self.temp_media_dir

        with app.app_context():
            db.drop_all()
            db.create_all()

            self.regular_user = User(
                email="regular@example.com",
                password_hash=generate_password_hash("password123"),
            )
            db.session.add(self.regular_user)

            self.admin_user = User(
                email="admin@example.com",
                password_hash=generate_password_hash("adminpass123"),
                is_admin=True,
            )
            db.session.add(self.admin_user)
            db.session.commit()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()
        shutil.rmtree(self.temp_media_dir, ignore_errors=True)

    def _login_admin(self):
        response = self.client.post(
            "/api/login",
            json={"email": "admin@example.com", "password": "adminpass123"},
        )
        return response.get_json()["csrfToken"]

    def _login_regular(self):
        response = self.client.post(
            "/api/login",
            json={"email": "regular@example.com", "password": "password123"},
        )
        return response.get_json()["csrfToken"]

    def test_get_background_public_endpoint(self):
        """Public endpoint returns null settings when no background is set."""
        response = self.client.get("/api/settings/background")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("portrait", data)
        self.assertIn("landscape", data)
        self.assertIsNone(data["portrait"])
        self.assertIsNone(data["landscape"])

    def test_upload_background_requires_admin(self):
        """Non-admin and unauthenticated users cannot upload background images."""
        # Unauthenticated
        response = self.client.post(
            "/api/admin/settings/background",
            data={"portrait": (io.BytesIO(b"fake image data"), "portrait.jpg")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 401)

        # Regular user
        csrf = self._login_regular()
        response = self.client.post(
            "/api/admin/settings/background",
            data={"portrait": (io.BytesIO(b"fake image data"), "portrait.jpg")},
            headers={"X-CSRF-Token": csrf},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 403)

    def test_upload_background_csrf_protection(self):
        """Admin user without CSRF token cannot upload background images."""
        self._login_admin()
        response = self.client.post(
            "/api/admin/settings/background",
            data={"portrait": (io.BytesIO(b"fake image data"), "portrait.jpg")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 403)

    def test_upload_background_empty_payload(self):
        """Uploading without files returns 400."""
        csrf = self._login_admin()
        response = self.client.post(
            "/api/admin/settings/background",
            data={},
            headers={"X-CSRF-Token": csrf},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_upload_background_invalid_file_type(self):
        """Uploading non-image files returns 400."""
        csrf = self._login_admin()
        response = self.client.post(
            "/api/admin/settings/background",
            data={"portrait": (io.BytesIO(b"malicious script"), "script.sh")},
            headers={"X-CSRF-Token": csrf},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Only image files are allowed", response.get_json()["error"])

    def test_upload_background_rejects_oversized_request(self):
        csrf = self._login_admin()
        response = self.client.post(
            "/api/admin/settings/background",
            data={"portrait": (io.BytesIO(b"x" * (25 * 1024 * 1024)), "large.jpg")},
            headers={"X-CSRF-Token": csrf},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.get_json(), {"error": "Request is too large"})

    def test_upload_portrait_and_landscape_backgrounds(self):
        """Admin can upload portrait and landscape backgrounds and retrieve them."""
        csrf = self._login_admin()

        # Upload portrait
        response = self.client.post(
            "/api/admin/settings/background",
            data={"portrait": (io.BytesIO(b"portrait image"), "portrait.png")},
            headers={"X-CSRF-Token": csrf},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsNotNone(data["portrait"])
        self.assertTrue(data["portrait"].startswith("/media/backgrounds/portrait_"))
        self.assertTrue(data["portrait"].endswith(".png"))
        self.assertIsNone(data["landscape"])

        # Check public endpoint reflection
        public_resp = self.client.get("/api/settings/background")
        self.assertEqual(public_resp.status_code, 200)
        self.assertEqual(public_resp.get_json()["portrait"], data["portrait"])
        self.assertIsNone(public_resp.get_json()["landscape"])

        # Upload landscape
        response = self.client.post(
            "/api/admin/settings/background",
            data={"landscape": (io.BytesIO(b"landscape image"), "landscape.webp")},
            headers={"X-CSRF-Token": csrf},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsNotNone(data["portrait"])
        self.assertIsNotNone(data["landscape"])
        self.assertTrue(data["landscape"].startswith("/media/backgrounds/landscape_"))
        self.assertTrue(data["landscape"].endswith(".webp"))

    def test_replace_background_cleans_up_old_file(self):
        """Uploading a new background cleans up previous file on disk."""
        csrf = self._login_admin()

        # Upload initial portrait
        resp1 = self.client.post(
            "/api/admin/settings/background",
            data={"portrait": (io.BytesIO(b"first image"), "first.jpg")},
            headers={"X-CSRF-Token": csrf},
            content_type="multipart/form-data",
        )
        first_path = resp1.get_json()["portrait"].removeprefix("/media/")
        full_first_file = Path(self.temp_media_dir) / first_path
        self.assertTrue(full_first_file.is_file())

        # Upload second portrait
        resp2 = self.client.post(
            "/api/admin/settings/background",
            data={"portrait": (io.BytesIO(b"second image"), "second.png")},
            headers={"X-CSRF-Token": csrf},
            content_type="multipart/form-data",
        )
        second_path = resp2.get_json()["portrait"].removeprefix("/media/")
        full_second_file = Path(self.temp_media_dir) / second_path
        self.assertTrue(full_second_file.is_file())
        self.assertFalse(full_first_file.is_file())

    def test_delete_background_setting(self):
        """Admin can delete portrait, landscape, or all background settings."""
        csrf = self._login_admin()

        # Upload both
        self.client.post(
            "/api/admin/settings/background",
            data={
                "portrait": (io.BytesIO(b"portrait"), "portrait.jpg"),
                "landscape": (io.BytesIO(b"landscape"), "landscape.jpg"),
            },
            headers={"X-CSRF-Token": csrf},
            content_type="multipart/form-data",
        )

        with app.app_context():
            settings = get_background_settings()
            self.assertIsNotNone(settings["portrait"])
            self.assertIsNotNone(settings["landscape"])

        # Invalid orientation delete
        resp_invalid = self.client.delete(
            "/api/admin/settings/background/invalid_mode",
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(resp_invalid.status_code, 400)

        # Delete portrait
        resp_del = self.client.delete(
            "/api/admin/settings/background/portrait",
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(resp_del.status_code, 200)
        data = resp_del.get_json()
        self.assertIsNone(data["portrait"])
        self.assertIsNotNone(data["landscape"])

        # Delete landscape
        resp_del2 = self.client.delete(
            "/api/admin/settings/background/landscape",
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(resp_del2.status_code, 200)
        data2 = resp_del2.get_json()
        self.assertIsNone(data2["portrait"])
        self.assertIsNone(data2["landscape"])


if __name__ == "__main__":
    unittest.main()
