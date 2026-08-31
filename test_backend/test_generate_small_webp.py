"""Unit tests for the small WebP generation script."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from scripts.generate_small_webp import generate_small_webp, parse_args


class TestGenerateSmallWebp(unittest.TestCase):
    def test_generate_small_webp_processes_all_supported_image_filenames(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_paths = [
                root / "0a.jpg",
                root / "cover image.png",
                root / "hero.webp",
            ]

            Image.new("RGB", (32, 32), color="red").save(source_paths[0], format="JPEG")
            Image.new("RGB", (32, 32), color="blue").save(source_paths[1], format="PNG")
            Image.new("RGB", (32, 32), color="green").save(
                source_paths[2], format="WEBP"
            )
            Image.new("RGB", (32, 32), color="black").save(
                root / "already_small.webp",
                format="WEBP",
            )

            converted, skipped = generate_small_webp(
                root,
                max_width=32,
                max_height=32,
                quality=72,
                overwrite=False,
            )

            self.assertEqual(converted, 3)
            self.assertEqual(skipped, 0)
            self.assertTrue((root / "0a_small.webp").exists())
            self.assertTrue((root / "cover image_small.webp").exists())
            self.assertTrue((root / "hero_small.webp").exists())
            self.assertFalse((root / "already_small_small.webp").exists())

    def test_generate_small_webp_skips_sources_with_existing_small_webp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_path = root / "cover image.png"
            target_path = root / "cover image_small.webp"

            Image.new("RGB", (32, 32), color="blue").save(source_path, format="PNG")
            Image.new("RGB", (16, 16), color="green").save(target_path, format="WEBP")

            converted, skipped = generate_small_webp(
                root,
                max_width=32,
                max_height=32,
                quality=72,
                overwrite=False,
            )

            self.assertEqual(converted, 0)
            self.assertEqual(skipped, 1)

            with Image.open(target_path) as image:
                self.assertEqual(image.size, (16, 16))

    def test_parse_args_supports_named_flags_in_any_order(self):
        args = parse_args(
            [
                "--quality",
                "80",
                "--root",
                "media/countries",
                "--max-height",
                "420",
                "--max-width",
                "360",
                "--overwrite",
            ]
        )

        self.assertEqual(args.root, "media/countries")
        self.assertEqual(args.max_width, 360)
        self.assertEqual(args.max_height, 420)
        self.assertEqual(args.quality, 80)
        self.assertTrue(args.overwrite)

    def test_parse_args_supports_key_value_args_in_any_order(self):
        args = parse_args(
            [
                "quality=81",
                "height=421",
                "root=media/countries",
                "width=361",
                "overwrite=true",
            ]
        )

        self.assertEqual(args.root, "media/countries")
        self.assertEqual(args.max_width, 361)
        self.assertEqual(args.max_height, 421)
        self.assertEqual(args.quality, 81)
        self.assertTrue(args.overwrite)

    def test_parse_args_supports_positional_root_anywhere(self):
        args = parse_args(
            [
                "--quality",
                "77",
                "media/countries",
                "--max-width",
                "320",
            ]
        )

        self.assertEqual(args.root, "media/countries")
        self.assertEqual(args.max_width, 320)
        self.assertEqual(args.max_height, 960)
        self.assertEqual(args.quality, 77)
        self.assertFalse(args.overwrite)


if __name__ == "__main__":
    unittest.main()
