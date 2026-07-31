"""Narration via edge-tts, with a graceful offline fallback.

``synthesize`` tries to render real neural speech with edge-tts. edge-tts talks
to Microsoft's speech endpoint over the network, so in locked-down environments
(no egress, blocked host) it will fail; callers should fall back to
``estimate_duration`` + a silent track so the video still builds with captions.

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
    """Render ``text`` to an MP3 at ``out_path``. Raises TTSUnavailable on failure."""
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
