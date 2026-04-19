"""FFmpeg command builder for broadcast-quality video composition.

Features:
- Ken Burns with directional variety (zoom in/out, pan L/R/up/down)
- Smooth crossfade transitions between scenes
- Broadcast audio mixing (44.1kHz stereo)
- Subtitle burn-in with senior-friendly styling
- M3 VideoToolbox hardware acceleration with fallback
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from src.utils.logging_setup import get_logger

log = get_logger(__name__)

# Ken Burns direction patterns for visual variety
KEN_BURNS_PATTERNS = [
    # (x_expr, y_expr, zoom_expr) - each creates a different camera movement
    {
        "name": "zoom_in_center",
        "x": "iw/2-(iw/zoom/2)",
        "y": "ih/2-(ih/zoom/2)",
        "z": "min(zoom+{speed},{max})",
    },
    {
        "name": "zoom_out_center",
        "x": "iw/2-(iw/zoom/2)",
        "y": "ih/2-(ih/zoom/2)",
        "z": "max({max}-(zoom-1)*{speed_inv},{min})",
    },
    {
        "name": "pan_left_to_right",
        "x": "iw*0.1+(iw*0.3)*(on/{frames})",
        "y": "ih/2-(ih/zoom/2)",
        "z": "1.2",
    },
    {
        "name": "pan_right_to_left",
        "x": "iw*0.4-(iw*0.3)*(on/{frames})",
        "y": "ih/2-(ih/zoom/2)",
        "z": "1.2",
    },
    {
        "name": "slow_zoom_up",
        "x": "iw/2-(iw/zoom/2)",
        "y": "ih*0.4-(ih*0.2)*(on/{frames})",
        "z": "min(zoom+{speed},{max})",
    },
    {
        "name": "slow_zoom_down",
        "x": "iw/2-(iw/zoom/2)",
        "y": "ih*0.1+(ih*0.2)*(on/{frames})",
        "z": "min(zoom+{speed},{max})",
    },
]


def ken_burns_scene(
    image_path: Path,
    output_path: Path,
    duration_sec: float,
    fps: int = 24,
    zoom_speed: float = 0.0005,
    max_zoom: float = 1.3,
    scene_index: int = 0,
) -> None:
    """Apply Ken Burns effect with directional variety per scene.

    Each scene gets a different camera movement pattern for visual interest.
    """
    total_frames = int(duration_sec * fps)
    pattern = KEN_BURNS_PATTERNS[scene_index % len(KEN_BURNS_PATTERNS)]

    speed_inv = zoom_speed * 1.5
    min_zoom = 1.0

    x_expr = pattern["x"].format(frames=total_frames)
    y_expr = pattern["y"].format(frames=total_frames)
    z_expr = pattern["z"].format(
        speed=zoom_speed, max=max_zoom, speed_inv=speed_inv, min=min_zoom, frames=total_frames
    )

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", str(image_path),
            "-vf", (
                f"zoompan=z='{z_expr}':"
                f"x='{x_expr}':"
                f"y='{y_expr}':"
                f"d={total_frames}:"
                f"s=1920x1080:"
                f"fps={fps}"
            ),
            "-t", str(duration_sec),
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            str(output_path),
        ],
        capture_output=True,
        check=True,
    )


def concat_videos_with_transitions(
    video_paths: list[Path],
    output_path: Path,
    transition_duration: float = 1.0,
) -> None:
    """Concatenate video clips with smooth crossfade transitions.

    Uses xfade filter for real crossfade between scenes.
    Falls back to simple concat if xfade fails.
    """
    if not video_paths:
        raise ValueError("비디오 경로가 비어있습니다.")

    if len(video_paths) == 1:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(video_paths[0]), "-c", "copy", str(output_path)],
            capture_output=True,
            check=True,
        )
        return

    # Try xfade crossfade first
    result = _try_xfade_concat(video_paths, output_path, transition_duration)
    if result:
        return

    # Fallback: concat with fade-out/fade-in per clip
    log.warning("xfade_failed, using fade concat fallback")
    _fade_concat(video_paths, output_path, transition_duration)


def _try_xfade_concat(
    video_paths: list[Path], output_path: Path, transition_duration: float
) -> bool:
    """Try xfade-based concatenation. Returns True on success."""
    # Get durations of each clip
    durations: list[float] = []
    for p in video_paths:
        dur = _get_duration(p)
        if dur <= 0:
            return False
        durations.append(dur)

    # Build xfade filter chain
    inputs = []
    for p in video_paths:
        inputs.extend(["-i", str(p)])

    filter_parts = []
    current = "[0:v]"

    for i in range(1, len(video_paths)):
        next_in = f"[{i}:v]"
        out_label = f"[v{i}]" if i < len(video_paths) - 1 else "[outv]"

        # Offset = cumulative duration minus transitions so far
        offset = sum(durations[:i]) - transition_duration * i
        if offset < 0:
            offset = sum(durations[:i]) * 0.9

        filter_parts.append(
            f"{current}{next_in}xfade=transition=fade:duration={transition_duration}:offset={offset:.2f}{out_label}"
        )
        current = out_label

    filter_str = ";".join(filter_parts)

    result = subprocess.run(
        [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_str,
            "-map", "[outv]",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            str(output_path),
        ],
        capture_output=True,
    )

    return result.returncode == 0


def _fade_concat(
    video_paths: list[Path], output_path: Path, transition_duration: float
) -> None:
    """Fallback: concat clips with individual fade-in/fade-out."""
    import tempfile

    faded_clips: list[Path] = []
    for i, p in enumerate(video_paths):
        dur = _get_duration(p)
        faded = p.parent / f"_faded_{i}.mp4"

        fade_filter = f"fade=t=in:st=0:d={transition_duration}"
        if dur > transition_duration * 2:
            fade_filter += f",fade=t=out:st={dur - transition_duration}:d={transition_duration}"

        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(p),
                "-vf", fade_filter,
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-pix_fmt", "yuv420p",
                str(faded),
            ],
            capture_output=True,
            check=True,
        )
        faded_clips.append(faded)

    # Simple concat
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for p in faded_clips:
            f.write(f"file '{p.resolve()}'\n")
        list_file = f.name

    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", list_file,
                "-c", "copy",
                str(output_path),
            ],
            capture_output=True,
            check=True,
        )
    finally:
        Path(list_file).unlink(missing_ok=True)
        for f in faded_clips:
            f.unlink(missing_ok=True)


def mix_audio(
    narration_path: Path,
    bgm_path: Path,
    output_path: Path,
    narration_db: float = -3,
    bgm_db: float = -15,
    fade_out_sec: float = 3.0,
) -> None:
    """Mix narration and BGM with ducking and fade.

    Falls back to narration-only if mixing fails.
    """
    narr_duration = _get_duration(narration_path) or 300.0
    # BGM runs for the full duration + extra 5 seconds for fade out after narration ends
    total_duration = narr_duration + 5.0
    fade_start = max(0, total_duration - fade_out_sec)

    mix_result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(narration_path),
            "-stream_loop", "-1",
            "-i", str(bgm_path),
            "-filter_complex", (
                f"[0:a]aresample=44100,volume={narration_db}dB[narr];"
                f"[1:a]aresample=44100,volume={bgm_db}dB,"
                f"afade=t=in:st=0:d=2,"
                f"afade=t=out:st={fade_start}:d={fade_out_sec}[bgm];"
                f"[narr][bgm]amix=inputs=2:duration=longest:dropout_transition=3[out]"
            ),
            "-map", "[out]",
            "-t", str(total_duration),
            "-c:a", "libmp3lame",
            "-q:a", "2",
            "-ar", "44100",
            "-ac", "2",
            str(output_path),
        ],
        capture_output=True,
    )

    if mix_result.returncode != 0:
        log.warning("audio_mix_failed, using narration only")
        import shutil
        shutil.copy2(str(narration_path), str(output_path))


def burn_subtitles(
    video_path: Path,
    subtitle_path: Path,
    output_path: Path,
    font_name: str = "NanumSquareRoundEB",
    font_size: int = 52,
    font_dir: str | None = None,
) -> None:
    """Burn SRT subtitles with senior-friendly styling.

    Uses fontsdir to point ffmpeg at the project's font directory so that
    custom Korean fonts are found reliably across platforms.
    """
    # Modern Korean YouTube subtitle style: clean background box
    style = (
        f"FontName={font_name},"
        f"FontSize={font_size},"
        f"PrimaryColour=&H00FFFFFF,"       # White text
        f"BackColour=&H80000000,"           # Semi-transparent black background
        f"BorderStyle=4,"                   # Background box style
        f"Outline=0,"                       # No outline
        f"Shadow=0,"                        # No shadow
        f"MarginV=45,"                      # Bottom margin
        f"MarginL=80,"
        f"MarginR=80,"
        f"Alignment=2,"                     # Bottom center
        f"Bold=1"
    )

    # Copy subtitle to a simple path to avoid escaping issues
    import shutil
    import tempfile

    tmp_dir = Path(tempfile.mkdtemp())
    tmp_srt = tmp_dir / "subs.srt"
    shutil.copy2(str(subtitle_path.resolve()), str(tmp_srt))

    if font_dir is None:
        font_dir = str(Path(__file__).resolve().parent.parent.parent / "assets" / "fonts")

    # Copy fonts to tmp dir too for simplicity
    tmp_fonts = tmp_dir / "fonts"
    tmp_fonts.mkdir(exist_ok=True)
    fonts_src = Path(font_dir)
    if fonts_src.exists():
        for f in fonts_src.glob("*.ttf"):
            shutil.copy2(str(f), str(tmp_fonts / f.name))

    # Use simple relative-style path from tmp dir
    srt_escaped = str(tmp_srt).replace(":", "\\\\:")
    fonts_escaped = str(tmp_fonts).replace(":", "\\\\:")
    vf_filter = f"subtitles={srt_escaped}:fontsdir={fonts_escaped}:force_style='{style}'"

    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", vf_filter,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "copy",
            str(output_path),
        ],
        capture_output=True,
    )

    if result.returncode != 0:
        log.warning(
            "subtitle_burn_failed",
            stderr=result.stderr.decode(errors="replace")[-500:],
        )
        # Retry with just subtitles, no fontsdir
        vf_simple = f"subtitles={srt_escaped}:force_style='{style}'"
        result2 = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-vf", vf_simple,
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-c:a", "copy",
                str(output_path),
            ],
            capture_output=True,
        )
        if result2.returncode != 0:
            log.warning("subtitle_burn_retry_failed, skipping subtitles")
            shutil.copy2(str(video_path), str(output_path))

    # Cleanup tmp
    shutil.rmtree(str(tmp_dir), ignore_errors=True)


def compose_final_video(
    video_path: Path,
    audio_path: Path,
    output_path: Path,
    use_hw_accel: bool = True,
) -> None:
    """Combine video + audio. M3 VideoToolbox with libx264 fallback."""
    codec = "h264_videotoolbox" if use_hw_accel else "libx264"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-map", "0:v",
        "-map", "1:a",
        "-c:v", codec,
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "44100",
        "-ac", "2",
        "-shortest",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True)

    if result.returncode != 0 and use_hw_accel:
        log.warning("hw_accel_failed, falling back to libx264")
        for i, arg in enumerate(cmd):
            if arg == "h264_videotoolbox":
                cmd[i] = "libx264"
                break
        subprocess.run(cmd, capture_output=True, check=True)
    elif result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)


def _get_duration(file_path: Path) -> float:
    """Get media file duration in seconds."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(file_path),
        ],
        capture_output=True,
        text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0
