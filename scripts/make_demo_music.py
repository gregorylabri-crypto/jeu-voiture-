#!/usr/bin/env python3
"""Synthesize a gentle, royalty-free ambient bed with ffmpeg.

This is a convenience so the generator has *something* to mix when you don't
have your own track yet. It is not a substitute for real music - swap in your
own licensed file at the path your spec's ``music`` field points to.

Usage:
    python scripts/make_demo_music.py [output.mp3] [--seconds 40]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from shortgen import ffmpeg  # noqa: E402

# A soft, wide A-minor 9 pad: detuned partials, slow tremolo, low-pass + echo.
_VOICES = [110.00, 164.81, 220.00, 261.63, 329.63]  # A2 E3 A3 C4 E4


def build_filter(seconds: float) -> tuple[list[str], str]:
    inputs: list[str] = []
    labels: list[str] = []
    for i, freq in enumerate(_VOICES):
        # Two slightly detuned oscillators per note for a warm chorus.
        inputs += ["-f", "lavfi", "-t", f"{seconds:.2f}",
                   "-i", f"sine=frequency={freq:.2f}:sample_rate=44100"]
        inputs += ["-f", "lavfi", "-t", f"{seconds:.2f}",
                   "-i", f"sine=frequency={freq * 1.004:.2f}:sample_rate=44100"]
    n = len(_VOICES) * 2
    mix_inputs = "".join(f"[{i}:a]" for i in range(n))
    chain = (
        f"{mix_inputs}amix=inputs={n}:normalize=1[m];"
        "[m]tremolo=f=0.12:d=0.35,"
        "lowpass=f=1600,"
        "aecho=0.8:0.7:600|900:0.35|0.25,"
        f"afade=t=in:st=0:d=2,afade=t=out:st={max(0.0, seconds - 3):.2f}:d=3,"
        "volume=0.7[a]"
    )
    return inputs, chain


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("output", nargs="?", default="assets/music/background.mp3")
    ap.add_argument("--seconds", type=float, default=40.0)
    args = ap.parse_args(argv)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    inputs, chain = build_filter(args.seconds)
    ffmpeg.run(inputs + [
        "-filter_complex", chain, "-map", "[a]",
        "-c:a", "libmp3lame", "-b:a", "192k", str(out),
    ])
    print(f"wrote {out} ({args.seconds:.0f}s ambient bed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
