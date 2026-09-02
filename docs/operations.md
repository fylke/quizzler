# Operations Guide

This guide summarizes runtime configuration, container workflows, backups, and runbooks.

## Environment Variables

| Variable | Description | Example |
| --- | --- | --- |
| SECRET_KEY | Flask session signing key (required in production) | change-me-in-production |
| QUIZ_DATABASE_URL | SQLAlchemy database URI; takes precedence over `DATABASE_URL` | sqlite:///database/quiz_data.db |
| DATABASE_URL | Fallback SQLAlchemy database URI when `QUIZ_DATABASE_URL` is not set | sqlite:///database/quiz_data.db |
| CORS_ALLOWED_ORIGINS | Comma-separated allowed origins; must be explicit in production | https://quizzler.example.com |
| SESSION_COOKIE_SECURE | Set to `true` when served over HTTPS | true |
| SMTP_HOST | SMTP server hostname | smtp.gmail.com |
| SMTP_PORT | SMTP server port (1-65535) | 587 |
| SMTP_USERNAME | SMTP auth username | user@gmail.com |
| SMTP_PASSWORD | SMTP auth password | app-password |
| SMTP_FROM_ADDRESS | Sender address | noreply@quizzler.com |
| SMTP_USE_TLS | Use TLS if set to true | true |
| ADMIN_EMAIL | Hint complaint destination email | (none) |

`SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and
`SMTP_FROM_ADDRESS` are required when sending password-reset or complaint
email. `SMTP_USE_TLS=true` enables STARTTLS for the SMTP connection.

In production, set `SECRET_KEY` and an explicit `CORS_ALLOWED_ORIGINS`; the
application rejects the insecure defaults. The deployment workflow stores the
secret as `FLASK_SECRET_KEY` in GitHub and passes it to the container as
`SECRET_KEY`.

## Podman Workflows

Prerequisites:

- Podman installed
- podman-compose installed

Run stack:

```bash
just podman-up
```

If local host does not support CPU/memory cgroup limits:

```bash
just podman-up-local
```

Stop stack:

```bash
just podman-down
```

App URL when using compose defaults:

- http://localhost:9696

## Backup and Restore

Automated weekly backup is defined in:

- [.github/workflows/backup-qnap.yml](../.github/workflows/backup-qnap.yml)

What it backs up:

- The SQLite database at `/share/CACHEDEV2_DATA/Container/quizzler/database/quiz_data.db`
- The media directory at `/share/CACHEDEV2_DATA/Container/quizzler/media`

The backup workflow writes timestamped `db_*.tar.gz` and `media_*.tar.gz`
archives under `/share/CACHEDEV2_DATA/Container/quizzler/backups` by default.
Set the `QNAP_BACKUP_DIR` repository variable to use another absolute QNAP
path.

The database backup includes the `quiz_identity` table and therefore preserves
existing shared quiz links. On startup and during seeding, Quizzler
idempotently creates missing catalog rows for registered quiz source tables.
A fresh database rebuild retains compact links when the source IDs and quiz type
codes are unchanged. Links for deleted or renumbered source rows are not
expected to resolve.

Manual workflow inputs:

- backup action with optional retention_count
- restore action with optional backup_id

Required GitHub secrets:

- QNAP_HOST
- QNAP_SSH_PORT
- QNAP_USER
- QNAP_SSH_KEY

## Runbooks

- Rollback procedure: [rollback_procedure.md](rollback_procedure.md)
- Deployment checklist: [deployment_checklist.md](deployment_checklist.md)

## Related Guides

- Getting started: [getting_started.md](getting_started.md)
- Testing: [testing.md](testing.md)
