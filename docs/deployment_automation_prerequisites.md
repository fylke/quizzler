# Deployment Automation Prerequisites

This document covers GitHub-side setup and workflow behavior for automated deploys.

Manual QNAP operator tasks are documented in [deployment_checklist.md](deployment_checklist.md).

---

## Deployment Trigger Policy

- Production deployment is intentionally tag-only.
- The deploy workflow runs build and deploy only for tags matching `v*` (for example `v1.4.0`).
- Pushes to `main` do not deploy to QNAP.

---

## Required GitHub Secrets

Configure these in repository settings under Settings -> Secrets and variables -> Actions.

| Secret | Purpose |
| --- | --- |
| `FLASK_SECRET_KEY` | Flask session signing key used at runtime |
| `QNAP_HOST` | QNAP hostname or IP address |
| `QNAP_SSH_PORT` | SSH port for QNAP |
| `QNAP_USER` | SSH username on QNAP |
| `QNAP_SSH_KEY` | Private SSH key used by deploy workflow |
| `QNAP_GHCR_TOKEN` | GitHub token with `read:packages` for image pulls on QNAP |
| `ADMIN_BOOTSTRAP_PASSWORD` | Bootstrap admin password used by seeding step |
| `ADMIN_BOOTSTRAP_EMAIL` | Optional bootstrap admin email (defaults to `admin@example.com`) |

Notes:
- Use a long random value for `FLASK_SECRET_KEY` (32+ characters).
- `ADMIN_BOOTSTRAP_PASSWORD` should be at least 12 characters.

---

## SSH Key Setup For Automation

1. Generate a dedicated key pair for deploy automation:

```bash
ssh-keygen -t ed25519 -C "deploy@quizzler" -f deploy_key
```

2. Add the public key to target QNAP user `~/.ssh/authorized_keys`.
3. Save private key contents as GitHub secret `QNAP_SSH_KEY`.
4. Validate connection from your workstation:

```bash
ssh -i deploy_key -p <port> <user>@<qnap-host> "echo ok"
```

---

## GHCR Token Setup

1. Create a GitHub Personal Access Token with `read:packages` scope.
2. Save it as secret `QNAP_GHCR_TOKEN`.
3. Optional manual validation from QNAP shell:

```bash
echo "$TOKEN" | docker login ghcr.io -u <github-user> --password-stdin
```

---

## What The Deploy Workflow Verifies

For tag deploys, the workflow performs these checks automatically:
- Verifies image signature before deploy.
- Pulls immutable image reference by digest.
- Starts container with hardening flags and mounted paths.
- Waits for in-container health endpoint readiness.
- Runs seed step with bootstrap admin env vars.
- Verifies post-deploy health and bootstrap-admin login when password secret is set.

Operational recommendation:
- Keep using immutable image references (digest) for troubleshooting and rollback confidence.
