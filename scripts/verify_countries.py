#!/usr/bin/env python3
"""Verify frontend/assets/countries.txt against the official UN member states list."""

import html
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
COUNTRIES_TXT = ROOT / "frontend" / "assets" / "countries.txt"
UN_MEMBER_STATES_URL = "https://www.un.org/en/about-us/member-states"

# Mapping of official UN diplomatic / protocol names to common English names used in countries.txt
NAME_ALIASES = {
    "Bahamas (The)": "Bahamas",
    "Bolivia (Plurinational State of)": "Bolivia",
    "Brunei Darussalam": "Brunei",
    "China (the People's Republic of)": "China",
    "Côte D'Ivoire": "Cote d'Ivoire",
    "Democratic People's Republic of Korea": "North Korea",
    "Gambia (Republic of The)": "Gambia",
    "Guinea Bissau": "Guinea-Bissau",
    "Iran (Islamic Republic of)": "Iran",
    "Lao People’s Democratic Republic": "Laos",
    "Micronesia (Federated States of)": "Micronesia",
    "Naoero": "Nauru",
    "Netherlands (Kingdom of the)": "Netherlands",
    "Republic of Korea": "South Korea",
    "Republic of Moldova": "Moldova",
    "Russian Federation": "Russia",
    "Syrian Arab Republic": "Syria",
    "Türkiye": "Turkey",
    "United Kingdom of Great Britain and Northern Ireland": "United Kingdom",
    "United Republic of Tanzania": "Tanzania",
    "United States of America": "United States",
    "Venezuela, Bolivarian Republic of": "Venezuela",
    "Viet Nam": "Vietnam",
}


def fetch_un_member_states() -> list[str]:
    """Fetch official UN member states list from un.org."""
    req = urllib.request.Request(
        UN_MEMBER_STATES_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; QuizzlerCountriesVerifier/1.0)"
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        page_html = response.read().decode("utf-8")

    pattern = re.compile(
        r'<h2[^>]*>(?:\s*<a[^>]*>)?\s*([^<]+?)\s*(?:</a>)?\s*</h2>\s*<div\s+class="mb-1 text-muted">Date of Admission:'
    )
    raw_names = [html.unescape(m.strip()) for m in pattern.findall(page_html)]

    if len(raw_names) < 190:
        raise ValueError(
            f"Expected at least 190 member states from UN page, but parsed {len(raw_names)}"
        )

    return [NAME_ALIASES.get(name, name) for name in raw_names]


def load_local_countries() -> list[str]:
    """Load country names from frontend/assets/countries.txt."""
    if not COUNTRIES_TXT.exists():
        raise FileNotFoundError(f"Missing {COUNTRIES_TXT}")
    return [
        line.strip()
        for line in COUNTRIES_TXT.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def verify() -> int:
    print(
        f"Fetching authoritative UN member states list from {UN_MEMBER_STATES_URL}..."
    )
    try:
        authoritative_names = fetch_un_member_states()
    except Exception as exc:
        print(f"Error fetching UN member states list: {exc}", file=sys.stderr)
        return 1

    local_names = load_local_countries()

    authoritative_set = set(authoritative_names)
    local_set = set(local_names)

    missing_in_local = sorted(authoritative_set - local_set)
    extra_in_local = sorted(local_set - authoritative_set)

    if missing_in_local or extra_in_local:
        print("ERROR: frontend/assets/countries.txt is out of date!", file=sys.stderr)
        if missing_in_local:
            print(
                f"\nMissing in countries.txt ({len(missing_in_local)}):",
                file=sys.stderr,
            )
            for country in missing_in_local:
                print(f"  + {country}", file=sys.stderr)
        if extra_in_local:
            print(f"\nExtra in countries.txt ({len(extra_in_local)}):", file=sys.stderr)
            for country in extra_in_local:
                print(f"  - {country}", file=sys.stderr)
        return 1

    if len(local_names) != len(set(local_names)):
        duplicates = [name for name in local_names if local_names.count(name) > 1]
        print(
            f"ERROR: Duplicate entries in countries.txt: {set(duplicates)}",
            file=sys.stderr,
        )
        return 1

    print(
        f"SUCCESS: frontend/assets/countries.txt is up to date ({len(local_names)} UN member states verified)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(verify())
