"""Locate a TrueType font that covers Latin + French accents.

Order: ``$SHORTGEN_FONT`` / ``$SHORTGEN_FONT_BOLD`` override, then a bundled
font under ``assets/fonts``, then common system paths (DejaVu is almost always
present on Linux), then Pillow's built-in bitmap font as a last resort.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

_ROOT = Path(__file__).resolve().parent.parent.parent  # repo root

_REGULAR_CANDIDATES = [
    os.environ.get("SHORTGEN_FONT", ""),
    str(_ROOT / "assets" / "fonts" / "DejaVuSans.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/Library/Fonts/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",
]

_BOLD_CANDIDATES = [
    os.environ.get("SHORTGEN_FONT_BOLD", ""),
    str(_ROOT / "assets" / "fonts" / "DejaVuSans-Bold.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _first_existing(paths: list[str]) -> str | None:
    for p in paths:
        if p and os.path.isfile(p):
            return p
    return None


@lru_cache(maxsize=64)
def load(size: int, *, bold: bool = True) -> ImageFont.FreeTypeFont:
    path = _first_existing(_BOLD_CANDIDATES if bold else _REGULAR_CANDIDATES)
    if path is None and bold:
        path = _first_existing(_REGULAR_CANDIDATES)
    if path is None:
        # Extremely unlikely on a real system; keeps the pipeline alive.
        return ImageFont.load_default()
    return ImageFont.truetype(path, size)
