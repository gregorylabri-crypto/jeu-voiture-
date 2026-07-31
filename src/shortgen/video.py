"""Turn composed frames + narration into the final MP4 with ffmpeg.

Pipeline per scene:
  frame.png (+ narration.mp3 | silence) --> sceneN.mp4  (H.264, subtle motion)

Then all scene clips are concatenated and, if a music track is available, a
looped background bed is mixed in at ``music_volume`` under the narration.
"""

from __future__ import annotations

from pathlib import Path

from . import ffmpeg


def _motion_filter(index: int, width: int, height: int, fps: int, frames: int) -> str:
    """A gentle Ken Burns move, alternating direction per scene.

    The source is pre-upscaled before ``zoompan`` so the sub-pixel stepping is
    smooth rather than jittery, then rendered back to the canvas size.
    """
    frames = max(frames, 1)
    zoom_max = 1.16
    step = (zoom_max - 1.0) / frames
    # Alternate a centred zoom-in with a slow diagonal drift.
    if index % 2 == 0:
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
    else:
        x = "(iw-iw/zoom)*(on/%d)" % frames
        y = "ih/2-(ih/zoom/2)"
    return (
        "scale=%(w)d:%(h)d,"
        "zoompan=z='min(zoom+%(step).6f\\,%(zmax).3f)':d=%(d)d:"
        "x='%(x)s':y='%(y)s':s=%(W)dx%(H)d:fps=%(fps)d,"
        "format=yuv420p"
    ) % {
        "w": int(width * 1.5),
        "h": int(height * 1.5),
        "step": step,
        "zmax": zoom_max,
        "d": frames,
        "x": x,
        "y": y,
        "W": width,
        "H": height,
        "fps": fps,
    }


def make_scene_clip(
    png: Path, audio: Path | None, duration: float, spec, out_mp4: Path,
    *, index: int = 0, motion: bool = True,
) -> Path:
    """Render one scene to an H.264 clip.

    ``index`` varies the Ken Burns direction so consecutive scenes don't move
    identically. ``audio`` is the narration; when ``None`` a silent track of
    ``duration`` seconds is synthesised so the clip still has an audio stream to
    concatenate cleanly.
    """
    fps = spec.fps
    frames = max(1, round(duration * fps))
    args: list[str] = ["-loop", "1", "-framerate", str(fps), "-t", f"{duration:.3f}",
                       "-i", str(png)]
    if audio is not None:
        args += ["-i", str(audio)]
    else:
        args += ["-f", "lavfi", "-t", f"{duration:.3f}",
                 "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]

    vf = _motion_filter(index, spec.width, spec.height, fps, frames) if motion else "format=yuv420p"
    fade = min(0.35, duration / 4)
    vf += ",fade=t=in:st=0:d=%.2f,fade=t=out:st=%.3f:d=%.2f" % (
        fade, max(0.0, duration - fade), fade)

    args += [
        "-filter_complex", f"[0:v]{vf}[v]",
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        "-t", f"{duration:.3f}",
        str(out_mp4),
    ]
    ffmpeg.run(args)
    return out_mp4


def concat_clips(clips: list[Path], out_mp4: Path) -> Path:
    """Concatenate clips (same codec params) via the concat demuxer."""
    listfile = out_mp4.parent / "_concat.txt"
    listfile.write_text(
        "".join(f"file '{c.resolve().as_posix()}'\n" for c in clips),
        encoding="utf-8",
    )
    ffmpeg.run([
        "-f", "concat", "-safe", "0", "-i", str(listfile),
        "-c", "copy", str(out_mp4),
    ])
    listfile.unlink(missing_ok=True)
    return out_mp4


def mix_music(video: Path, music: Path, volume: float, out_mp4: Path) -> Path:
    """Loop ``music`` under the narration at ``volume`` and trim to video length."""
    ffmpeg.run([
        "-i", str(video),
        "-stream_loop", "-1", "-i", str(music),
        "-filter_complex",
        # Duck the music, keep narration up front, cut to the video's length.
        f"[1:a]volume={volume:.3f}[bg];"
        f"[0:a][bg]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]",
        "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        "-shortest", str(out_mp4),
    ])
    return out_mp4
