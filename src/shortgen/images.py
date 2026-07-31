"""Resolve each scene's image query to an actual picture.

Resolution order (first hit wins):

  1. **Local map** - an ``images.json`` next to the spec, or an ``assets/images``
     folder, mapping a query (or a slugified query) to a local file. Lets you
     pin exact art and run fully offline.
  2. **Pexels**   - if ``PEXELS_API_KEY`` is set.
  3. **Unsplash** - if ``UNSPLASH_ACCESS_KEY`` is set.
  4. **Placeholder** - a clean, generated card showing the query text, so the
     pipeline always yields a usable frame (used in CI / offline demos).

Every resolved image is normalised to an RGB JPEG in the cache directory and
its path returned. Network providers are best-effort: any failure quietly falls
through to the next source.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from PIL import Image

from .placeholder import make_placeholder

_IMG_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "image"


class ImageResolver:
    def __init__(
        self,
        spec_dir: Path,
        cache_dir: Path,
        *,
        size: tuple[int, int],
        verbose: bool = True,
    ):
        self.spec_dir = Path(spec_dir)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.size = size
        self.verbose = verbose
        self.local_map = self._load_local_map()
        # Remember which queries fell back to placeholders, for the run summary.
        self.placeholders: list[str] = []

    # ---- local map ---------------------------------------------------------
    def _load_local_map(self) -> dict[str, Path]:
        mapping: dict[str, Path] = {}
        map_file = self.spec_dir / "images.json"
        if map_file.is_file():
            try:
                raw = json.loads(map_file.read_text(encoding="utf-8"))
                for key, val in raw.items():
                    p = (self.spec_dir / val).resolve()
                    if p.is_file():
                        mapping[slugify(key)] = p
            except (json.JSONDecodeError, OSError):
                pass
        # Also index assets/images/<slug>.<ext> by filename.
        img_dir = self.spec_dir / "assets" / "images"
        if img_dir.is_dir():
            for p in img_dir.iterdir():
                if p.suffix.lower() in _IMG_EXTS:
                    mapping.setdefault(slugify(p.stem), p.resolve())
        return mapping

    # ---- public API --------------------------------------------------------
    def resolve(self, query: str, size: tuple[int, int] | None = None) -> Path:
        """Return a path to a normalised JPEG for ``query``.

        ``size`` overrides the default target dimensions (used e.g. to make a
        half-width placeholder for one side of a split scene). Real downloads
        are kept at their native resolution and cover-fitted later; only
        generated placeholders are sized to ``size``.
        """
        target = size or self.size
        cache_key = hashlib.sha1(
            f"{query}|{target[0]}x{target[1]}".encode()
        ).hexdigest()[:16]
        cached = self.cache_dir / f"{cache_key}.jpg"
        if cached.is_file():
            return cached

        raw = self._fetch_raw(query)
        if raw is not None:
            try:
                img = Image.open(raw).convert("RGB")
                img.save(cached, "JPEG", quality=90)
                return cached
            except Exception:
                pass  # corrupt download -> placeholder

        # Fallback: generate a placeholder card at the requested size.
        self.placeholders.append(query)
        card = make_placeholder(query, target)
        card.save(cached, "JPEG", quality=90)
        return cached

    # ---- source chain ------------------------------------------------------
    def _fetch_raw(self, query: str):
        slug = slugify(query)
        if slug in self.local_map:
            self._log(f"  image: '{query}' -> local {self.local_map[slug].name}")
            return self.local_map[slug]

        for fetch, key_env, name in (
            (self._fetch_pexels, "PEXELS_API_KEY", "Pexels"),
            (self._fetch_unsplash, "UNSPLASH_ACCESS_KEY", "Unsplash"),
        ):
            if os.environ.get(key_env):
                path = fetch(query)
                if path is not None:
                    self._log(f"  image: '{query}' -> {name}")
                    return path
        return None

    def _download(self, url: str, headers: dict | None = None):
        import requests

        dest = self.cache_dir / f"_dl_{hashlib.sha1(url.encode()).hexdigest()[:12]}"
        resp = requests.get(url, headers=headers or {}, timeout=20)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return dest

    def _fetch_pexels(self, query: str):
        import requests

        try:
            resp = requests.get(
                "https://api.pexels.com/v1/search",
                params={"query": query, "per_page": 1, "orientation": "portrait"},
                headers={"Authorization": os.environ["PEXELS_API_KEY"]},
                timeout=20,
            )
            resp.raise_for_status()
            photos = resp.json().get("photos", [])
            if not photos:
                return None
            src = photos[0]["src"].get("large2x") or photos[0]["src"]["original"]
            return self._download(src)
        except (requests.RequestException, KeyError, ValueError):
            return None

    def _fetch_unsplash(self, query: str):
        import requests

        try:
            resp = requests.get(
                "https://api.unsplash.com/search/photos",
                params={"query": query, "per_page": 1, "orientation": "portrait"},
                headers={"Authorization": f"Client-ID {os.environ['UNSPLASH_ACCESS_KEY']}"},
                timeout=20,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            if not results:
                return None
            return self._download(results[0]["urls"]["regular"])
        except (requests.RequestException, KeyError, ValueError):
            return None

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)
