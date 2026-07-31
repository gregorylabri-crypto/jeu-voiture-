#!/usr/bin/env python3
"""Download a Piper neural voice for fully offline narration.

Piper (https://github.com/rhasspy/piper) runs a small ONNX model locally, so it
needs no network at synthesis time and works where the edge-tts host is blocked.
The official voices live on Hugging Face; this script pulls the same model files
from community GitHub mirrors (with fallbacks) so it works in environments where
only GitHub is reachable.

Usage:
    python scripts/fetch_piper_voice.py                 # default French voice
    python scripts/fetch_piper_voice.py --voice fr_FR-siwis-medium
    python scripts/fetch_piper_voice.py --dest models/piper

The generator auto-discovers the model in ``models/piper`` (or set
``SHORTGEN_PIPER_MODEL`` to a specific .onnx path).
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

# voice -> list of (onnx_url, json_url) mirrors, tried in order.
VOICES = {
    "fr_FR-siwis-medium": [
        (
            "https://raw.githubusercontent.com/crocsg/speakerkeyboard/main/fr_FR-siwis-medium.onnx",
            "https://raw.githubusercontent.com/crocsg/speakerkeyboard/main/fr_FR-siwis-medium.onnx.json",
        ),
        (
            "https://raw.githubusercontent.com/arkdevuk/Webpiper/main/voices/fr_FR-siwis-medium.onnx",
            "https://raw.githubusercontent.com/arkdevuk/Webpiper/main/voices/fr_FR-siwis-medium.onnx.json",
        ),
        (
            "https://raw.githubusercontent.com/ilyasgdo/STREAM-History/main/backend/tts_models/fr_FR-siwis-medium.onnx",
            "https://raw.githubusercontent.com/ilyasgdo/STREAM-History/main/backend/tts_models/fr_FR-siwis-medium.onnx.json",
        ),
    ],
}


def _download(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "shortgen/0.1"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = resp.read()
        # Guard against tiny LFS-pointer files masquerading as the model.
        if dest.suffix == ".onnx" and len(data) < 1_000_000:
            print(f"    {url} looks like a pointer ({len(data)} bytes), skipping")
            return False
        dest.write_bytes(data)
        print(f"    saved {dest} ({len(data):,} bytes)")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"    {url} failed: {exc}")
        return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--voice", default="fr_FR-siwis-medium", choices=sorted(VOICES))
    ap.add_argument("--dest", type=Path,
                    default=Path(__file__).resolve().parent.parent / "models" / "piper")
    args = ap.parse_args(argv)

    args.dest.mkdir(parents=True, exist_ok=True)
    onnx = args.dest / f"{args.voice}.onnx"
    conf = args.dest / f"{args.voice}.onnx.json"
    if onnx.is_file() and conf.is_file() and onnx.stat().st_size > 1_000_000:
        print(f"already present: {onnx}")
        return 0

    print(f"Fetching Piper voice '{args.voice}' -> {args.dest}")
    for onnx_url, json_url in VOICES[args.voice]:
        print(f"  mirror: {onnx_url.split('/')[3]}/{onnx_url.split('/')[4]}")
        if _download(onnx_url, onnx) and _download(json_url, conf):
            print(f"Done. Model ready at {onnx}")
            return 0
    print("error: every mirror failed. Download the .onnx + .onnx.json manually "
          "from a Piper voices source and place them in "
          f"{args.dest}.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
