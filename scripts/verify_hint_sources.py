#!/usr/bin/env python3
"""Verify hint source links across quiz data files and ensure they are not 404."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
USER_AGENT = "Mozilla/5.0 (compatible; QuizzlerHintSourceVerifier/1.0)"


def _clean_url(url: str) -> str:
    """Clean trailing punctuation from extracted URL."""
    cleaned = url.rstrip(".,;:!?)]}>\"'")
    return cleaned


def extract_urls_from_value(value: object) -> list[str]:
    """Extract http/https URLs from a string or nested structure."""
    if value is None:
        return []
    if isinstance(value, str):
        raw_urls = URL_PATTERN.findall(value.strip())
        cleaned_urls = []
        for raw in raw_urls:
            cleaned = _clean_url(raw)
            if cleaned:
                cleaned_urls.append(cleaned)
        return cleaned_urls
    if isinstance(value, list):
        urls: list[str] = []
        for item in value:
            urls.extend(extract_urls_from_value(item))
        return urls
    if isinstance(value, dict):
        urls = []
        for v in value.values():
            urls.extend(extract_urls_from_value(v))
        return urls
    return []


def extract_hint_sources_from_record(record: dict) -> list[dict]:
    """Extract hint sources with metadata from a single question record."""
    sources: list[dict] = []
    question_name = record.get("name") or record.get("id") or "Unknown question"

    # Check hint_sources list
    if "hint_sources" in record and isinstance(record["hint_sources"], list):
        for idx, src in enumerate(record["hint_sources"], start=1):
            for url in extract_urls_from_value(src):
                sources.append(
                    {
                        "question": str(question_name),
                        "difficulty": idx,
                        "url": url,
                    }
                )

    # Check hint1_source ... hint5_source
    for idx in range(1, 6):
        key = f"hint{idx}_source"
        if key in record and record[key]:
            for url in extract_urls_from_value(record[key]):
                sources.append(
                    {
                        "question": str(question_name),
                        "difficulty": idx,
                        "url": url,
                    }
                )

    # Check hints list if it contains dicts with source info
    if "hints" in record and isinstance(record["hints"], list):
        for idx, hint in enumerate(record["hints"], start=1):
            if isinstance(hint, dict):
                src = hint.get("source") or hint.get("hint_source")
                for url in extract_urls_from_value(src):
                    sources.append(
                        {
                            "question": str(question_name),
                            "difficulty": idx,
                            "url": url,
                        }
                    )

    return sources


def extract_hint_sources_from_file(file_path: pathlib.Path) -> list[dict]:
    """Load JSON file and extract hint sources."""
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Warning: Failed to parse JSON from {file_path}: {exc}", file=sys.stderr)
        return []

    sources: list[dict] = []
    if isinstance(data, list):
        for record in data:
            if isinstance(record, dict):
                for item in extract_hint_sources_from_record(record):
                    item["source_file"] = str(file_path)
                    sources.append(item)
    elif isinstance(data, dict):
        for _key, val in data.items():
            if isinstance(val, list):
                for record in val:
                    if isinstance(record, dict):
                        for item in extract_hint_sources_from_record(record):
                            item["source_file"] = str(file_path)
                            sources.append(item)
            elif isinstance(val, dict):
                for item in extract_hint_sources_from_record(val):
                    item["source_file"] = str(file_path)
                    sources.append(item)
    return sources


def collect_hint_sources(paths: list[pathlib.Path] | None = None) -> list[dict]:
    """Collect all hint sources from specified paths or default data files."""
    files_to_scan: list[pathlib.Path] = []

    if paths:
        for p in paths:
            if p.is_file():
                files_to_scan.append(p)
            elif p.is_dir():
                files_to_scan.extend(sorted(p.glob("*.json")))
    else:
        seed_path_env = os.environ.get("SEED_DATA_PATH")
        if seed_path_env:
            seed_p = pathlib.Path(seed_path_env)
            if seed_p.is_file():
                files_to_scan.append(seed_p)

        if DATA_DIR.is_dir():
            files_to_scan.extend(sorted(DATA_DIR.glob("*.json")))

    unique_files: list[pathlib.Path] = []
    for f in files_to_scan:
        if f not in unique_files and f.is_file():
            unique_files.append(f)

    all_sources: list[dict] = []
    for file_path in unique_files:
        all_sources.extend(extract_hint_sources_from_file(file_path))

    return all_sources


def check_url(url: str, timeout: int = 15) -> tuple[str, bool, int | None, str | None]:
    """Check if a URL is accessible and not 404.

    Returns: (url, is_success, status_code, error_message)
    """
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
    }

    # Try HEAD request first
    head_req = urllib.request.Request(url, headers=headers, method="HEAD")
    try:
        with urllib.request.urlopen(head_req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            if status == 404:
                return (url, False, 404, "404 Not Found")
            return (url, True, status, None)
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return (url, False, 404, "404 Not Found")
        # For 405 Method Not Allowed, 403 Forbidden, 400, etc., fall back to GET
    except Exception:
        # Fall back to GET on network or method errors
        pass

    # Fall back to GET request
    get_req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(get_req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            if status == 404:
                return (url, False, 404, "404 Not Found")
            return (url, True, status, None)
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return (url, False, 404, "404 Not Found")
        return (url, False, err.code, f"HTTP {err.code}: {err.reason}")
    except Exception as exc:
        return (url, False, None, str(exc))


def verify(
    paths: list[pathlib.Path] | None = None,
    max_workers: int = 10,
    timeout: int = 15,
) -> int:
    sources = collect_hint_sources(paths)
    if not sources:
        print("No hint source links found to verify.")
        return 0

    unique_urls = sorted({s["url"] for s in sources})
    print(
        f"Found {len(sources)} hint source link reference(s) across {len(unique_urls)} unique URL(s)."
    )
    print("Checking URL accessibility (verifying not 404)...")

    results: dict[str, tuple[bool, int | None, str | None]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(check_url, url, timeout=timeout): url for url in unique_urls
        }
        for future in concurrent.futures.as_completed(future_to_url):
            url, success, status, error = future.result()
            results[url] = (success, status, error)

    failures = []
    for s in sources:
        success, status, error = results[s["url"]]
        if not success:
            failures.append(
                {
                    **s,
                    "status": status,
                    "error": error,
                }
            )

    if failures:
        print(
            f"\nERROR: Found {len(failures)} broken or unreachable hint source link(s):",
            file=sys.stderr,
        )
        for f in failures:
            loc = f.get("source_file", "unknown")
            diff = f.get("difficulty", "?")
            q = f.get("question", "?")
            status_str = (
                f"Status: {f['status']}" if f["status"] else f"Error: {f['error']}"
            )
            print(
                f"  - [{q} | Hint {diff}] {f['url']}\n    ({status_str} in {loc})",
                file=sys.stderr,
            )
        return 1

    print(
        f"SUCCESS: All {len(unique_urls)} unique hint source link(s) verified successfully (none returned 404)."
    )
    return 0


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify hint source URLs are reachable and not 404."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=pathlib.Path,
        help="Optional paths to JSON files or directories to verify.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        help="Number of concurrent worker threads for URL checks (default: 10).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="Timeout in seconds for URL requests (default: 15).",
    )
    return parser.parse_args(args)


def main() -> int:
    parsed = parse_args()
    return verify(
        paths=parsed.paths or None,
        max_workers=parsed.workers,
        timeout=parsed.timeout,
    )


if __name__ == "__main__":
    sys.exit(main())
