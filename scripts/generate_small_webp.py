"""Generate optimized _small.webp images for existing media files.

By default, scans media/countries/** for source image files that Pillow can read.
Existing generated files named *_small.webp are ignored.

Examples converted:
    5a.jpg -> 5a_small.webp
    panorama.png -> panorama_small.webp
    poster.webp -> poster_small.webp
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


SUPPORTED_SOURCE_SUFFIXES = frozenset(Image.registered_extensions())


def _is_supported_source_image(path: Path) -> bool:
    return (
        path.is_file()
        and path.suffix.lower() in SUPPORTED_SOURCE_SUFFIXES
        and not (path.suffix.lower() == ".webp" and path.stem.lower().endswith("_small"))
    )


def _target_path(source_path: Path) -> Path:
    return source_path.with_name(f"{source_path.stem}_small.webp")


def _iter_hint_source_images(root: Path) -> list[Path]:
    images: list[Path] = []
    for path in root.rglob("*"):
        if not _is_supported_source_image(path):
            continue
        images.append(path)
    return sorted(images)


def _target_size(width: int, height: int, max_width: int, max_height: int) -> tuple[int, int]:
    scale_w = max_width / width if width > max_width else 1.0
    scale_h = max_height / height if height > max_height else 1.0
    scale = min(scale_w, scale_h)
    if scale >= 1.0:
        return width, height
    return max(1, int(width * scale)), max(1, int(height * scale))


def _convert_image(source_path: Path, *, max_width: int, max_height: int, quality: int) -> Path:
    if not _is_supported_source_image(source_path):
        raise ValueError(f"Unsupported hint image filename: {source_path.name}")

    target_path = _target_path(source_path)

    with Image.open(source_path) as image:
        image = image.convert("RGB")
        width, height = image.size
        resized_width, resized_height = _target_size(width, height, max_width, max_height)
        if (resized_width, resized_height) != (width, height):
            image = image.resize((resized_width, resized_height), Image.Resampling.LANCZOS)
        image.save(target_path, format="WEBP", quality=quality, method=6)

    return target_path


def generate_small_webp(
    root: Path,
    *,
    max_width: int,
    max_height: int,
    quality: int,
    overwrite: bool,
) -> tuple[int, int]:
    converted = 0
    skipped = 0
    for source_path in _iter_hint_source_images(root):
        target_path = _target_path(source_path)
        if target_path.exists() and not overwrite:
            skipped += 1
            continue
        _convert_image(
            source_path,
            max_width=max_width,
            max_height=max_height,
            quality=quality,
        )
        converted += 1
    return converted, skipped


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate _small.webp hint images under a media root.",
    )
    parser.add_argument(
        "--root",
        required=True,
        help="Root directory to scan for source images.",
    )
    parser.add_argument(
        "--max-width",
        type=int,
        default=960,
        help="Maximum output width in pixels (default: 960).",
    )
    parser.add_argument(
        "--max-height",
        type=int,
        default=960,
        help="Maximum output height in pixels (default: 960).",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=72,
        help="WebP quality 1-100 (default: 72).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing _small.webp files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root)

    if args.max_width < 1 or args.max_height < 1:
        raise SystemExit("--max-width and --max-height must be positive integers")
    if not (1 <= args.quality <= 100):
        raise SystemExit("--quality must be between 1 and 100")
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Root directory not found: {root}")

    converted, skipped = generate_small_webp(
        root,
        max_width=args.max_width,
        max_height=args.max_height,
        quality=args.quality,
        overwrite=args.overwrite,
    )

    print(f"Converted: {converted}")
    print(f"Skipped:   {skipped}")
    print(f"Root:      {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())