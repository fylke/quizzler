# Scripts

This directory contains utility scripts used for local development, deployment, and maintenance tasks.

## Overview

- `seed_db.py`: Seeds the database with admin account(s) and destination data.
- `check_hardening.py`: Validates repository hardening policies used by CI/deployment.
- `generate_small_webp.py`: Generates optimized `_small.webp` hint images from existing media files.
- `entrypoint.sh`: Container startup entrypoint (seed first, then run app).

## Script Details

### `seed_db.py`

Seeds destination data and bootstrap admin credentials.

Behavior Summary:
- Runs `db.create_all()` and applies minimal SQLite schema compatibility for legacy DBs.
- Seeds admin account(s) and destination rows if missing.
- Uses `data/countries.json` by default.
- Falls back to `data/destinations.json` if the default seed file does not exist.
- Skips existing destinations/admins unless explicit updates are needed.

Run:

```bash
uv run python -m scripts.seed_db
```

Common Environment Variables:
- `SEED_DATA_PATH`: Custom path to destination seed JSON.
- `ADMIN_BOOTSTRAP_EMAIL`: Bootstrap admin email.
- `ADMIN_BOOTSTRAP_PASSWORD`: Bootstrap admin password (must be >= 12 chars).
- `REQUIRE_CUSTOM_ADMIN_BOOTSTRAP=true`: Fail startup if no custom admin password is provided and no admin exists.

### `check_hardening.py`

Checks hardening expectations such as:

- Security header presence in backend setup.
- Pinned GitHub Action SHAs in workflows.
- Required container/workflow hardening flags.

Run directly:

```bash
uv run python -m scripts.check_hardening
```

Or via just target:

```bash
just hardening
```

### `generate_small_webp.py`

Converts hint images to optimized WebP variants with `_small` suffix.

Example Conversions:
- `5a.jpg` -> `5a_small.webp`
- `2b.png` -> `2b_small.webp`

Default Behavior:
- Scans `media/countries` recursively.
- Processes names matching hint image slots (`1a`..`5b`) with extensions `.jpg`, `.jpeg`, `.png`, `.webp`.
- Writes `_small.webp` files next to the originals.
- Skips existing `_small.webp` files unless `--overwrite` is set.

Run directly:

```bash
uv run generate-small-webp --root media/countries --max-width 960 --max-height 960 --quality 72
```

Convenience Just Target:

```bash
just generate-small-webp
```

Overwrite Existing Optimized Files:

```bash
just generate-small-webp overwrite=true
```

### `entrypoint.sh`

Used by the container image at startup.

Flow:

1. Runs database seeding via `scripts.seed_db`.
2. Starts the Flask backend module.

This keeps container boot deterministic for new/empty volumes.

## Notes

- Keep scripts idempotent where possible so they are safe to rerun.
- Prefer failing fast on invalid input/configuration to avoid silent partial changes.
