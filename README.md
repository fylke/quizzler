# ✈️ Quizzler Webapp

[![CI](https://github.com/fylke/quizzler/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/fylke/quizzler/actions/workflows/ci.yml)
[![Deploy to QNAP](https://github.com/fylke/quizzler/actions/workflows/deploy-qnap.yml/badge.svg?branch=main)](https://github.com/fylke/quizzler/actions/workflows/deploy-qnap.yml)
[![backup-qnap](https://github.com/fylke/quizzler/actions/workflows/backup-qnap.yml/badge.svg?branch=main)](https://github.com/fylke/quizzler/actions/workflows/backup-qnap.yml)
[![E2E Nightly](https://github.com/fylke/quizzler/actions/workflows/e2e-nightly.yml/badge.svg?branch=main)](https://github.com/fylke/quizzler/actions/workflows/e2e-nightly.yml)
[![Dependabot](https://img.shields.io/badge/Dependabot-enabled-025E8C?logo=dependabot)](https://github.com/fylke/quizzler/blob/main/.github/dependabot.yml)

A quiz game where you are presented with a number of progressively easier hints that are both text- and picture based. The earlier you guess correctly, the higher the score.

## Project Structure

```
quizzler/
├── data/
│   ├── countries.example.json  # Example country data
│   └── destinations.json       # Quiz destination seed data
├── backend/
│   ├── __init__.py          # Flask app initialization
│   ├── __main__.py          # Entry point
│   ├── admin.py             # Admin helpers and operations
│   ├── auth.py              # Authentication/session helpers
│   ├── email_service.py     # Password reset email delivery
│   ├── models.py            # SQLAlchemy models
│   ├── quiz_types.py        # Quiz mode/type logic
│   ├── reset_tokens.py      # Password reset token utilities
│   ├── routes_admin.py      # Admin API routes
│   ├── routes_auth.py       # Auth API routes
│   ├── routes_quiz.py       # Quiz API routes
│   ├── stats.py             # Statistics helpers
│   ├── validation_rules.py  # Validation helpers
│   └── assets/
│       ├── names.txt        # Name source data
│       └── rules/
│           └── countries.md # Country rule definitions
├── frontend/
│   ├── index.html          # Main HTML page
│   ├── style.css           # Styling
│   ├── app.js              # Core app logic (state, auth, quiz flow)
│   ├── admin.js            # Admin panel
│   ├── modal.js            # Modal dialogs and focus traps
│   ├── markdown.js         # Markdown renderer
│   └── reset_password.html # Password reset page
├── docs/                   # Design and operations documentation
├── scripts/                # Test and utility entry points
├── test_backend/           # Backend unit tests
├── test_e2e/               # End-to-end Playwright tests
├── test_frontend/          # Frontend Jasmine spec unit tests
├── media/                  # Media storage directory
├── pyproject.toml          # Project configuration
├── Containerfile           # Container build configuration
├── podman-compose.yml      # Podman Compose orchestration
└── README.md               # This file
```

## Setup Instructions

### Prerequisites
- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Git

### Installation

1. **Clone and enter the project:**
   ```bash
   git clone <repo-url>
   cd quizzler
   ```

2. **Install dependencies with uv:**
   ```bash
   uv sync
   ```

4. **(Optional) Auto-activate the venv with direnv:**

   If you'd like the virtual environment to activate automatically whenever you enter the project directory:

   ```bash
   # Install direnv (Ubuntu/Debian)
   sudo apt install direnv

   # Add the hook to your shell (bash)
   echo 'eval "$(direnv hook bash)"' >> ~/.bashrc
   source ~/.bashrc

   # Allow the .envrc included in the repo
   direnv allow
   ```

   Now the venv activates/deactivates automatically as you enter/leave the directory.

## Common Tasks

```bash
just hardening
just format
just playwright-install
just podman-up
just podman-up-local
just podman-down
```

- `just hardening` runs the repository hardening policy checks.
- `just format` runs `black` and `isort` across the repo.
- `just playwright-install` installs Playwright browser dependencies for e2e/frontend testing.
- `just podman-up` starts the Podman stack with the repo's Podman compatibility defaults.
- `just podman-up-local` starts the Podman stack with the same compatibility defaults plus local overrides for hosts that do not support CPU/memory cgroup limits.
- `just podman-down` stops the Podman stack.

## Running All Tests

If you use [just](https://github.com/casey/just), the repo provides a top-level `justfile`:

```bash
just test
```

This will install the test dependency group and then run backend unit tests, frontend Jasmine tests, and Playwright end-to-end tests in sequence.

`just test` now randomizes test/spec execution order by default and prints the per-suite seeds it used.

If you prefer running the equivalent commands directly:

```bash
uv sync --group test
just backend
just frontend
just e2e
```

This runs backend unit tests, frontend Jasmine tests, and Playwright end-to-end tests in sequence. The frontend step is now executed directly from the `justfile` and no longer uses a separate wrapper script.

## Randomized Test Order

Randomized ordering is the default for backend, frontend, e2e, and the aggregate `test` target.

Run randomized suites with auto-generated seeds:

```bash
just backend
just frontend
just e2e
just test
```

Use a fixed seed to reproduce a failure:

```bash
just backend 12345
just frontend 12345
just e2e 12345
```

The backend and e2e randomized commands use `pytest-randomly`.

## Running E2E Tests

```bash
uv sync --group test
just playwright-install
just e2e
```

Important: run E2E through `just` targets only (`just e2e` or `just e2e-single <pytest-selector>`). Avoid direct `uv run pytest ...` for E2E so repo-specific test wrappers stay consistent.

To run one E2E test with a reproducible seed:

```bash
just e2e-single "test_e2e/test_wrong_guess_animation.py::test_empty_input_animates_without_alert[chromium]" 12345
```

## Guest Mode

You can now play quizzes without creating an account by clicking **Continue as Guest** on the welcome screen.

Guest mode behavior:

- Quiz progress and scoring are tracked server-side.
- The browser stores a guest token cookie that links to that server-side state.
- You can run random/specific quizzes, use hints, submit answers, view quiz rules, and see stats.
- You can create an account or log in later and keep your guest progress.

Guest restrictions:

- Guest progress is bound to the current browser cookie.
- Clearing cookies (or moving to another browser/device) loses guest progress.
- Account-only features (for example admin access and account-based continuity) still require login.

### Podman

#### Prerequisites
- Podman installed ([Get Podman](https://podman.io/docs/installation))
- Podman Compose installed (`pip install podman-compose`)

#### Running with Podman Compose (Recommended)

1. **Build and start the container (-d for detached, to not block terminal):**
   ```bash
   just podman-up
   ```

   The Just targets load the repo's Podman compatibility module to force `cgroupfs`, a file-backed events backend, and `slirp4netns` for rootless Podman.

   If rootless Podman reports a missing systemd user bus such as `/run/user/1000/bus`, enable lingering for your user with `sudo loginctl enable-linger 1000`, restart WSL, and try again.

   If you get `cpu.max` errors, that's likely because your host doesn't support container CPU/memory cgroup limits. Use this target as workaround:
   ```bash
   just podman-up-local
   ```

2. **Open your browser and go to:**
   ```
   http://localhost:9696
   ```

3. **Stop the container:**
   ```bash
   just podman-down
   ```

## Environment Variables

| Variable            | Description                                                                     | Example                           |
| --------------------| --------------------------------------------------------------------------------| ----------------------------------|
| `SECRET_KEY`        | Flask session signing key (required in production)                              | `change-me-in-production`         |
| `QUIZ_DATABASE_URL` | SQLAlchemy database URI                                                         | `sqlite:///database/quiz_data.db` |
| `SMTP_HOST`         | SMTP server hostname for sending password reset emails                          | `smtp.gmail.com`                  |
| `SMTP_PORT`         | SMTP server port (1–65535)                                                      | `587`                             |
| `SMTP_USERNAME`     | SMTP authentication username                                                    | `user@gmail.com`                  |
| `SMTP_PASSWORD`     | SMTP authentication password                                                    | `app-password`                    |
| `SMTP_FROM_ADDRESS` | Sender address for outgoing emails                                              | `noreply@quizzler.com`            |
| `SMTP_USE_TLS`      | Use TLS for SMTP connection (`"true"` enables, any other value uses plain SMTP) | `true`                            |
| `ADMIN_EMAIL`       | Destination address for hint complaint emails                                   | _(none)_                          |

## Weekly Backup and Restore Workflow

The repository includes a GitHub Actions workflow at `.github/workflows/backup-qnap.yml` that performs weekly production backups on the QNAP host.

### What it does

- Runs automatically every Sunday at 02:15 UTC.
- Creates compressed backups for:
   - `/share/Container/quizzler/database/quiz_data.db`
   - `/share/Container/quizzler/media`
- Skips backup creation when neither the database nor media content changed since the previous backup.
- Validates backup content by:
   - running SQLite `PRAGMA quick_check` on the copied database
   - verifying archive readability (`tar -tzf`)
   - extracting and comparing checksums against source content
- Stores backups on QNAP under `/share/Container/quizzler/backups`.
- Automatically prunes older backup sets and keeps the latest 12 complete snapshots.

### Manual backup run

From GitHub Actions, run workflow **QNAP Backup and Restore** with:

- `action=backup`
- `retention_count=12` (optional, must be a positive integer)

### Manual restore (redeploy backup)

From GitHub Actions, run workflow **QNAP Backup and Restore** with:

- `action=restore`
- `backup_id=`

Set `backup_id` to a timestamp like `20260701T021500Z`, or leave it empty to restore the latest backup.

The restore job validates the selected archives, replaces live database/media content, and restarts the `quizzler` container if it was running.

If the container was running before restore, the workflow also runs a post-restore health check against `/health` and fails the run if the app does not become healthy in time.

### Backup and restore reports

Each successful workflow run uploads a JSON artifact with execution details:

- `backup-report-<run_id>` for backup runs
- `restore-report-<run_id>` for restore runs

Reports include backup identifier, selected archives, key checksums, and health-check status for restore.

### Required GitHub secrets

- `QNAP_HOST`
- `QNAP_SSH_PORT`
- `QNAP_USER`
- `QNAP_SSH_KEY`

## Operations Runbooks

- Rollback procedure: [docs/rollback_procedure.md](docs/rollback_procedure.md)

## Technologies Used

- **Backend**: Flask (Python web framework)
- **Frontend**: Vanilla JavaScript, HTML5, CSS3
- **Images**: Picsum (free placeholder images)
- **CORS**: Flask-CORS for cross-origin requests

## Browser Compatibility

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)
- Mobile browsers (iOS Safari, Chrome Mobile)

## License

MIT License - feel free to use and modify this project!

## Support

If you encounter any issues:
1. Make sure Python 3.10+ is installed
2. Make sure uv is installed: `uv --version`
3. Ensure dependencies are installed: `uv sync`
4. Check that the server is running on `http://localhost:5000`
5. Check browser console for any JavaScript errors (F12 → Console)

Enjoy the quizzes! 🌍✨
