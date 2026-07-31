"""Orchestrate the whole build: spec -> images -> narration -> frames -> mp4."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import tts, video
from .compose import render_scene
from .config import Spec, load_spec
from .ffmpeg import probe_duration
from .images import ImageResolver


@dataclass
class BuildResult:
    output: Path
    duration: float
    scene_durations: list[float] = field(default_factory=list)
    narration: str = "none"            # "neural" | "estimated"
    placeholders: list[str] = field(default_factory=list)
    music: str = "none"                # "mixed" | "missing" | "none"


@dataclass
class BuildOptions:
    output: Path | None = None
    motion: bool = True
    use_tts: bool = True          # try edge-tts neural voices
    use_piper: bool = True        # fall back to a local Piper model if present
    keep_temp: bool = False
    verbose: bool = True


def _log(opts: BuildOptions, msg: str) -> None:
    if opts.verbose:
        print(msg)


def _resolve_output(spec: Spec, spec_path: Path, opts: BuildOptions) -> Path:
    if opts.output is not None:
        return opts.output
    # Spec output is relative to the current working directory by convention.
    out = spec.output
    return out if out.is_absolute() else Path.cwd() / out


def _resolve_music(spec: Spec, spec_path: Path) -> Path | None:
    if not spec.music:
        return None
    candidates = [Path(spec.music)]
    if not candidates[0].is_absolute():
        candidates += [Path.cwd() / spec.music, spec_path.parent / spec.music]
    for c in candidates:
        if c.is_file():
            return c
    return None


def build(spec_path: str | Path, opts: BuildOptions | None = None) -> BuildResult:
    opts = opts or BuildOptions()
    spec_path = Path(spec_path)
    spec = load_spec(spec_path)

    output = _resolve_output(spec, spec_path, opts)
    output.parent.mkdir(parents=True, exist_ok=True)

    workdir = Path(tempfile.mkdtemp(prefix="shortgen_"))
    cache = workdir / "img"
    frames = workdir / "frames"
    clips = workdir / "clips"
    audio = workdir / "audio"
    for d in (cache, frames, clips, audio):
        d.mkdir(parents=True, exist_ok=True)

    resolver = ImageResolver(spec_path.parent, cache,
                             size=(spec.width, spec.height), verbose=opts.verbose)

    result = BuildResult(output=output, duration=0.0)
    used_edge = used_piper = used_estimate = False
    edge_warned = False

    piper_ready = opts.use_piper and opts.use_tts and tts.piper_available()

    _log(opts, f"Building '{spec.title}' -> {output}")
    _log(opts, f"  {len(spec.scenes)} scenes | {spec.width}x{spec.height} @ {spec.fps}fps")
    if piper_ready:
        _log(opts, f"  offline voice available: {tts.find_piper_model().name}")

    try:
        clip_paths: list[Path] = []
        for scene in spec.scenes:
            # ---- imagery -------------------------------------------------
            if scene.layout == "split":
                half = spec.width // 2
                imgs = [
                    resolver.resolve(scene.image_left_query, (half, spec.height)),
                    resolver.resolve(scene.image_right_query, (spec.width - half, spec.height)),
                ]
            else:
                imgs = [resolver.resolve(scene.image_query)]

            # ---- narration ----------------------------------------------
            scene_audio: Path | None = None
            backend = None
            duration = tts.estimate_duration(scene.text, spec.rate)
            if opts.use_tts:
                # 1) edge-tts neural voice (the spec's `voice`).
                mp3 = audio / f"scene{scene.index}.mp3"
                try:
                    tts.synthesize(scene.text, spec.voice, spec.rate, str(mp3))
                    scene_audio, backend = mp3, "edge"
                except tts.TTSUnavailable as exc:
                    if not edge_warned:
                        _log(opts, f"  edge-tts unavailable ({exc})"
                                   + ("; using offline Piper voice" if piper_ready
                                      else "; using estimated timing"))
                        edge_warned = True
                # 2) offline Piper model.
                if scene_audio is None and piper_ready:
                    wav = audio / f"scene{scene.index}.wav"
                    try:
                        tts.synthesize_piper(scene.text, str(wav), spec.rate)
                        scene_audio, backend = wav, "piper"
                    except tts.TTSUnavailable as exc:
                        _log(opts, f"  scene {scene.index}: piper failed ({exc})")

            if scene_audio is not None:
                probed = probe_duration(str(scene_audio))
                if probed:
                    duration = round(probed + 0.35, 3)  # small tail pause
                used_edge = used_edge or backend == "edge"
                used_piper = used_piper or backend == "piper"
                _log(opts, f"  scene {scene.index}: {backend} narration ({duration:.2f}s)")
            else:
                used_estimate = True

            # ---- frame + clip -------------------------------------------
            png = frames / f"scene{scene.index}.png"
            render_scene(scene, imgs, spec, png, total_scenes=len(spec.scenes))
            clip = clips / f"scene{scene.index}.mp4"
            video.make_scene_clip(png, scene_audio, duration, spec, clip,
                                  index=scene.index, motion=opts.motion)
            clip_paths.append(clip)
            result.scene_durations.append(duration)

        # ---- concat --------------------------------------------------------
        merged = workdir / "merged.mp4"
        video.concat_clips(clip_paths, merged)

        # ---- music ---------------------------------------------------------
        music_path = _resolve_music(spec, spec_path)
        if spec.music and music_path is None:
            result.music = "missing"
            _log(opts, f"  music: '{spec.music}' not found; continuing without it")
        if music_path is not None:
            video.mix_music(merged, music_path, spec.music_volume, output)
            result.music = "mixed"
            _log(opts, f"  music: mixed '{music_path.name}' at volume {spec.music_volume}")
        else:
            shutil.move(str(merged), str(output))

        result.duration = probe_duration(str(output)) or sum(result.scene_durations)
        result.placeholders = list(resolver.placeholders)
        parts = []
        if used_edge:
            parts.append("edge-tts")
        if used_piper:
            parts.append("piper (offline)")
        if used_estimate:
            parts.append("estimated")
        result.narration = " + ".join(parts) if parts else "estimated"
        return result
    finally:
        if not opts.keep_temp:
            shutil.rmtree(workdir, ignore_errors=True)
