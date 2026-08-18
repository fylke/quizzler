import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def read_text(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def assert_contains(text: str, needle: str, label: str, failures: list[str]) -> None:
    if needle not in text:
        failures.append(f"{label}: missing '{needle}'")


def assert_matches(text: str, pattern: str, label: str, failures: list[str]) -> None:
    if not re.search(pattern, text, re.MULTILINE):
        failures.append(f"{label}: missing pattern /{pattern}/")


def check_uses_pinned_shas(workflow_rel: str, failures: list[str]) -> None:
    text = read_text(workflow_rel)
    for idx, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped.startswith("uses:"):
            continue
        value = stripped.split("uses:", 1)[1].strip()
        if value.startswith("./"):
            continue
        if "@" not in value:
            failures.append(f"{workflow_rel}:{idx}: action reference missing @ pin")
            continue
        _, ref = value.rsplit("@", 1)
        if not re.fullmatch(r"[0-9a-f]{40}", ref):
            failures.append(f"{workflow_rel}:{idx}: action ref is not a 40-char SHA")


def main() -> int:
    failures: list[str] = []

    containerfile = read_text("Containerfile")
    # Enforce immutable python base image pins while allowing safe minor/patch upgrades.
    assert_matches(
        containerfile,
        r"^FROM\s+python:[0-9]+\.[0-9]+(?:\.[0-9]+)?-slim@sha256:[0-9a-f]{64}$",
        "Containerfile",
        failures,
    )
    assert_contains(
        containerfile,
        "COPY --from=ghcr.io/astral-sh/uv@sha256:",
        "Containerfile",
        failures,
    )
    assert_contains(containerfile, "USER 10001:10001", "Containerfile", failures)

    deploy = read_text(".github/workflows/deploy-qnap.yml")
    required_deploy_bits = [
        "--read-only",
        "--security-opt no-new-privileges:true",
        "--cap-drop ALL",
        "--user 10001:10001",
        "cosign verify",
        "cosign sign --yes",
        "image_ref:",
        "aquasecurity/trivy-action",
    ]
    for item in required_deploy_bits:
        assert_contains(deploy, item, ".github/workflows/deploy-qnap.yml", failures)

    backend = read_text("backend/__init__.py")
    for header in [
        "Content-Security-Policy",
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "CORS_ALLOWED_ORIGINS must be explicitly set in production",
    ]:
        assert_contains(backend, header, "backend/__init__.py", failures)

    ci_workflow = read_text(".github/workflows/ci.yml")
    assert_contains(
        ci_workflow,
        "gitleaks/gitleaks-action@",
        ".github/workflows/ci.yml",
        failures,
    )

    for workflow in [
        ".github/workflows/ci.yml",
        ".github/workflows/deploy-qnap.yml",
        ".github/workflows/e2e-nightly.yml",
        ".github/workflows/rollback-qnap.yml",
        ".github/workflows/rollback-self-test.yml",
    ]:
        check_uses_pinned_shas(workflow, failures)

    if failures:
        print("Hardening policy check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Hardening policy check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
