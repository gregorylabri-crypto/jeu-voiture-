"""Lightweight tests for the pure-logic parts (no ffmpeg/network needed).

Run with:  python -m pytest -q   (or)   python tests/test_basic.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest  # noqa: E402

from shortgen import tts  # noqa: E402
from shortgen.config import SpecError, load_spec  # noqa: E402
from shortgen.images import slugify  # noqa: E402

SPEC = Path(__file__).resolve().parent.parent / "config" / "difference-crocodile-alligator.json"


def test_spec_loads_and_validates():
    spec = load_spec(SPEC)
    assert spec.voice == "fr-FR-RemyNeural"
    assert spec.rate == "+10%"
    assert 0.0 <= spec.music_volume <= 1.0
    assert len(spec.scenes) == 5
    first = spec.scenes[0]
    assert first.layout == "split"
    assert first.queries == ["crocodile head close up", "alligator head close up"]
    assert first.label_left == "CROCODILE" and first.label_right == "ALLIGATOR"
    assert spec.scenes[1].layout == "single"


def test_music_volume_clamped(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(
        '{"output":"o.mp4","music_volume":5,'
        '"scenes":[{"layout":"single","image_query":"x","text":"hi"}]}',
        encoding="utf-8",
    )
    assert load_spec(p).music_volume == 1.0


@pytest.mark.parametrize("bad", [
    '{"scenes":[]}',                                             # empty scenes
    '{"scenes":[{"layout":"single","text":"hi"}]}',             # missing image_query
    '{"scenes":[{"layout":"triple","image_query":"x","text":"y"}]}',  # bad layout
    '{"scenes":[{"layout":"split","text":"y"}]}',              # split missing queries
    'not json',                                                 # invalid json
])
def test_invalid_specs_raise(tmp_path, bad):
    p = tmp_path / "bad.json"
    p.write_text(bad, encoding="utf-8")
    with pytest.raises(SpecError):
        load_spec(p)


def test_duration_estimate_scales_with_rate_and_length():
    short = "Un deux trois."
    long = "Un deux trois quatre cinq six sept huit neuf dix onze douze."
    assert tts.estimate_duration(long) > tts.estimate_duration(short)
    # A faster rate should never make the same text take longer.
    assert tts.estimate_duration(long, "+50%") <= tts.estimate_duration(long, "+0%")
    # There is always a sane floor.
    assert tts.estimate_duration("Oui.") >= 2.2


def test_slugify():
    assert slugify("Crocodile Head Close-Up!") == "crocodile-head-close-up"
    assert slugify("   ") == "image"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
