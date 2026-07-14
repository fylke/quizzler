# Getting Started

This guide covers local setup, daily commands, and basic app usage.

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Git

Optional for container workflows:

- Podman
- podman-compose

## Installation

1. Clone and enter the repo.

```bash
git clone <repo-url>
cd quizzler
```

2. Install dependencies.

```bash
uv sync
```

3. Start the app.

```bash
uv run python -m backend
```

4. Open http://localhost:5000

## Optional Direnv Setup

If you use direnv:

```bash
sudo apt install direnv
echo 'eval "$(direnv hook bash)"' >> ~/.bashrc
source ~/.bashrc
direnv allow
```

## Common Commands

```bash
just hardening
just format
just generate-small-webp
just podman-up
just podman-up-local
just podman-down
```

Command details are documented in [../justfile](../justfile).

## Guest Mode

Guest mode is available from the welcome screen.

Behavior:
- Progress and scoring are stored server-side.
- Browser cookie identifies the guest session.
- You can later create an account and migrate progress.

Restrictions:

- Clearing cookies removes guest session continuity.
- Admin and account-only features still require login.

## Project Structure

High-level structure:

- backend: Flask app and API routes
- frontend: HTML, CSS, and JS app
- scripts: utility/maintenance scripts
- test_backend: backend unit tests
- test_frontend: Jasmine frontend specs
- test_e2e: Playwright end-to-end tests
- docs: architecture and operational docs

## Related Guides

- Testing guide: [testing.md](testing.md)
- Operations guide: [operations.md](operations.md)
- Scripts guide: [../scripts/README.md](../scripts/README.md)
