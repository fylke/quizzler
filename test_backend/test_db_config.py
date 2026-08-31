"""Unit tests for database connection error handling.

Validates Requirements: 2.4, 8.3
"""

import os
import subprocess
import sys
import unittest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class TestConnectionFailureExit(unittest.TestCase):
    """Test that connection failure with a PostgreSQL URI causes non-zero exit.

    Validates Requirement 2.4: If the Database_Driver fails to establish a
    connection to the PostgreSQL server within 5 seconds, the App_Container
    SHALL exit with a non-zero status code.
    """

    def _run_app_import(self, env_overrides):
        """Import the app in a subprocess with given environment."""
        env = os.environ.copy()
        # Clear any existing DB-related env vars
        env.pop("QUIZ_DATABASE_URL", None)
        env.pop("DATABASE_URL", None)
        env.pop("SECRET_KEY", None)
        env.update(env_overrides)
        result = subprocess.run(
            [sys.executable, "-c", "from backend import app; print('OK')"],
            capture_output=True,
            text=True,
            cwd=ROOT_DIR,
            env=env,
            timeout=30,
        )
        return result

    def test_unreachable_postgresql_causes_nonzero_exit(self):
        """App exits with non-zero status when PostgreSQL is unreachable."""
        result = self._run_app_import(
            {
                "QUIZ_DATABASE_URL": "postgresql+psycopg2://user:pass@localhost:59999/nonexistent",
            }
        )
        self.assertNotEqual(result.returncode, 0)
        # Should log a connection error
        self.assertIn("connection failed", result.stderr.lower())


class TestMissingDatabaseDirectory(unittest.TestCase):
    """Test auto-creation behavior when database/ directory is missing.

    Validates Requirement 8.3: If the App_Container starts without a
    QUIZ_DATABASE_URL or DATABASE_URL and without a database/ directory,
    it SHALL create the directory and start successfully.
    """

    def _run_app_in_temp_dir(self, env_overrides=None):
        """Run the app import from a temp directory where database/ doesn't exist."""
        import shutil
        import tempfile

        env = os.environ.copy()
        env.pop("QUIZ_DATABASE_URL", None)
        env.pop("DATABASE_URL", None)
        env.pop("SECRET_KEY", None)
        if env_overrides:
            env.update(env_overrides)

        # Create a temporary copy of the project without the database/ directory
        with tempfile.TemporaryDirectory() as tmpdir:
            # Copy only the necessary Python source files
            shutil.copytree(
                os.path.join(ROOT_DIR, "backend"),
                os.path.join(tmpdir, "backend"),
            )
            # Copy pyproject.toml so imports work
            shutil.copy2(
                os.path.join(ROOT_DIR, "pyproject.toml"),
                os.path.join(tmpdir, "pyproject.toml"),
            )

            # Use the same venv to have all dependencies available
            result = subprocess.run(
                [sys.executable, "-c", "from backend import app; print('OK')"],
                capture_output=True,
                text=True,
                cwd=tmpdir,
                env=env,
                timeout=30,
            )
        return result

    def test_no_env_vars_and_no_database_dir_is_created(self):
        """App starts successfully when database/ is missing and no env vars are set."""
        result = self._run_app_in_temp_dir()
        self.assertEqual(
            result.returncode,
            0,
            msg=f"Expected success but got: {result.stderr}",
        )

    def test_with_quiz_database_url_set_no_database_dir_needed(self):
        """App does NOT fail when QUIZ_DATABASE_URL is set even without database/ dir."""
        # Use in-memory SQLite so no real connection is needed
        result = self._run_app_in_temp_dir(
            env_overrides={"QUIZ_DATABASE_URL": "sqlite:///:memory:"}
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"Expected success but got: {result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
