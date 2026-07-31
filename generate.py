#!/usr/bin/env python3
"""Generate a narrated vertical short from a JSON spec.

Usage:
    python generate.py config/difference-crocodile-alligator.json
    python generate.py <spec.json> [--output out.mp4] [--no-motion] [--no-tts]

The spec format is documented in README.md and src/shortgen/config.py.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make the src/ layout importable without installation.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from shortgen.builder import BuildOptions, build  # noqa: E402
from shortgen.config import SpecError  # noqa: E402
from shortgen.ffmpeg import FFmpegNotFound  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Turn a JSON spec into a narrated vertical short-form video.",
    )
    parser.add_argument("spec", help="Path to the JSON spec file")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="Override the output path from the spec")
    parser.add_argument("--no-motion", action="store_true",
                        help="Disable the Ken Burns pan/zoom (static frames)")
    parser.add_argument("--no-tts", action="store_true",
                        help="Skip neural narration; use estimated timing + silent track")
    parser.add_argument("--keep-temp", action="store_true",
                        help="Keep the temporary working directory (for debugging)")
    parser.add_argument("-q", "--quiet", action="store_true", help="Less logging")
    args = parser.parse_args(argv)

    opts = BuildOptions(
        output=args.output,
        motion=not args.no_motion,
        use_tts=not args.no_tts,
        keep_temp=args.keep_temp,
        verbose=not args.quiet,
    )

    try:
        result = build(args.spec, opts)
    except SpecError as exc:
        print(f"error: invalid spec: {exc}", file=sys.stderr)
        return 2
    except FFmpegNotFound as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print("\n" + "=" * 52)
    print(f"  Done: {result.output}")
    print(f"  Duration : {result.duration:.1f}s across {len(result.scene_durations)} scenes")
    print(f"  Narration: {result.narration}")
    print(f"  Music    : {result.music}")
    if result.placeholders:
        print(f"  Placeholders used for {len(result.placeholders)} image(s):")
        for q in result.placeholders:
            print(f"    - {q}")
        print("  (set PEXELS_API_KEY / UNSPLASH_ACCESS_KEY or add assets/images "
              "for real photos)")
    print("=" * 52)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
