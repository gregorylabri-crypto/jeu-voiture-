"""shortgen - turn a JSON spec into a narrated vertical short-form video.

The package is intentionally small and dependency-light:

    config   - load and validate the JSON spec into typed dataclasses
    tts      - neural narration (edge-tts) with an offline duration estimate
    images   - resolve each scene's imagery (providers -> placeholder cards)
    compose  - paint a 1080x1920 frame for a scene with Pillow
    video    - drive ffmpeg to turn frames + audio into the final .mp4

The public entry point is :func:`shortgen.builder.build`, wired up by the
``generate.py`` CLI at the repository root.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
