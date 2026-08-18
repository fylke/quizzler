# Operations Guide

This guide summarizes runtime configuration, container workflows, backups, and runbooks.

## Environment Variables

| Variable | Description | Example |
| --- | --- | --- |
| SECRET_KEY | Flask session signing key (required in production) | change-me-in-production |
| QUIZ_DATABASE_URL | SQLAlchemy database URI | sqlite:///database/quiz_data.db |
| SMTP_HOST | SMTP server hostname | smtp.gmail.com |
| SMTP_PORT | SMTP server port (1-65535) | 587 |
| SMTP_USERNAME | SMTP auth username | user@gmail.com |
| SMTP_PASSWORD | SMTP auth password | app-password |
| SMTP_FROM_ADDRESS | Sender address | noreply@quizzler.com |
| SMTP_USE_TLS | Use TLS if set to true | true |
| ADMIN_EMAIL | Hint complaint destination email | (none) |

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

- /share/Container/quizzler/database/quiz_data.db
- /share/Container/quizzler/media

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
