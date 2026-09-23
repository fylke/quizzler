"""Unit tests for the hint source link verification script."""

from __future__ import annotations

import io
import json
import pathlib
import tempfile
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from scripts.verify_hint_sources import (
    check_url,
    collect_hint_sources,
    extract_hint_sources_from_file,
    extract_hint_sources_from_record,
    extract_urls_from_value,
    parse_args,
    verify,
)


class TestVerifyHintSources(unittest.TestCase):
    def test_extract_urls_from_value(self):
        self.assertEqual(extract_urls_from_value(None), [])
        self.assertEqual(extract_urls_from_value(""), [])
        self.assertEqual(extract_urls_from_value("Not a URL"), [])
        self.assertEqual(
            extract_urls_from_value("https://example.com/test"),
            ["https://example.com/test"],
        )
        self.assertEqual(
            extract_urls_from_value("Source: http://foo.org/a and https://bar.org/b."),
            ["http://foo.org/a", "https://bar.org/b"],
        )
        self.assertEqual(
            extract_urls_from_value(["https://a.com", None, "text", ["http://b.com"]]),
            ["https://a.com", "http://b.com"],
        )
        self.assertEqual(
            extract_urls_from_value({"src1": "https://a.com", "src2": "http://b.com"}),
            ["https://a.com", "http://b.com"],
        )

    def test_extract_hint_sources_from_record(self):
        # Record with hint_sources array
        record1 = {
            "name": "Paris",
            "hint_sources": [
                "https://example.com/paris-1",
                None,
                "https://example.com/paris-3",
                "",
                "https://example.com/paris-5",
            ],
        }
        sources1 = extract_hint_sources_from_record(record1)
        self.assertEqual(len(sources1), 3)
        self.assertEqual(sources1[0]["difficulty"], 1)
        self.assertEqual(sources1[0]["url"], "https://example.com/paris-1")
        self.assertEqual(sources1[1]["difficulty"], 3)
        self.assertEqual(sources1[1]["url"], "https://example.com/paris-3")
        self.assertEqual(sources1[2]["difficulty"], 5)
        self.assertEqual(sources1[2]["url"], "https://example.com/paris-5")

        # Record with hint1_source..hint5_source
        record2 = {
            "name": "Tokyo",
            "hint1_source": "https://example.com/tokyo-1",
            "hint4_source": "https://example.com/tokyo-4",
        }
        sources2 = extract_hint_sources_from_record(record2)
        self.assertEqual(len(sources2), 2)
        self.assertEqual(sources2[0]["url"], "https://example.com/tokyo-1")
        self.assertEqual(sources2[1]["url"], "https://example.com/tokyo-4")

        # Record with hints list of objects
        record3 = {
            "name": "Rome",
            "hints": [
                {"text": "Hint 1", "source": "https://example.com/rome-1"},
                {"text": "Hint 2"},
                {"text": "Hint 3", "hint_source": "https://example.com/rome-3"},
            ],
        }
        sources3 = extract_hint_sources_from_record(record3)
        self.assertEqual(len(sources3), 2)
        self.assertEqual(sources3[0]["url"], "https://example.com/rome-1")
        self.assertEqual(sources3[1]["url"], "https://example.com/rome-3")

    def test_extract_hint_sources_from_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = pathlib.Path(tmpdir) / "test.json"
            file_path.write_text(
                json.dumps(
                    [
                        {
                            "name": "Destination A",
                            "hint_sources": [
                                "https://example.com/a1",
                                None,
                                None,
                                None,
                                None,
                            ],
                        },
                        {
                            "name": "Destination B",
                            "hint1_source": "https://example.com/b1",
                        },
                    ]
                ),
                encoding="utf-8",
            )

            sources = extract_hint_sources_from_file(file_path)
            self.assertEqual(len(sources), 2)
            self.assertEqual(sources[0]["url"], "https://example.com/a1")
            self.assertEqual(sources[1]["url"], "https://example.com/b1")
            self.assertEqual(sources[0]["source_file"], str(file_path))

    def test_extract_hint_sources_from_dict_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = pathlib.Path(tmpdir) / "quiz_types.json"
            file_path.write_text(
                json.dumps(
                    {
                        "countries": [
                            {
                                "name": "France",
                                "hint_sources": [
                                    "https://example.com/fr",
                                    None,
                                    None,
                                    None,
                                    None,
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            sources = extract_hint_sources_from_file(file_path)
            self.assertEqual(len(sources), 1)
            self.assertEqual(sources[0]["url"], "https://example.com/fr")

    def test_extract_hint_sources_from_invalid_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = pathlib.Path(tmpdir) / "corrupt.json"
            file_path.write_text("not json content", encoding="utf-8")
            sources = extract_hint_sources_from_file(file_path)
            self.assertEqual(sources, [])

    def test_collect_hint_sources_with_custom_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dir_path = pathlib.Path(tmpdir)
            f1 = dir_path / "1.json"
            f2 = dir_path / "2.json"
            f1.write_text(
                json.dumps([{"name": "X", "hint1_source": "https://example.com/x"}]),
                encoding="utf-8",
            )
            f2.write_text(
                json.dumps([{"name": "Y", "hint1_source": "https://example.com/y"}]),
                encoding="utf-8",
            )

            sources = collect_hint_sources([dir_path])
            self.assertEqual(len(sources), 2)
            urls = {s["url"] for s in sources}
            self.assertEqual(urls, {"https://example.com/x", "https://example.com/y"})

    @patch("urllib.request.urlopen")
    def test_check_url_head_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        url, success, status, error = check_url("https://example.com/ok")
        self.assertTrue(success)
        self.assertEqual(status, 200)
        self.assertIsNone(error)

    @patch("urllib.request.urlopen")
    def test_check_url_404_head(self, mock_urlopen):
        http_error = urllib.error.HTTPError(
            url="https://example.com/not-found",
            code=404,
            msg="Not Found",
            hdrs=MagicMock(),
            fp=None,
        )
        mock_urlopen.side_effect = http_error

        url, success, status, error = check_url("https://example.com/not-found")
        self.assertFalse(success)
        self.assertEqual(status, 404)
        self.assertEqual(error, "404 Not Found")

    @patch("urllib.request.urlopen")
    def test_check_url_head_405_get_success(self, mock_urlopen):
        err_405 = urllib.error.HTTPError(
            url="https://example.com/page",
            code=405,
            msg="Method Not Allowed",
            hdrs=MagicMock(),
            fp=None,
        )
        mock_get_response = MagicMock()
        mock_get_response.status = 200
        mock_get_response.__enter__.return_value = mock_get_response

        # HEAD raises 405, GET returns 200
        mock_urlopen.side_effect = [err_405, mock_get_response]

        url, success, status, error = check_url("https://example.com/page")
        self.assertTrue(success)
        self.assertEqual(status, 200)
        self.assertIsNone(error)

    @patch("urllib.request.urlopen")
    def test_check_url_head_405_get_404(self, mock_urlopen):
        err_405 = urllib.error.HTTPError(
            url="https://example.com/page",
            code=405,
            msg="Method Not Allowed",
            hdrs=MagicMock(),
            fp=None,
        )
        err_404 = urllib.error.HTTPError(
            url="https://example.com/page",
            code=404,
            msg="Not Found",
            hdrs=MagicMock(),
            fp=None,
        )

        # HEAD raises 405, GET raises 404
        mock_urlopen.side_effect = [err_405, err_404]

        url, success, status, error = check_url("https://example.com/page")
        self.assertFalse(success)
        self.assertEqual(status, 404)
        self.assertEqual(error, "404 Not Found")

    def test_verify_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_file = pathlib.Path(tmpdir) / "empty.json"
            empty_file.write_text(json.dumps([]), encoding="utf-8")
            result = verify([empty_file])
            self.assertEqual(result, 0)

    @patch("scripts.verify_hint_sources.check_url")
    def test_verify_all_ok(self, mock_check_url):
        mock_check_url.return_value = ("https://example.com/hint", True, 200, None)
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = pathlib.Path(tmpdir) / "test.json"
            file_path.write_text(
                json.dumps([{"name": "X", "hint1_source": "https://example.com/hint"}]),
                encoding="utf-8",
            )
            result = verify([file_path])
            self.assertEqual(result, 0)

    @patch("scripts.verify_hint_sources.check_url")
    def test_verify_404_failure(self, mock_check_url):
        mock_check_url.return_value = (
            "https://example.com/missing",
            False,
            404,
            "404 Not Found",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = pathlib.Path(tmpdir) / "test.json"
            file_path.write_text(
                json.dumps(
                    [{"name": "X", "hint1_source": "https://example.com/missing"}]
                ),
                encoding="utf-8",
            )
            result = verify([file_path])
            self.assertEqual(result, 1)

    def test_parse_args(self):
        args = parse_args(["file1.json", "--workers", "5", "--timeout", "20"])
        self.assertEqual(len(args.paths), 1)
        self.assertEqual(args.workers, 5)
        self.assertEqual(args.timeout, 20)


if __name__ == "__main__":
    unittest.main()
