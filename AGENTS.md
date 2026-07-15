# AGENTS.md

Guidelines for AI agents working on the Quizzler project.

## Hard Rules

- E2E tests must be run via `just e2e` (or `just e2e-single <selector>` for a single test). Do not run Playwright E2E tests with direct `uv run pytest ...` commands.

## Project Overview

A Flask-based quizzler webapp with a vanilla JS frontend. Users log in, answer geography/travel questions with progressive hints, and earn points. Admins can manage quiz destinations via a CRUD API.

## Tech Stack

- **Backend**: Python 3.10+, Flask, SQLAlchemy, SQLite
- **Frontend**: Vanilla JavaScript, HTML5, CSS3
- **Package manager**: [uv](https://docs.astral.sh/uv/)
- **Containerization**: Podman / podman-compose
- **CI**: GitHub Actions

## Setup

```bash
uv sync            # Install all dependencies
uv sync --group test  # Include test dependencies (Playwright, Hypothesis)
```

## Running the App

```bash
uv run python -m backend   # Starts Flask on http://localhost:5000
```

Or via Podman:
```bash
podman-compose -f podman-compose.yml up --build
```

## Common Tasks

```bash
just hardening
```

- `just hardening` runs the repository hardening policy checks.

## Testing

### Unit Tests

```bash
just backend
```

Uses `unittest` and discovers tests in the `test_backend/` directory. Some test files use the `hypothesis` library for property-based testing.

### End-to-End Tests

```bash
uv run playwright install   # First time only
just e2e
```

Uses `pytest` + `playwright` against `test_e2e/`.

**Important**: Playwright does not officially support this Ubuntu version. Before running e2e tests locally, apply the platform detection patch:

```bash
uv run python -c "
import pathlib, playwright
base = pathlib.Path(playwright.__file__).parent / 'driver' / 'package' / 'lib'
targets = list(base.glob('**/hostPlatform.js')) + list(base.glob('coreBundle.js'))
for p in targets:
    if p.exists():
        text = p.read_text()
        text = text.replace('\"ubuntu\" + distroInfo.version + archSuffix', '\"ubuntu24.04\" + archSuffix')
        text = text.replace(\"'ubuntu' + distroInfo.version + archSuffix\", \"'ubuntu24.04' + archSuffix\")
        p.write_text(text)
"
```

### Before Pushing

Always run all relevant tests locally before pushing:

```bash
just test           # Full backend + frontend + e2e suite
```

Do not rely on CI round-trips to catch failures. Iterate locally until tests pass, then push once.

### Frontend Tests

Jasmine specs live in `test_frontend/spec/`. Run them with `just frontend`.

## Code Style

- **Formatter**: Black (line length default 88)
- **Import sorting**: isort (profile: black)
- Pre-commit hooks enforce both on Python files.

Run manually:
```bash
uv run black .
uv run isort .
```

## Project Layout

```
backend/          # Flask application (routes, models, admin helpers, stats)
frontend/         # Static HTML/CSS/JS served by Flask
database/         # Runtime-generated SQLite database directory
docs/             # Design documentation and diagrams
scripts/          # CLI entry points and utility scripts
test_backend/     # Unit tests (unittest + hypothesis)
test_e2e/         # End-to-end tests (pytest + playwright)
test_frontend/    # Frontend Jasmine specs
```

## Key Architecture Decisions

- Server-side quiz state: hint difficulty, remaining guesses, and scoring are tracked in the `quiz_result` table — never trust the client.
- CSRF protection via `X-CSRF-Token` header matched against session-stored tokens.
- Rate limiting on `/api/login` (5 per minute) using flask-limiter.
- Session-based auth with `login_required` and `admin_required` decorators.
- Database URL is configurable via `QUIZ_DATABASE_URL` or `DATABASE_URL` env vars; defaults to `database/quiz_data.db`.

## Environment Variables

| Variable                             | Purpose                                        | Default                           |
| --------------------------------------| ------------------------------------------------| -----------------------------------|
| `SECRET_KEY`                         | Flask session signing (required in production) | insecure fallback in dev          |
| `QUIZ_DATABASE_URL` / `DATABASE_URL` | SQLAlchemy database URI                        | `sqlite:///database/quiz_data.db` |
| `CORS_ALLOWED_ORIGINS`               | Comma-separated allowed origins                | `*`                               |
| `RATELIMIT_STORAGE_URI`              | Flask-Limiter backend                          | `memory://`                       |
| `SESSION_COOKIE_SECURE`              | Set cookie secure flag                         | `false`                           |
| `SMTP_HOST`                          | SMTP server hostname for sending emails        | _(none)_                          |
| `SMTP_PORT`                          | SMTP server port (1–65535)                     | _(none)_                          |
| `SMTP_USERNAME`                      | SMTP authentication username                   | _(none)_                          |
| `SMTP_PASSWORD`                      | SMTP authentication password                   | _(none)_                          |
| `SMTP_FROM_ADDRESS`                  | Sender address for outgoing emails             | _(none)_                          |
| `SMTP_USE_TLS`                       | Use TLS for SMTP connection ("true" enables)   | _(not set)_                       |

## Conventions

- Keep routes in `backend/__init__.py`; extract helpers to dedicated modules (`admin.py`, `stats.py`).
- Destination hints are stored as columns `hint1`–`hint5` (difficulty 1 = easiest, 5 = hardest).
- Correct answers are stored as a JSON list of lowercase strings.
- All API endpoints return JSON. Errors use `{"error": "message"}` with appropriate HTTP status codes.
- Tests use an in-memory SQLite database — never modify `database/quiz_data.db` in tests.
- When designing solutions, the policy should be to "fail fast" - if input data is not on the expected form, no attempt should be made to fix it in the app, instead more care should be take at system boundry to make sure input is on the correct format before sending it on.
- Deprecation warnings should be taken seriously and be fixed.
- When adding tests; avoid testing specific strings, unless they represent state.
- In `just` recipes and other automation, prefer the project environment over global tools. Use `uv run ...` when `uv` is available, since it resolves and runs inside the project environment; fall back to direct `.venv/bin/...` executables only when `uv` is unavailable. Keep `uv` as the provisioning path for `just sync`.
