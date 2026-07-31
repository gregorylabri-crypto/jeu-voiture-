"""Locate an ffmpeg binary and run it.

Order of preference:
  1. ``$SHORTGEN_FFMPEG`` if set (explicit override).
  2. The static binary shipped with ``imageio-ffmpeg`` (no system install).
  3. ``ffmpeg`` on ``$PATH``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache


class FFmpegNotFound(RuntimeError):
    pass


@lru_cache(maxsize=1)
def ffmpeg_exe() -> str:
    override = os.environ.get("SHORTGEN_FFMPEG")
    if override and os.path.exists(override):
        return override

    try:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:  # pragma: no cover - optional dependency
        pass

    found = shutil.which("ffmpeg")
    if found:
        return found

    raise FFmpegNotFound(
        "ffmpeg not found. Install 'imageio-ffmpeg' (pip install imageio-ffmpeg), "
        "put ffmpeg on PATH, or set $SHORTGEN_FFMPEG."
    )


def run(args: list[str], *, quiet: bool = True) -> None:
    """Run ffmpeg with ``args`` (excluding the binary itself)."""
    cmd = [ffmpeg_exe(), "-y"]
    if quiet:
        cmd += ["-loglevel", "error", "-nostats"]
    cmd += args
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            "ffmpeg failed (exit %d)\n  cmd: %s\n  stderr:\n%s"
            % (proc.returncode, " ".join(cmd), proc.stderr.strip())
        )


def probe_duration(path: str) -> float | None:
    """Return the duration of a media file in seconds, or ``None`` if unknown.

    Uses ffmpeg itself (no separate ffprobe) so we only depend on one binary.
    """
    proc = subprocess.run(
        [ffmpeg_exe(), "-i", path, "-hide_banner"],
        capture_output=True,
        text=True,
    )
    # ffmpeg prints "Duration: HH:MM:SS.xx" to stderr.
    for line in proc.stderr.splitlines():
        line = line.strip()
        if line.startswith("Duration:"):
            token = line.split("Duration:", 1)[1].split(",", 1)[0].strip()
            if token.lower().startswith("n/a"):
                return None
            try:
                h, m, s = token.split(":")
                return int(h) * 3600 + int(m) * 60 + float(s)
            except ValueError:
                return None
    return None
