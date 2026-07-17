# Testing Guide

This project uses randomized test order by default.

Before running tests, install the test dependency group:

```bash
uv sync --group test
```

## Run All Test Suites

```bash
just test
```

This runs:

- Backend unit tests
- Frontend Jasmine specs
- End-to-end Playwright tests

## Run Individual Suites

```bash
just backend
just frontend
just frontend_integration
just e2e
```

## Frontend Integration Category

Use this target when you want frontend-focused integration tests that run against backend-rendered pages (instead of the static Jasmine fixture):

```bash
just frontend_integration_single "<pytest-selector>" [seed]
```

Examples:

```bash
just frontend_integration_single "test_e2e/test_quiz.py"
just frontend_integration_single "test_e2e/test_quiz.py::test_submit_correct_answer[chromium]" 12345
```

This target is a category alias and internally routes through `just e2e-single` to keep the repository E2E execution rule intact.

For a curated frontend integration suite, run:

```bash
just frontend_integration [seed]
```

This suite currently covers:

- `test_e2e/test_auth.py`
- `test_e2e/test_quiz.py`
- `test_e2e/test_wrong_guess_animation.py`
- `test_e2e/test_forgot_password.py`

## Reproduce with a Fixed Seed

```bash
just backend 12345
just frontend 12345
just e2e 12345
```

## End-to-End Rule

Run end-to-end tests only through just targets:

- just e2e
- just e2e-single <pytest-selector> [seed]

Example:

```bash
just e2e-single "test_e2e/test_wrong_guess_animation.py::test_empty_input_animates_without_alert[chromium]" 12345
```

## Playwright Browser Install

```bash
just playwright-install
```

## Notes

- Backend and end-to-end suites use pytest-randomly.
- Frontend specs are run via Playwright against test_frontend/SpecRunner.html.
- CI also runs `just frontend_integration` as a frontend-focused integration lane against backend-rendered pages.

## Home Markup Parity Guardrails

The app currently keeps two home-page markup sources during migration:

- Backend-rendered template at `/` (composed from `backend/templates/partials/*.html`)
- Static frontend fixture in `frontend/index.html` (used by frontend specs)

To prevent silent drift between those sources, backend tests include parity checks in `test_backend/test_main.py` that validate:

- Critical UI IDs exist in both rendered home markup and static fixture markup.
- Script bootstrap order stays aligned (`/static/app.js` through `/static/admin.js`).
- Top-level screen and modal section ordering remains consistent.

When changing home-page markup or script tags, update both files and keep these parity tests green.
