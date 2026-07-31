"""Paint a single 1080x1920 scene frame with Pillow.

Handles the two layouts in the spec:

  * ``single`` - one image cover-fitted to the whole canvas.
  * ``split``  - two images side by side with a divider and label banners
                 (the "split_comparison" look).

Every scene gets a top/bottom scrim for legibility and a rounded caption box
carrying the narration text. The result is saved as a PNG that ffmpeg later
turns into a moving clip.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from . import fonts
from .config import Scene, Spec

# Palette
_ACCENT = (255, 209, 77)          # warm yellow accent (labels / progress)
_CAPTION_BG = (12, 14, 20, 205)   # translucent dark caption panel
_LABEL_BG = (18, 20, 26, 225)


def _cover(img: Image.Image, box: tuple[int, int]) -> Image.Image:
    """Scale + center-crop ``img`` to exactly fill ``box`` (like CSS cover)."""
    bw, bh = box
    iw, ih = img.size
    scale = max(bw / iw, bh / ih)
    nw, nh = max(1, round(iw * scale)), max(1, round(ih * scale))
    img = img.resize((nw, nh), Image.LANCZOS)
    left = (nw - bw) // 2
    top = (nh - bh) // 2
    return img.crop((left, top, left + bw, top + bh))


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _scrim(size, top_alpha, bottom_alpha):
    """A vertical black gradient scrim (transparent middle)."""
    w, h = size
    grad = Image.new("L", (1, h))
    px = grad.load()
    for y in range(h):
        t = y / max(1, h - 1)
        # Strong at very top and bottom, clear through the middle band.
        a_top = top_alpha * max(0.0, 1 - t / 0.28)
        a_bot = bottom_alpha * max(0.0, (t - 0.55) / 0.45)
        px[0, y] = int(min(255, a_top + a_bot))
    alpha = grad.resize((w, h))
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    layer.putalpha(alpha)
    return layer


def _draw_label(base: Image.Image, cx: int, cy: int, text: str):
    draw = ImageDraw.Draw(base, "RGBA")
    font = fonts.load(max(30, base.width // 24), bold=True)
    tw = draw.textlength(text, font=font)
    th = font.size
    pad_x, pad_y = int(base.width * 0.028), int(base.width * 0.016)
    box = [cx - tw / 2 - pad_x, cy - th / 2 - pad_y,
           cx + tw / 2 + pad_x, cy + th / 2 + pad_y]
    draw.rounded_rectangle(box, radius=int(th * 0.35), fill=_LABEL_BG)
    draw.rounded_rectangle(box, radius=int(th * 0.35), outline=_ACCENT,
                           width=max(2, base.width // 360))
    draw.text((cx - tw / 2, cy - th / 2 - 2), text, font=font, fill=(255, 255, 255, 255))


def _draw_caption(base: Image.Image, text: str):
    draw = ImageDraw.Draw(base, "RGBA")
    w, h = base.size
    font = fonts.load(max(34, w // 20), bold=True)
    max_w = int(w * 0.86)
    lines = _wrap(draw, text, font, max_w)
    line_h = int(font.size * 1.22)
    block_h = line_h * len(lines)

    pad = int(w * 0.045)
    # Sit above the bottom safe-area (room for platform UI on Shorts/Reels).
    bottom = int(h * 0.88)
    top = bottom - block_h - pad
    box = [int(w * 0.05), top - pad, int(w * 0.95), bottom + pad]

    panel = Image.new("RGBA", base.size, (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(panel)
    pdraw.rounded_rectangle(box, radius=int(w * 0.045), fill=_CAPTION_BG)
    base.alpha_composite(panel)

    y = top
    for line in lines:
        tw = draw.textlength(line, font=font)
        x = (w - tw) / 2
        draw.text((x + 2, y + 3), line, font=font, fill=(0, 0, 0, 160))
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_h


def _draw_progress(base: Image.Image, index: int, total: int):
    """Small segmented progress bar along the very top (story-style)."""
    draw = ImageDraw.Draw(base, "RGBA")
    w = base.width
    gap = int(w * 0.012)
    margin = int(w * 0.04)
    seg_w = (w - 2 * margin - gap * (total - 1)) / total
    y = int(base.height * 0.022)
    hgt = max(4, w // 220)
    for i in range(total):
        x0 = margin + i * (seg_w + gap)
        color = _ACCENT + (255,) if i <= index else (255, 255, 255, 90)
        draw.rounded_rectangle([x0, y, x0 + seg_w, y + hgt], radius=hgt // 2, fill=color)


def render_scene(
    scene: Scene,
    image_paths: list[Path],
    spec: Spec,
    out_png: Path,
    *,
    total_scenes: int,
) -> Path:
    W, H = spec.width, spec.height
    canvas = Image.new("RGBA", (W, H), (8, 9, 12, 255))

    if scene.layout == "split" and len(image_paths) >= 2:
        half = W // 2
        left = _cover(Image.open(image_paths[0]).convert("RGB"), (half, H))
        right = _cover(Image.open(image_paths[1]).convert("RGB"), (W - half, H))
        canvas.paste(left, (0, 0))
        canvas.paste(right, (half, 0))
        # Divider.
        div = ImageDraw.Draw(canvas, "RGBA")
        div_w = max(4, W // 180)
        div.rectangle([half - div_w // 2, 0, half + div_w // 2, H], fill=(255, 255, 255, 235))
    else:
        img = _cover(Image.open(image_paths[0]).convert("RGB"), (W, H))
        canvas.paste(img, (0, 0))

    # Legibility scrims.
    canvas.alpha_composite(_scrim((W, H), top_alpha=150, bottom_alpha=225))

    # Split labels.
    if scene.layout == "split" and len(image_paths) >= 2:
        band_y = int(H * 0.12)
        if scene.label_left:
            _draw_label(canvas, W // 4, band_y, scene.label_left)
        if scene.label_right:
            _draw_label(canvas, 3 * W // 4, band_y, scene.label_right)

    _draw_progress(canvas, scene.index, total_scenes)
    _draw_caption(canvas, scene.text)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_png, "PNG")
    return out_png
