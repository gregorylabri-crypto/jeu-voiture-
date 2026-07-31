"""Load and validate the JSON video spec into typed dataclasses.

The spec format (see ``config/difference-crocodile-alligator.json``)::

    {
      "title": "...",
      "voice": "fr-FR-RemyNeural",   # any edge-tts voice
      "rate":  "+10%",                # edge-tts rate string
      "music": "assets/music/background.mp3",
      "music_volume": 0.10,           # 0.0 - 1.0
      "output": "output/video.mp4",
      "format": "split_comparison",
      "scenes": [
        {"layout": "split",  "image_left_query": "...", "label_left": "...",
                             "image_right_query": "...", "label_right": "...",
                             "text": "..."},
        {"layout": "single", "image_query": "...", "text": "..."}
      ]
    }

Validation is deliberately strict about the things that would otherwise fail
deep inside ffmpeg (missing text, unknown layout) and lenient about the rest.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class SpecError(ValueError):
    """Raised when the JSON spec is missing or malformed."""


@dataclass
class Scene:
    """A single narrated shot."""

    layout: str                 # "single" | "split"
    text: str                   # narration + on-screen caption
    index: int                  # 0-based position in the spec

    # single layout
    image_query: str | None = None

    # split layout
    image_left_query: str | None = None
    label_left: str | None = None
    image_right_query: str | None = None
    label_right: str | None = None

    @property
    def queries(self) -> list[str]:
        """All image queries this scene needs, left-to-right."""
        if self.layout == "split":
            return [q for q in (self.image_left_query, self.image_right_query) if q]
        return [self.image_query] if self.image_query else []


@dataclass
class Spec:
    """The whole video."""

    title: str
    voice: str
    rate: str
    music: str | None
    music_volume: float
    output: Path
    fmt: str
    scenes: list[Scene] = field(default_factory=list)

    # 9:16 vertical short-form canvas.
    width: int = 1080
    height: int = 1920
    fps: int = 30


_VALID_LAYOUTS = {"single", "split"}


def _require(mapping: dict[str, Any], key: str, ctx: str) -> Any:
    if key not in mapping or mapping[key] in (None, ""):
        raise SpecError(f"{ctx}: missing required field '{key}'")
    return mapping[key]


def _parse_scene(raw: dict[str, Any], index: int) -> Scene:
    ctx = f"scenes[{index}]"
    if not isinstance(raw, dict):
        raise SpecError(f"{ctx}: expected an object, got {type(raw).__name__}")

    layout = str(raw.get("layout", "single")).strip().lower()
    if layout not in _VALID_LAYOUTS:
        raise SpecError(
            f"{ctx}: unknown layout '{layout}' (expected one of {sorted(_VALID_LAYOUTS)})"
        )

    text = str(_require(raw, "text", ctx)).strip()

    scene = Scene(layout=layout, text=text, index=index)

    if layout == "single":
        scene.image_query = str(_require(raw, "image_query", ctx)).strip()
    else:  # split
        scene.image_left_query = str(_require(raw, "image_left_query", ctx)).strip()
        scene.image_right_query = str(_require(raw, "image_right_query", ctx)).strip()
        # Labels are optional but strongly recommended for a comparison.
        scene.label_left = (raw.get("label_left") or "").strip() or None
        scene.label_right = (raw.get("label_right") or "").strip() or None

    return scene


def load_spec(path: str | Path) -> Spec:
    """Parse ``path`` (a JSON spec file) into a validated :class:`Spec`."""
    path = Path(path)
    if not path.is_file():
        raise SpecError(f"spec file not found: {path}")

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SpecError(f"{path}: invalid JSON ({exc})") from exc

    if not isinstance(raw, dict):
        raise SpecError(f"{path}: top level must be a JSON object")

    scenes_raw = _require(raw, "scenes", str(path))
    if not isinstance(scenes_raw, list) or not scenes_raw:
        raise SpecError(f"{path}: 'scenes' must be a non-empty array")

    scenes = [_parse_scene(s, i) for i, s in enumerate(scenes_raw)]

    music_volume = float(raw.get("music_volume", 0.1))
    music_volume = min(max(music_volume, 0.0), 1.0)

    # Resolve output relative to the spec file's project root (its parent's
    # parent when the spec lives in config/, otherwise the spec's directory).
    output = Path(str(_require(raw, "output", str(path))))

    return Spec(
        title=str(raw.get("title", path.stem)),
        voice=str(raw.get("voice", "fr-FR-RemyNeural")),
        rate=str(raw.get("rate", "+0%")),
        music=(str(raw["music"]) if raw.get("music") else None),
        music_volume=music_volume,
        output=output,
        fmt=str(raw.get("format", "split_comparison")),
        scenes=scenes,
    )
