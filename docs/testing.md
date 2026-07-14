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
