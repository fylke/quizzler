# ✈️ Quizzler Webapp

[![CI](https://github.com/fylke/quizzler/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/fylke/quizzler/actions/workflows/ci.yml)
[![Deploy to QNAP](https://github.com/fylke/quizzler/actions/workflows/deploy-qnap.yml/badge.svg?branch=main)](https://github.com/fylke/quizzler/actions/workflows/deploy-qnap.yml)
[![backup-qnap](https://github.com/fylke/quizzler/actions/workflows/backup-qnap.yml/badge.svg?branch=main)](https://github.com/fylke/quizzler/actions/workflows/backup-qnap.yml)
[![E2E Nightly](https://github.com/fylke/quizzler/actions/workflows/e2e-nightly.yml/badge.svg?branch=main)](https://github.com/fylke/quizzler/actions/workflows/e2e-nightly.yml)
[![Dependabot](https://img.shields.io/badge/Dependabot-enabled-025E8C?logo=dependabot)](https://github.com/fylke/quizzler/blob/main/.github/dependabot.yml)

A quiz game where you are presented with a number of progressively easier hints that are both text- and picture based. The earlier you guess correctly, the higher the score.

## Quick Start

```bash
git clone <repo-url>
cd quizzler
uv sync
uv run python -m backend
```

Open http://localhost:5000

## Documentation Index

Core guides:

- Getting started and local workflows: [docs/getting_started.md](docs/getting_started.md)
- Testing (backend/frontend/e2e, seeds, reproducibility): [docs/testing.md](docs/testing.md)
- Operations (env vars, podman, backup/restore): [docs/operations.md](docs/operations.md)
- Utility scripts overview: [scripts/README.md](scripts/README.md)

Gameplay and architecture:

- Product/flow overview: [docs/overview.md](docs/overview.md)
- Login/auth flow notes: [docs/login.md](docs/login.md)
- Hint lifecycle and behavior: [docs/hint.md](docs/hint.md)
- Answer checking flow: [docs/check_answer.md](docs/check_answer.md)
- Media naming and optimization: [docs/media_images.md](docs/media_images.md)
- Database schema: [docs/database_schema.md](docs/database_schema.md)

Admin and runbooks:

- Admin page behavior: [docs/admin_page.md](docs/admin_page.md)
- Deployment checklist: [docs/deployment_checklist.md](docs/deployment_checklist.md)
- Rollback procedure: [docs/rollback_procedure.md](docs/rollback_procedure.md)

## Tech Stack

- Backend: Flask + SQLAlchemy
- Frontend: Vanilla JavaScript, HTML5, CSS3
- Testing: pytest, Jasmine, Playwright
- Tooling: uv, just, Podman

## License

MIT License
