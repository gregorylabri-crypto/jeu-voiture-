"""Generate a clean placeholder card when no real photo is available.

Produces a deterministic vertical gradient (colour derived from the query so
each subject looks distinct), a soft vignette, a camera glyph, the query text,
and a small "placeholder" ribbon. Good enough to preview layout, timing and
captions offline; swap in real imagery via a provider key or a local map.
"""

from __future__ import annotations

import colorsys
import hashlib

from PIL import Image, ImageDraw

from . import fonts


def _hue(query: str) -> float:
    h = hashlib.sha1(query.encode("utf-8")).digest()
    return h[0] / 255.0


def _gradient(size: tuple[int, int], top: tuple[int, int, int],
              bottom: tuple[int, int, int]) -> Image.Image:
    w, h = size
    base = Image.new("RGB", (1, h))
    px = base.load()
    for y in range(h):
        t = y / max(1, h - 1)
        px[0, y] = tuple(int(top[c] + (bottom[c] - top[c]) * t) for c in range(3))
    return base.resize((w, h))


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def make_placeholder(query: str, size: tuple[int, int]) -> Image.Image:
    w, h = size
    hue = _hue(query)
    r1, g1, b1 = colorsys.hsv_to_rgb(hue, 0.55, 0.42)
    r2, g2, b2 = colorsys.hsv_to_rgb((hue + 0.05) % 1.0, 0.65, 0.16)
    top = (int(r1 * 255), int(g1 * 255), int(b1 * 255))
    bottom = (int(r2 * 255), int(g2 * 255), int(b2 * 255))

    img = _gradient(size, top, bottom)
    draw = ImageDraw.Draw(img, "RGBA")

    # Soft vignette so text pops.
    draw.ellipse(
        [-w * 0.3, -h * 0.15, w * 1.3, h * 1.15],
        fill=None,
        outline=(0, 0, 0, 0),
    )

    # Camera glyph (simple, drawn — no external assets).
    cx, cy = w // 2, int(h * 0.40)
    bw, bh = int(w * 0.26), int(w * 0.19)
    body = [cx - bw // 2, cy - bh // 2, cx + bw // 2, cy + bh // 2]
    draw.rounded_rectangle(body, radius=int(bw * 0.10), fill=(255, 255, 255, 40))
    draw.rectangle(
        [cx - int(bw * 0.16), body[1] - int(bh * 0.16),
         cx + int(bw * 0.16), body[1] + int(bh * 0.04)],
        fill=(255, 255, 255, 40),
    )
    lens_r = int(bw * 0.20)
    draw.ellipse([cx - lens_r, cy - lens_r, cx + lens_r, cy + lens_r],
                 outline=(255, 255, 255, 90), width=max(3, w // 260))

    # Query text.
    font = fonts.load(max(30, w // 22), bold=True)
    lines = _wrap(draw, query.upper(), font, int(w * 0.80))
    line_h = int(font.size * 1.25)
    total = line_h * len(lines)
    y = int(h * 0.60)
    for line in lines:
        tw = draw.textlength(line, font=font)
        x = (w - tw) / 2
        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 120))
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 235))
        y += line_h

    # "placeholder" ribbon.
    small = fonts.load(max(18, w // 46), bold=True)
    label = "IMAGE PLACEHOLDER"
    lw = draw.textlength(label, font=small)
    pad = int(w * 0.02)
    ribbon = [int(w / 2 - lw / 2 - pad), y + int(line_h * 0.4),
              int(w / 2 + lw / 2 + pad), y + int(line_h * 0.4) + small.size + 2 * pad]
    draw.rounded_rectangle(ribbon, radius=int(small.size * 0.4), fill=(0, 0, 0, 90))
    draw.text((w / 2 - lw / 2, ribbon[1] + pad), label, font=small,
              fill=(255, 255, 255, 200))

    return img
