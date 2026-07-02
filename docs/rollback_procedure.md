# Rollback Procedure

This document describes how to roll back a QNAP deployment safely.

## Scope

Use this runbook for production incidents where a newly deployed container is unhealthy or behavior regresses.

The project has two rollback paths:

- Automatic rollback in deploy workflow: [.github/workflows/deploy-qnap.yml](../.github/workflows/deploy-qnap.yml)
- Manual rollback workflow: [.github/workflows/rollback-qnap.yml](../.github/workflows/rollback-qnap.yml)

A scheduled readiness check also exists:

- Rollback self-test workflow: [.github/workflows/rollback-self-test.yml](../.github/workflows/rollback-self-test.yml)

## Rollback model

Rollback containers are kept with generation names:

- `quizzler-rollback-1` (most recent previous deployment)
- `quizzler-rollback-2`
- `quizzler-rollback-3`

The active container name is always:

- `quizzler`

## Before you roll back

1. Confirm the current failure in the latest deployment run logs.
2. Check health endpoint from host/container context.
3. Confirm the rollback generation you want to restore.

## Manual rollback (recommended during incident)

1. Open GitHub Actions and run workflow [rollback-qnap.yml](../.github/workflows/rollback-qnap.yml) using `workflow_dispatch`.
2. Select input `generation`:
   - `1` = most recent previous release
   - `2` = older release
   - `3` = oldest retained release
3. Start the workflow.
4. Verify workflow result is successful.
5. Verify service health on QNAP:
   - Container health probe should pass.
   - Application endpoint `/health` should return healthy.
6. Monitor application behavior and error logs for at least 10-15 minutes.

## Automatic rollback behavior

During tagged deploy, if the new container fails readiness checks, the deploy workflow attempts to restore generation 1 automatically.

If automatic rollback fails, run manual rollback immediately using generation 1, then 2 if needed.

## Post-rollback verification checklist

1. Confirm active container is `quizzler` and running.
2. Confirm `/health` responds successfully.
3. Validate login and one quiz round manually.
4. Confirm no database migration/data integrity errors in logs.
5. Record incident summary and selected rollback generation.

## Recovery and follow-up

1. Open or update incident issue.
2. Link failing deploy run and rollback run.
3. Identify regression commit/tag.
4. Prepare fix in a new branch and redeploy after validation.
5. Keep at least one known-good rollback generation available.

## Troubleshooting

### No rollback container found

- Meaning: `quizzler-rollback-<n>` does not exist.
- Action: choose another available generation or redeploy last known good tag.

### Rollback container starts but health fails

- Check container logs on QNAP.
- Validate DB connectivity and mounted volume permissions.
- Try older generation (`2` then `3`).

### Rollback workflow fails to connect to QNAP

- Verify secrets: `QNAP_HOST`, `QNAP_SSH_PORT`, `QNAP_USER`, `QNAP_SSH_KEY`.
- Verify Docker binary resolution paths in workflow scripts.
