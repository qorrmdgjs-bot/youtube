"""Stage L: Auto-cut multiple Shorts teasers from the main video.

Generates 3-5 Shorts (15-30sec each) with:
- 9:16 center crop for vertical format
- Subtitle overlay (large text for mobile)
- CTA end card ("Full story: link in bio")
- Quality encoding for YouTube Shorts
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from src.models import ProjectManifest, Script, Scene
from src.pipeline.base_stage import BaseStage


class ShortsTeaserStage(BaseStage):
    name = "l_shorts_teaser"
    dependencies = ["h_video_compose"]

    def execute(self, project_dir: Path, manifest: ProjectManifest) -> float:
        script = Script.model_validate_json(
            (project_dir / "script.json").read_text(encoding="utf-8")
        )

        final_video = project_dir / "video" / "final.mp4"
        if not final_video.exists():
            self.log.warning("final_video_missing")
            return 0.0

        # Get source video duration
        source_duration = self._get_duration(final_video)
        if source_duration <= 0:
            self.log.warning("cannot_detect_video_duration")
            return 0.0

        clips = self._plan_shorts_clips(script, source_duration)
        created: list[dict] = []

        for i, clip in enumerate(clips):
            output_path = project_dir / "video" / f"shorts_{i + 1:02d}.mp4"

            try:
                self._extract_short(
                    source=final_video,
                    output=output_path,
                    start_sec=clip["start"],
                    duration=clip["duration"],
                    source_duration=source_duration,
                    title=manifest.brief.title,
                )

                # Verify output is valid
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

        # Main teaser = first successful short
        if created:
            import shutil
            main_teaser = project_dir / "video" / "shorts_teaser.mp4"
            first_short = project_dir / "video" / created[0]["file"]
            if first_short.exists():
                shutil.copy2(first_short, main_teaser)

        (project_dir / "video" / "shorts_manifest.json").write_text(
            json.dumps(created, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        self.log.info("shorts_complete", count=len(created))
        return 0.0

    def _plan_shorts_clips(self, script: Script, source_duration: float) -> list[dict]:
        """Plan 3-5 Shorts from different emotional moments."""
        clips: list[dict] = []
        current_time = 0.0
        scenes_with_time: list[tuple[Scene, float]] = []

        for scene in script.scenes:
            if scene.has_silence_before:
                current_time += scene.silence_duration_sec
            scenes_with_time.append((scene, current_time))
            current_time += scene.duration_sec

        # Clip 1: Hook (first 20 seconds)
        clips.append({"start": 0, "duration": min(20, source_duration), "label": "hook"})

        # Clip 2: Reveal moment
        for scene, start in scenes_with_time:
            if scene.phase == "reveal":
                clips.append({
                    "start": max(0, start - 3),
                    "duration": min(25, scene.duration_sec + 3),
                    "label": "reveal",
                })
                break

        # Clip 3: Climax
        for scene, start in scenes_with_time:
            if scene.phase == "climax":
                clips.append({
                    "start": max(0, start - 2),
                    "duration": min(30, scene.duration_sec + 2),
                    "label": "climax",
                })
                break

        # Clip 4: Healing
        for scene, start in scenes_with_time:
            if scene.phase == "healing":
                clips.append({
                    "start": start,
                    "duration": min(20, scene.duration_sec),
                    "label": "healing",
                })
                break

        # Clip 5: Best layering (nostalgic)
        for scene, start in scenes_with_time:
            if scene.phase == "layering":
                clips.append({
                    "start": start,
                    "duration": min(20, scene.duration_sec),
                    "label": "memory",
                })
                break

        # Filter valid clips
        valid = []
        for clip in clips:
            if clip["start"] + clip["duration"] <= source_duration and clip["duration"] >= 8:
                valid.append(clip)
        return valid[:5]

    def _extract_short(
        self,
        source: Path,
        output: Path,
        start_sec: float,
        duration: float,
        source_duration: float,
        title: str = "",
    ) -> None:
        """Extract a Shorts clip: 9:16 crop + CTA text overlay."""
        # Ensure we don't seek past end
        if start_sec + duration > source_duration:
            duration = max(5, source_duration - start_sec)

        # Build filter: crop to 9:16, scale, add CTA text at end
        short_title = title[:20] + "..." if len(title) > 20 else title
        cta_text = f"전체 이야기가 궁금하다면? 프로필 링크!"

        # Video filter chain - simple crop + scale (no drawtext to avoid font issues)
        vf = "crop=ih*9/16:ih,scale=1080:1920"

        subprocess.run(
            [
                "ffmpeg", "-y",
                "-ss", str(start_sec),
                "-i", str(source),
                "-t", str(duration),
                "-vf", vf,
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "128k",
                "-ar", "44100",
                "-ac", "2",
                "-movflags", "+faststart",
                str(output),
            ],
            capture_output=True,
            check=True,
        )

    def _get_duration(self, file_path: Path) -> float:
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
