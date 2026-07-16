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
just e2e
```

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

## Home Markup Parity Guardrails

The app currently keeps two home-page markup sources during migration:

- Backend-rendered template at `/` (composed from `backend/templates/partials/*.html`)
- Static frontend fixture in `frontend/index.html` (used by frontend specs)

To prevent silent drift between those sources, backend tests include parity checks in `test_backend/test_main.py` that validate:

- Critical UI IDs exist in both rendered home markup and static fixture markup.
- Script bootstrap order stays aligned (`/static/app.js` through `/static/admin.js`).
- Top-level screen and modal section ordering remains consistent.

When changing home-page markup or script tags, update both files and keep these parity tests green.
