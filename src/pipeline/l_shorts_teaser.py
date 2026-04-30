"""Stage L: Auto-cut multiple Shorts teasers from the main video.

For each short clip:
1. Source = `video/composed.mp4` (자막 없는 버전) if present, else final.mp4
2. Trim to the time window + crop to 9:16 + scale to 1080x1920
3. Slice SRT to the window, shift timestamps to start at 0
4. Burn subtitles at shorts-specific font size (half of main video)
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import yaml

from src.engines.llm_client import PROJECT_ROOT
from src.models import ProjectManifest, Scene, Script
from src.pipeline.base_stage import BaseStage


SRT_TIME_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})"
)


def _srt_to_seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def _seconds_to_srt(sec: float) -> str:
    if sec < 0:
        sec = 0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    if ms == 1000:
        s += 1
        ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _slice_and_shift_srt(src_srt: Path, start_sec: float, duration: float) -> str:
    """Return an SRT string containing only cues within [start, start+duration],
    with timestamps shifted so the window begins at 00:00:00,000."""
    end_sec = start_sec + duration
    content = src_srt.read_text(encoding="utf-8")
    blocks = re.split(r"\n\s*\n", content.strip())

    out_blocks: list[str] = []
    idx = 1

    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 2:
            continue

        time_line_idx = 0
        if not SRT_TIME_RE.search(lines[0]):
            time_line_idx = 1
            if len(lines) < 3 or not SRT_TIME_RE.search(lines[time_line_idx]):
                continue

        match = SRT_TIME_RE.search(lines[time_line_idx])
        if not match:
            continue

        start = _srt_to_seconds(*match.group(1, 2, 3, 4))
        end = _srt_to_seconds(*match.group(5, 6, 7, 8))

        # Overlap with window?
        if end <= start_sec or start >= end_sec:
            continue

        new_start = max(0.0, start - start_sec)
        new_end = min(duration, end - start_sec)
        if new_end <= new_start:
            continue

        text_lines = lines[time_line_idx + 1:]
        out_blocks.append(
            f"{idx}\n{_seconds_to_srt(new_start)} --> {_seconds_to_srt(new_end)}\n"
            + "\n".join(text_lines)
        )
        idx += 1

    return "\n\n".join(out_blocks) + ("\n" if out_blocks else "")


class ShortsTeaserStage(BaseStage):
    name = "l_shorts_teaser"
    dependencies = ["h_video_compose"]

    def execute(self, project_dir: Path, manifest: ProjectManifest) -> float:
        script = Script.model_validate_json(
            (project_dir / "script.json").read_text(encoding="utf-8")
        )

        with open(PROJECT_ROOT / "config" / "settings.yaml", encoding="utf-8") as f:
            settings = yaml.safe_load(f)
        shorts_sub_cfg = settings.get("subtitle_shorts") or settings.get("subtitle", {})

        # Prefer the pre-subtitle version so we can burn smaller subs after crop
        composed_video = project_dir / "video" / "composed.mp4"
        final_video = project_dir / "video" / "final.mp4"
        source_video = composed_video if composed_video.exists() else final_video
        source_has_subs = source_video is final_video

        if not source_video.exists():
            self.log.warning("source_video_missing")
            return 0.0

        source_duration = self._get_duration(source_video)
        if source_duration <= 0:
            self.log.warning("cannot_detect_video_duration")
            return 0.0

        srt_path = project_dir / "subtitles" / "raw.srt"

        clips = self._plan_shorts_clips(script, source_duration)
        created: list[dict] = []

        for i, clip in enumerate(clips):
            output_path = project_dir / "video" / f"shorts_{i + 1:02d}.mp4"

            try:
                self._extract_short(
                    source=source_video,
                    source_has_subs=source_has_subs,
                    srt_path=srt_path if srt_path.exists() else None,
                    output=output_path,
                    project_dir=project_dir,
                    index=i + 1,
                    start_sec=clip["start"],
                    duration=clip["duration"],
                    source_duration=source_duration,
                    shorts_sub_cfg=shorts_sub_cfg,
                )

                out_dur = self._get_duration(output_path)
                if out_dur > 1:
                    created.append({
                        "file": output_path.name,
                        "start": clip["start"],
                        "duration": round(out_dur, 1),
                        "label": clip["label"],
                    })
                    self.log.info(
                        "short_created",
                        index=i + 1,
                        label=clip["label"],
                        duration=round(out_dur, 1),
                    )
                else:
                    output_path.unlink(missing_ok=True)
                    self.log.warning("short_too_short", index=i + 1)

            except subprocess.CalledProcessError as e:
                self.log.warning("short_failed", index=i + 1, error=str(e))

        if created:
            main_teaser = project_dir / "video" / "shorts_teaser.mp4"
            first_short = project_dir / "video" / created[0]["file"]
            if first_short.exists():
                shutil.copy2(first_short, main_teaser)

        (project_dir / "video" / "shorts_manifest.json").write_text(
            json.dumps(created, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        self.log.info("shorts_complete", count=len(created), source_has_subs=source_has_subs)
        return 0.0

    def _plan_shorts_clips(self, script: Script, source_duration: float) -> list[dict]:
        clips: list[dict] = []
        current_time = 0.0
        scenes_with_time: list[tuple[Scene, float]] = []

        for scene in script.scenes:
            if scene.has_silence_before:
                current_time += scene.silence_duration_sec
            scenes_with_time.append((scene, current_time))
            current_time += scene.duration_sec

        clips.append({"start": 0, "duration": min(20, source_duration), "label": "hook"})

        for scene, start in scenes_with_time:
            if scene.phase == "reveal":
                clips.append({
                    "start": max(0, start - 3),
                    "duration": min(25, scene.duration_sec + 3),
                    "label": "reveal",
                })
                break

        for scene, start in scenes_with_time:
            if scene.phase == "climax":
                clips.append({
                    "start": max(0, start - 2),
                    "duration": min(30, scene.duration_sec + 2),
                    "label": "climax",
                })
                break

        for scene, start in scenes_with_time:
            if scene.phase == "healing":
                clips.append({
                    "start": start,
                    "duration": min(20, scene.duration_sec),
                    "label": "healing",
                })
                break

        for scene, start in scenes_with_time:
            if scene.phase == "layering":
                clips.append({
                    "start": start,
                    "duration": min(20, scene.duration_sec),
                    "label": "memory",
                })
                break

        valid = []
        for clip in clips:
            if clip["start"] + clip["duration"] <= source_duration and clip["duration"] >= 8:
                valid.append(clip)
        return valid[:5]

    def _extract_short(
        self,
        source: Path,
        source_has_subs: bool,
        srt_path: Path | None,
        output: Path,
        project_dir: Path,
        index: int,
        start_sec: float,
        duration: float,
        source_duration: float,
        shorts_sub_cfg: dict,
    ) -> None:
        if start_sec + duration > source_duration:
            duration = max(5, source_duration - start_sec)

        # 1단계: 9:16 크롭·스케일 (자막 없는 raw 클립)
        raw_short = project_dir / "video" / f"_shorts_raw_{index:02d}.mp4"
        vf_crop = "crop=ih*9/16:ih,scale=1080:1920"

        subprocess.run(
            [
                "ffmpeg", "-y",
                "-ss", str(start_sec),
                "-i", source.as_posix(),
                "-t", str(duration),
                "-vf", vf_crop,
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "128k",
                "-ar", "44100",
                "-ac", "2",
                "-movflags", "+faststart",
                raw_short.as_posix(),
            ],
            capture_output=True,
            check=True,
        )

        # 2단계: SRT slice + 작은 자막 번인 (소스에 자막 없을 때만)
        if not source_has_subs and srt_path is not None and srt_path.exists():
            sliced_srt = project_dir / "video" / f"_shorts_sub_{index:02d}.srt"
            sliced_content = _slice_and_shift_srt(srt_path, start_sec, duration)
            if sliced_content.strip():
                sliced_srt.write_text(sliced_content, encoding="utf-8")

                font = shorts_sub_cfg.get("font", "NanumSquareRoundEB")
                font_size = int(shorts_sub_cfg.get("font_size", 11))
                outline = int(shorts_sub_cfg.get("outline_width", 2))
                shadow = int(shorts_sub_cfg.get("shadow_offset", 1))

                style = (
                    f"FontName={font},FontSize={font_size},"
                    f"PrimaryColour=&H00FFFFFF&,OutlineColour=&H00000000&,"
                    f"BackColour=&H80000000&,BorderStyle=4,"
                    f"Outline={outline},Shadow={shadow},Alignment=2,"
                    f"MarginV=80,MarginL=30,MarginR=30"
                )

                # Windows 한글 경로 이슈 회피: forward slash + 상대 이름 사용
                srt_fs = sliced_srt.as_posix().replace(":", r"\:")
                subprocess.run(
                    [
                        "ffmpeg", "-y",
                        "-i", raw_short.as_posix(),
                        "-vf", f"subtitles='{srt_fs}':force_style='{style}'",
                        "-c:v", "libx264",
                        "-preset", "medium",
                        "-crf", "23",
                        "-pix_fmt", "yuv420p",
                        "-c:a", "copy",
                        "-movflags", "+faststart",
                        output.as_posix(),
                    ],
                    capture_output=True,
                    check=True,
                )
                sliced_srt.unlink(missing_ok=True)
                raw_short.unlink(missing_ok=True)
                return

        # 폴백: 자막 번인 생략, raw를 그대로 사용
        shutil.move(str(raw_short), str(output))

    def _get_duration(self, file_path: Path) -> float:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path.as_posix(),
            ],
            capture_output=True,
            text=True,
        )
        try:
            return float(result.stdout.strip())
        except ValueError:
            return 0.0
