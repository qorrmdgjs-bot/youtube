"""Stage F: Generate SRT subtitle file synced to actual TTS audio timing.

Reads actual audio duration per scene to sync subtitles with narration.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from src.engines.llm_client import PROJECT_ROOT
from src.models import ProjectManifest, Script
from src.pipeline.base_stage import BaseStage
from src.utils.hangul_utils import split_subtitle_lines


class SubtitleSplitStage(BaseStage):
    name = "f_subtitle_split"
    dependencies = ["d_tts_gen"]  # Must run after TTS to use actual audio durations

    def execute(self, project_dir: Path, manifest: ProjectManifest) -> float:
        script = Script.model_validate_json(
            (project_dir / "script.json").read_text(encoding="utf-8")
        )

        with open(PROJECT_ROOT / "config" / "settings.yaml", encoding="utf-8") as f:
            settings = yaml.safe_load(f)

        subtitle_config = settings.get("subtitle", {})
        max_chars = subtitle_config.get("max_chars_per_line", 18)

        audio_dir = project_dir / "audio"
        srt_entries: list[str] = []
        entry_index = 1
        current_time = 0.0

        for scene in script.scenes:
            # Add silence gap between scenes (0.8s gap from TTS stage)
            if scene.index > 0:
                current_time += 0.8

            # Get actual audio duration for this scene
            audio_path = audio_dir / f"scene_{scene.index:03d}.mp3"
            if audio_path.exists():
                scene_audio_duration = self._get_audio_duration(audio_path)
            else:
                scene_audio_duration = scene.duration_sec

            # Split dialogue into subtitle chunks
            lines = self._split_dialogue_to_chunks(scene.dialogue, max_chars)
            if not lines:
                current_time += scene_audio_duration
                continue

            # Distribute actual audio duration across chunks proportionally by text length
            total_chars = sum(len(line) for line in lines)
            if total_chars == 0:
                current_time += scene_audio_duration
                continue

            for line_text in lines:
                # Duration proportional to text length
                line_ratio = len(line_text) / total_chars
                line_duration = scene_audio_duration * line_ratio

                start_time = current_time
                end_time = current_time + line_duration

                srt_entries.append(
                    f"{entry_index}\n"
                    f"{self._format_srt_time(start_time)} --> {self._format_srt_time(end_time)}\n"
                    f"{line_text}\n"
                )

                entry_index += 1
                current_time = end_time

        # Write SRT file
        srt_content = "\n".join(srt_entries)
        subtitles_dir = project_dir / "subtitles"
        subtitles_dir.mkdir(exist_ok=True)
        (subtitles_dir / "raw.srt").write_text(srt_content, encoding="utf-8")

        self.log.info(
            "subtitles_generated",
            entries=entry_index - 1,
            duration=round(current_time, 1),
        )

        return 0.0

    def _split_dialogue_to_chunks(self, text: str, max_chars: int) -> list[str]:
        """Split dialogue into subtitle-friendly chunks."""
        import re

        # Remove [침묵] markers
        cleaned = re.sub(r"\[침묵\]", "", text.strip())

        # Split by sentence boundaries
        sentences = re.split(r"(?<=[.!?])\s+", cleaned)

        chunks: list[str] = []
        for sentence in sentences:
            stripped = sentence.strip()
            if not stripped or len(stripped) <= 1:
                continue
            lines = split_subtitle_lines(stripped, max_chars)
            chunks.extend(lines)

        return [c for c in chunks if c.strip() and len(c.strip()) > 1]

    def _get_audio_duration(self, audio_path: Path) -> float:
        """Get actual audio file duration in seconds."""
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
        )
        try:
            return float(result.stdout.strip())
        except ValueError:
            return 5.0

    def _format_srt_time(self, seconds: float) -> str:
        """Format seconds to SRT timestamp (HH:MM:SS,mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
