default: test

sync:
    uv sync --group test

hardening:
    uv run python -m scripts.check_hardening

podman-up:
    podman-compose -p quizzler -f podman-compose.yml up --build -d

podman-up-local:
    QUIZZLER_CPUS=0 QUIZZLER_MEM_LIMIT=0 QUIZZLER_PIDS_LIMIT=2048 podman-compose -p quizzler -f podman-compose.yml up --build -d

podman-down:
    podman-compose -p quizzler -f podman-compose.yml down

format:
    uv run black .
    uv run isort .

playwright-install:
    uv run --group test playwright install

backend seed='':
    #!/usr/bin/env bash
    set -euo pipefail
    seed_value="{{seed}}"
    seed_value="${seed_value#seed=}"
    if [[ -z "$seed_value" ]]; then
        seed_value="$(date +%s)"
    fi
    echo "Running backend tests with random seed: $seed_value"
    uv run --group test python -m pytest test_backend --randomly-seed="$seed_value"

frontend seed='':
    #!/usr/bin/env bash
    set -euo pipefail
    seed_value="{{seed}}"
    seed_value="${seed_value#seed=}"
    if [[ -z "$seed_value" ]]; then
        seed_value="$(date +%s)"
    fi
    echo "Running frontend specs with random seed: $seed_value"
    export JASMINE_RANDOM=true
    export JASMINE_SEED="$seed_value"
    uv run --group test python - <<'PY'
    from pathlib import Path
    import sys

    from playwright.sync_api import sync_playwright


    import os

    spec_runner = Path("test_frontend/SpecRunner.html").resolve()
    seed = os.environ.get("JASMINE_SEED", "")
    randomize = os.environ.get("JASMINE_RANDOM", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    url = f"file://{spec_runner}"
    if randomize:
        seed = seed or str(int(__import__("time").time()))
        url = f"{url}?random=true&seed={seed}"
        print(f"Jasmine randomization enabled with seed: {seed}")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        page.wait_for_selector(".jasmine-overall-result", timeout=30000)

        summary = page.locator(".jasmine-overall-result").inner_text()
        print(summary)

        has_failures = (
            "failure" in summary.lower() and "0 failures" not in summary.lower()
        )
        if has_failures:
            failure_messages = (
                page.locator(".jasmine-failures .jasmine-spec-detail").all_inner_texts()
                or page.locator(".jasmine-failure-message").all_inner_texts()
            )
            for message in failure_messages:
                print(f"  FAILED: {message}")
            browser.close()
            sys.exit(1)

        browser.close()
    PY

e2e seed='':
    #!/usr/bin/env bash
    set -euo pipefail
    seed_value="{{seed}}"
    seed_value="${seed_value#seed=}"
    if [[ -z "$seed_value" ]]; then
        seed_value="$(date +%s)"
    fi
    echo "Running e2e tests with random seed: $seed_value"
    uv run --group test python -m pytest test_e2e/ --randomly-seed="$seed_value"

test:
    #!/usr/bin/env bash
    set -euo pipefail

    just sync

    tmp_dir="$(mktemp -d)"
    trap 'rm -rf "$tmp_dir"' EXIT

    overall_status=0
    base_seed="$(date +%s)"
    backend_seed="$base_seed"
    frontend_seed="$((base_seed + 1))"
    e2e_seed="$((base_seed + 2))"

    echo "Randomized suite seeds: backend=$backend_seed frontend=$frontend_seed e2e=$e2e_seed"

    just backend "$backend_seed" 2>&1 | tee "$tmp_dir/backend.log"
    backend_status=${PIPESTATUS[0]}
    if [[ $backend_status -ne 0 ]]; then
        overall_status=1
    fi

    backend_total=$(grep -Eo 'collected [0-9]+ items' "$tmp_dir/backend.log" | tail -1 | awk '{print $2}' || true)
    backend_total=${backend_total:-0}
    backend_passed=$(grep -Eo '[0-9]+ passed' "$tmp_dir/backend.log" | tail -1 | awk '{print $1}' || true)
    backend_failed=$(grep -Eo '[0-9]+ failed' "$tmp_dir/backend.log" | tail -1 | awk '{print $1}' || true)
    backend_failed=${backend_failed:-0}
    if [[ -z "${backend_passed:-}" ]]; then
        backend_passed=$((backend_total - backend_failed))
        if [[ $backend_passed -lt 0 ]]; then
            backend_passed=0
        fi
    fi

    just frontend "$frontend_seed" 2>&1 | tee "$tmp_dir/frontend.log"
    frontend_status=${PIPESTATUS[0]}
    if [[ $frontend_status -ne 0 ]]; then
        overall_status=1
    fi

    frontend_counts=$(grep -Eo '[0-9]+ specs, [0-9]+ failures' "$tmp_dir/frontend.log" | tail -1 || true)
    if [[ -n "$frontend_counts" ]]; then
        read -r frontend_total frontend_failures <<<"$(echo "$frontend_counts" | sed -E 's/([0-9]+) specs, ([0-9]+) failures/\1 \2/')"
    else
        frontend_total=0
        frontend_failures=0
    fi
    frontend_passed=$((frontend_total - frontend_failures))
    if [[ $frontend_passed -lt 0 ]]; then
        frontend_passed=0
    fi

    just e2e "$e2e_seed" 2>&1 | tee "$tmp_dir/e2e.log"
    e2e_status=${PIPESTATUS[0]}
    if [[ $e2e_status -ne 0 ]]; then
        overall_status=1
    fi

    e2e_total=$(grep -Eo 'collected [0-9]+ items' "$tmp_dir/e2e.log" | tail -1 | awk '{print $2}' || true)
    e2e_total=${e2e_total:-0}
    e2e_passed=$(grep -Eo '[0-9]+ passed' "$tmp_dir/e2e.log" | tail -1 | awk '{print $1}' || true)
    e2e_failed=$(grep -Eo '[0-9]+ failed' "$tmp_dir/e2e.log" | tail -1 | awk '{print $1}' || true)
    e2e_failed=${e2e_failed:-0}
    if [[ -z "${e2e_passed:-}" ]]; then
        e2e_passed=$((e2e_total - e2e_failed))
        if [[ $e2e_passed -lt 0 ]]; then
            e2e_passed=0
        fi
    fi

    echo
    echo 'Test results:'
    echo "backend: $backend_passed of $backend_total passed (seed: $backend_seed)"
    echo "frontend: $frontend_passed of $frontend_total passed (seed: $frontend_seed)"
    echo "e2e: $e2e_passed of $e2e_total passed (seed: $e2e_seed)"

    exit $overall_status
