"""Narration with two neural backends and a graceful offline fallback.

Order of preference (the builder walks it):

  1. **edge-tts**  - Microsoft Edge neural voices (the spec's ``voice``). Needs
     network access to ``speech.platform.bing.com``.
  2. **Piper**     - a small ONNX model that runs fully locally, for when the
     edge-tts host is unreachable (offline / firewalled / egress policy). Fetch
     a model with ``scripts/fetch_piper_voice.py``; auto-discovered under
     ``models/piper`` or via ``$SHORTGEN_PIPER_MODEL``.
  3. **estimate**  - no audio at all; the builder uses ``estimate_duration`` and
     a silent track so captions still play in sync.

Proxy handling: edge-tts uses aiohttp, which does *not* pick up ``HTTPS_PROXY``
automatically, so we read it from the environment and pass it through
explicitly. TLS trust (custom CA bundles) is honoured via the standard
``SSL_CERT_FILE`` / ``REQUESTS_CA_BUNDLE`` variables that aiohttp's default
context already respects.
"""

from __future__ import annotations

import asyncio
import os
import re
from functools import lru_cache
from pathlib import Path


class TTSUnavailable(RuntimeError):
    """Raised when neural narration could not be produced."""


def _proxy() -> str | None:
    for var in ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        val = os.environ.get(var)
        if val:
            return val
    return None


def _parse_rate(rate: str) -> float:
    """Turn an edge-tts rate string like ``+10%`` into a speed multiplier."""
    m = re.fullmatch(r"\s*([+-]?\d+(?:\.\d+)?)\s*%\s*", rate or "")
    if not m:
        return 1.0
    return max(0.5, 1.0 + float(m.group(1)) / 100.0)


def estimate_duration(text: str, rate: str = "+0%", *, min_seconds: float = 2.2) -> float:
    """Estimate narration length without synthesizing audio.

    Based on a French neural-TTS baseline of ~170 words/minute, scaled by the
    rate multiplier, with a little breathing room for the final pause. Used both
    as a fallback when TTS is unavailable and as a sanity clamp.
    """
    words = max(1, len(re.findall(r"\S+", text)))
    baseline_wps = 170.0 / 60.0
    wps = baseline_wps * _parse_rate(rate)
    seconds = words / wps
    seconds += 0.6  # trailing pause
    return round(max(seconds, min_seconds), 3)


async def _synthesize_async(text: str, voice: str, rate: str, out_path: str) -> None:
    import edge_tts  # imported lazily so the package loads without network deps

    communicate = edge_tts.Communicate(text, voice, rate=rate, proxy=_proxy())
    got_audio = False
    with open(out_path, "wb") as fh:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])
                got_audio = True
    if not got_audio:
        raise TTSUnavailable("edge-tts returned no audio data")


def synthesize(text: str, voice: str, rate: str, out_path: str) -> None:
    """Render ``text`` to an MP3 at ``out_path`` via edge-tts.

    Raises :class:`TTSUnavailable` on any failure (network/DNS/TLS/policy).
    """
    try:
        asyncio.run(_synthesize_async(text, voice, rate, out_path))
    except TTSUnavailable:
        raise
    except Exception as exc:  # network/DNS/TLS/policy errors -> unavailable
        # Clean up any partial file so callers don't mux a truncated clip.
        try:
            if os.path.exists(out_path):
                os.remove(out_path)
        except OSError:
            pass
        raise TTSUnavailable(f"edge-tts failed: {exc}") from exc


# --------------------------------------------------------------------------- #
# Piper (offline) backend
# --------------------------------------------------------------------------- #

_PIPER_ROOT = Path(__file__).resolve().parent.parent.parent  # repo root


def find_piper_model() -> Path | None:
    """Locate a Piper ``.onnx`` model (with a sibling ``.onnx.json``).

    Checks ``$SHORTGEN_PIPER_MODEL`` then ``<repo>/models/piper``.
    """
    override = os.environ.get("SHORTGEN_PIPER_MODEL")
    if override:
        p = Path(override)
        if p.is_file() and p.with_suffix(".onnx.json").is_file():
            return p
    search = _PIPER_ROOT / "models" / "piper"
    if search.is_dir():
        for onnx in sorted(search.glob("*.onnx")):
            if onnx.with_suffix(".onnx.json").is_file():
                return onnx
    return None


@lru_cache(maxsize=4)
def _load_piper(model_path: str):
    from piper import PiperVoice  # imported lazily; optional dependency

    return PiperVoice.load(model_path, model_path + ".json")


def piper_available() -> bool:
    if find_piper_model() is None:
        return False
    try:
        import piper  # noqa: F401
    except Exception:
        return False
    return True


def synthesize_piper(text: str, out_path: str, rate: str = "+0%",
                     model_path: str | None = None) -> None:
    """Render ``text`` to a WAV at ``out_path`` using a local Piper model."""
    model = model_path or (str(find_piper_model()) if find_piper_model() else None)
    if model is None:
        raise TTSUnavailable("no Piper model found (run scripts/fetch_piper_voice.py)")
    try:
        import wave

        from piper import SynthesisConfig

        voice = _load_piper(model)
        # length_scale is inverse speed: a faster rate -> shorter samples.
        syn = SynthesisConfig(length_scale=1.0 / _parse_rate(rate))
        with wave.open(out_path, "wb") as wav:
            voice.synthesize_wav(text, wav, syn_config=syn)
    except TTSUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001
        try:
            if os.path.exists(out_path):
                os.remove(out_path)
        except OSError:
            pass
        raise TTSUnavailable(f"piper failed: {exc}") from exc
