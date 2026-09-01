#!/usr/bin/env bash
set -euo pipefail

: "${QUIZZLER_CI_DEVCONTAINER_IMAGE:?Set QUIZZLER_CI_DEVCONTAINER_IMAGE to the built devcontainer image tag}"

workspace_dir=${GITHUB_WORKSPACE:-$PWD}

docker run --rm --interactive \
    --user root \
    --env "QUIZ_DATABASE_URL" \
    --env "PLAYWRIGHT_BROWSERS_PATH=/home/vscode/.cache/ms-playwright" \
    --env "UV_PROJECT_ENVIRONMENT=/home/vscode/.venvs/quizzler" \
    --volume quizzler-ci-python-venv:/home/vscode/.venvs \
    --volume quizzler-ci-playwright:/home/vscode/.cache/ms-playwright \
    --volume "${workspace_dir}:/workspaces/quizzler" \
    --workdir /workspaces/quizzler \
    "$QUIZZLER_CI_DEVCONTAINER_IMAGE" \
    "$@"