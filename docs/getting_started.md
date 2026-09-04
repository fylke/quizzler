# Getting Started

This guide covers local setup, daily commands, and basic app usage.

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Git

Optional for container workflows:

- Podman
- podman-compose

### Dev Containers

Use Podman Compose commands from the host workspace, before opening the
repository in a devcontainer. Running `just podman-up` or
`just podman-up-local` inside the devcontainer requires nested Podman support,
which is not provided by the standard development container runtime.

Inside the devcontainer, run the application directly:

```bash
uv run python -m backend
```

The devcontainer starts this command automatically after it starts. The app is
available at http://localhost:5000.

### Rootless Podman on WSL

Rootless Podman bridge networking requires a running systemd user session. Enable
systemd in the host WSL distribution's `/etc/wsl.conf`:

```ini
[boot]
systemd=true
```

From Windows PowerShell, restart WSL after saving the file:

```powershell
wsl --shutdown
```

Reopen the host distribution and verify that the user D-Bus socket exists before
running a Podman command:

```bash
test -S /run/user/$(id -u)/bus
```

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
just backend
just frontend
just frontend_integration
just e2e
just test
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
