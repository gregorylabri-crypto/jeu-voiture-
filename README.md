# shortgen — narrated vertical shorts from a JSON spec

Turn a small JSON file into a finished **1080×1920 vertical video** (TikTok /
Reels / Shorts format): images per scene, French neural narration, on-screen
captions, story-style progress bar, subtle Ken-Burns motion, and a background
music bed mixed under the voice.

The bundled example builds a French **“Crocodile vs Alligator”** explainer with
a split-screen comparison intro and four follow-up shots.

<p align="center"><em>spec.json → images → narration → captioned frames → MP4</em></p>

---

## Quick start

```bash
# 1. install deps (ships its own ffmpeg via imageio-ffmpeg — no system install)
pip install -r requirements.txt

# 2. (optional) generate a royalty-free ambient bed if you have no music yet
python scripts/make_demo_music.py            # -> assets/music/background.mp3

# 3. build the video
python generate.py config/difference-crocodile-alligator.json
# -> output/difference-crocodile-alligator.mp4
```

That’s it. With no API keys and no network, it still produces a complete video
using generated **placeholder cards** for the imagery and **estimated timing**
for the narration — so you can preview layout, captions and pacing anywhere
(including CI). Add keys / real assets to swap in real photos and real voice.

---

## The spec format

```jsonc
{
  "title": "Difference - Crocodile vs Alligator",
  "voice": "fr-FR-RemyNeural",   // any edge-tts voice
  "rate":  "+10%",                // edge-tts rate string
  "music": "assets/music/background.mp3",
  "music_volume": 0.10,           // 0.0–1.0, mixed under the narration
  "output": "output/difference-crocodile-alligator.mp4",
  "format": "split_comparison",
  "scenes": [
    {                                   // split-screen comparison shot
      "layout": "split",
      "image_left_query":  "crocodile head close up",
      "label_left":  "CROCODILE",
      "image_right_query": "alligator head close up",
      "label_right": "ALLIGATOR",
      "text": "Tu confonds sûrement le crocodile et l'alligator…"
    },
    {                                   // standard single-image shot
      "layout": "single",
      "image_query": "crocodile snout v shaped narrow",
      "text": "Regarde le museau. Le crocodile l'a fin et pointu, en forme de V."
    }
  ]
}
```

| Field          | Notes |
|----------------|-------|
| `voice`        | Any [edge-tts](https://github.com/rany2/edge-tts) voice, e.g. `fr-FR-RemyNeural`, `fr-FR-DeniseNeural`, `en-US-GuyNeural`. |
| `rate`         | edge-tts rate, e.g. `+10%`, `-5%`. Also used to scale the offline timing estimate. |
| `music`        | Path to a background track. Missing file ⇒ built without music (a warning, not an error). |
| `music_volume` | Linear gain applied to the music before mixing (clamped to 0–1). |
| `output`       | Output path, relative to the working directory. Overridable with `--output`. |
| `format`       | Informational label for the spec; the per-scene `layout` drives rendering. |
| `scenes[].layout` | `single` (one `image_query`) or `split` (`image_left_query` + `image_right_query`, optional `label_left`/`label_right`). |
| `scenes[].text`   | Narration **and** the on-screen caption. |

Each scene’s duration is the length of its narration (or an estimate when TTS
is unavailable), so audio and captions stay in sync automatically.

---

## Where the images come from

For every image query the resolver tries, in order, and uses the first hit:

1. **Local map** — an `images.json` next to the spec, e.g.
   `{"crocodile head close up": "assets/images/croc.jpg"}`, or any file dropped
   in `assets/images/<slug>.jpg` (slug = the query lowercased & hyphenated).
   Fully offline and gives you exact art.
2. **Pexels** — if `PEXELS_API_KEY` is set.
3. **Unsplash** — if `UNSPLASH_ACCESS_KEY` is set.
4. **Placeholder card** — a clean generated card with the query text, so a
   build never fails just because a photo is missing.

```bash
export PEXELS_API_KEY=xxxxx        # or UNSPLASH_ACCESS_KEY=xxxxx
python generate.py config/difference-crocodile-alligator.json
```

The run summary lists which queries fell back to placeholders.

---

## Narration — three tiers

The builder walks these in order and uses the first that works:

1. **edge-tts** (default) — Microsoft Edge neural voices, i.e. the spec’s
   `voice` (`fr-FR-RemyNeural`, `fr-FR-DeniseNeural`, …). Needs network access
   to `speech.platform.bing.com`. edge-tts talks over aiohttp, which does not
   read `HTTPS_PROXY` on its own, so the TTS module reads it from the
   environment and passes it through; TLS trust honours the standard
   `SSL_CERT_FILE` / `REQUESTS_CA_BUNDLE` variables.
2. **Piper** (offline fallback) — a small ONNX voice that runs fully locally,
   for when the edge-tts host is blocked. Fetch a French voice once:
   ```bash
   python scripts/fetch_piper_voice.py     # -> models/piper/fr_FR-siwis-medium.onnx
   ```
   It’s auto-discovered in `models/piper/` (or point `$SHORTGEN_PIPER_MODEL` at
   a specific `.onnx`). `--no-piper` disables this tier.
3. **Estimate** — no audio at all: each scene’s length is estimated from its
   word count and the `rate`, a silent track fills the clip, and the captions
   still carry the message. `--no-tts` forces this mode.

> Heads-up: in sandboxes that block outbound traffic (e.g. locked-down CI), the
> edge-tts host **and** the stock-photo APIs are unreachable. Install a Piper
> voice (GitHub-hosted mirrors, so it works where only GitHub is reachable) and
> you still get real French narration — only the imagery falls back to
> placeholders until you add a provider key or local photos.

---

## CLI

```
python generate.py <spec.json> [options]

  -o, --output PATH   Override the spec's output path
      --no-motion     Disable the Ken-Burns pan/zoom (static frames)
      --no-tts        Skip neural narration (estimated timing + silent track)
      --keep-temp     Keep the temp working dir for debugging
  -q, --quiet         Less logging
```

Exit codes: `0` ok · `1` render error · `2` invalid spec · `3` ffmpeg not found.

---

## How it works

```
config.py     load + validate the JSON spec into typed dataclasses
images.py     resolve each query (local map → Pexels → Unsplash → placeholder)
placeholder.py / fonts.py    generated fallback cards + font lookup
tts.py        edge-tts narration (proxy-aware) + offline duration estimate
compose.py    paint each 1080×1920 frame (layouts, labels, captions, scrims)
video.py      ffmpeg: per-scene clips (Ken Burns) → concat → music mix
builder.py    orchestrate the whole pipeline and report a summary
generate.py   CLI entry point
```

The renderer composites text with Pillow (not ffmpeg `drawtext`), so it works
with any ffmpeg build — including ones compiled without freetype/fontconfig.

---

## Requirements

- Python 3.9+
- `edge-tts`, `Pillow`, `requests`, `imageio-ffmpeg` (see `requirements.txt`).
  `imageio-ffmpeg` bundles a static ffmpeg; set `$SHORTGEN_FFMPEG` or put
  `ffmpeg` on `PATH` to use your own.

## Tests

```bash
python -m pytest -q            # spec validation, timing estimate, slugify
```

## Notes on assets & licensing

`assets/music/*.mp3` and `output/*.mp4` are git-ignored — background music is
usually copyrighted, and videos are regenerable build artifacts. Supply your
own licensed music, or generate the ambient bed with
`scripts/make_demo_music.py`. Provider imagery (Pexels/Unsplash) is subject to
each provider’s license.
