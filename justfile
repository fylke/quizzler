default: test

sync:
    uv sync --group test

hardening:
    uv run python -m scripts.check_hardening

backend:
    uv run python -m unittest discover -s test_backend -p 'test_*.py'

frontend:
    #!/usr/bin/env bash
    set -euo pipefail
    uv run --group test python - <<'PY'
    from pathlib import Path
    import sys

    from playwright.sync_api import sync_playwright


    spec_runner = Path("test_frontend/SpecRunner.html").resolve()
    url = f"file://{spec_runner}"

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

e2e:
    uv run --group test python -m pytest test_e2e/

test: sync backend frontend e2e
