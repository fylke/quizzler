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

## Running Unit Tests

```bash
uv run unit-test
```

## Running E2E Tests

```bash
uv sync --group test
uv run playwright install
uv run e2e-test
```

## Running the Application

### Podman

#### Prerequisites
- Podman installed ([Get Podman](https://podman.io/docs/installation))
- Podman Compose installed (`pip install podman-compose`)

#### Running with Podman Compose (Recommended)

1. **Build and start the container (-d for detached, to not block terminal):**
   ```bash
   podman-compose -p quizzler -f podman-compose.yml up --build -d
   ```

   If your host does not support container CPU/memory cgroup limits (for example `cpu.max` errors), disable CPU/memory limits for local runs but keep a non-zero process limit:
   ```bash
   QUIZZLER_CPUS=0 QUIZZLER_MEM_LIMIT=0 QUIZZLER_PIDS_LIMIT=2048 podman-compose -p quizzler -f podman-compose.yml up --build -d
   ```

   Or make the override persistent for your local checkout:
   ```bash
   cp .env.example .env
   podman-compose -p quizzler -f podman-compose.yml up --build -d
   ```

2. **Open your browser and go to:**
   ```
   http://localhost:9696
   ```

3. **Stop the container:**
   ```bash
   podman-compose -p quizzler -f podman-compose.yml down
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
