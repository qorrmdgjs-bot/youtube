"""Stage D: TTS narration generation for each scene.

Supports Google Cloud TTS (premium) and gTTS (free fallback).
Post-processes audio for broadcast quality: stereo, 44.1kHz, warmth EQ.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml

from src.engines.llm_client import PROJECT_ROOT
from src.models import ProjectManifest, Script
from src.pipeline.base_stage import BaseStage


class TTSGenStage(BaseStage):
    name = "d_tts_gen"
    dependencies = ["b_scene_segment"]

    def execute(self, project_dir: Path, manifest: ProjectManifest) -> float:
        script = Script.model_validate_json(
            (project_dir / "script.json").read_text(encoding="utf-8")
        )

        with open(PROJECT_ROOT / "config" / "settings.yaml", encoding="utf-8") as f:
            settings = yaml.safe_load(f)

        tts_config = settings.get("tts", {})
        voice_gender = manifest.brief.voice_gender
        client = self._get_tts_client(tts_config, voice_gender)

        total_cost = 0.0
        audio_dir = project_dir / "audio"
        audio_dir.mkdir(exist_ok=True)

        scene_audio_paths: list[Path] = []

        for scene in script.scenes:
            raw_path = audio_dir / f"scene_{scene.index:03d}_raw.mp3"
            final_path = audio_dir / f"scene_{scene.index:03d}.mp3"

            cost = client.synthesize(text=scene.dialogue, output_path=raw_path)
            total_cost += cost

            # Post-process: normalize, warm EQ, stereo, 44.1kHz
            self._post_process_audio(raw_path, final_path, scene)
            raw_path.unlink(missing_ok=True)

            scene_audio_paths.append(final_path)

            actual_duration = self._get_audio_duration(final_path)
            if actual_duration > scene.duration_sec:
                scene.duration_sec = round(actual_duration + 0.5, 1)

            self.log.info(
                "scene_tts_done",
                scene=scene.index,
                duration=round(actual_duration, 1),
            )

        # Concatenate with silence gaps between scenes
        self._concat_audio_with_gaps(script, scene_audio_paths, audio_dir / "narration_full.mp3")

        # Save updated script
        (project_dir / "script.json").write_text(
            script.model_dump_json(indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        self.log.info("tts_complete", scenes=len(script.scenes), cost=total_cost)
        return total_cost

    def _get_tts_client(self, tts_config: dict, voice_gender: str):
        # Priority: ElevenLabs > Google Cloud TTS > gTTS fallback
        if os.environ.get("ELEVENLABS_API_KEY"):
            from src.engines.elevenlabs_client import ElevenLabsTTSClient
            self.log.info("using_elevenlabs_tts", voice_gender=voice_gender)
            return ElevenLabsTTSClient(voice_gender=voice_gender)

        if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            from src.engines.tts_client import TTSClient
            voice_name = tts_config.get(f"voice_{voice_gender}", "ko-KR-Wavenet-A")
            return TTSClient(
                voice_name=voice_name,
                speaking_rate=tts_config.get("speaking_rate", 0.88),
                pitch=tts_config.get("pitch", -1.0),
            )
        self.log.warning("google_tts_unavailable, using gTTS fallback")
        return _GTTSFallback()

    def _post_process_audio(self, input_path: Path, output_path: Path, scene) -> None:
        """Post-process TTS audio: normalize, warm EQ, stereo 44.1kHz.

        - Upsample to 44100Hz stereo for broadcast quality
        - Apply warm EQ: boost low-mids (200-400Hz), gentle high roll-off
        - Normalize loudness to -16 LUFS (YouTube standard)
        - Add subtle reverb for warmth
        """
        # Build filter chain
        filters = [
            # Upsample to 44.1kHz
            "aresample=44100",
            # Warm EQ: boost 250Hz warmth, cut harsh 4kHz
            "equalizer=f=250:t=q:w=1.5:g=3",
            "equalizer=f=4000:t=q:w=2:g=-2",
            # Gentle compression for even volume
            "acompressor=threshold=-20dB:ratio=3:attack=20:release=200",
            # Normalize loudness
            "loudnorm=I=-16:LRA=11:TP=-1.5",
            # Convert to stereo
            "pan=stereo|FL=FC|FR=FC",
        ]

        # Add silence before climax scenes
        if scene.has_silence_before and scene.silence_duration_sec > 0:
            ms = int(scene.silence_duration_sec * 1000)
            filters.insert(0, f"adelay={ms}|{ms}")

        filter_str = ",".join(filters)

        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(input_path),
                "-af", filter_str,
                "-c:a", "libmp3lame",
                "-q:a", "2",  # High quality MP3 (~190kbps)
                "-ar", "44100",
                "-ac", "2",
                str(output_path),
            ],
            capture_output=True,
        )

        if result.returncode != 0:
            # Fallback: simple conversion without EQ
            self.log.warning("audio_postprocess_failed, using simple conversion")
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", str(input_path),
                    "-ar", "44100",
                    "-ac", "2",
                    "-c:a", "libmp3lame",
                    "-q:a", "2",
                    str(output_path),
                ],
                capture_output=True,
                check=True,
            )

    def _get_audio_duration(self, audio_path: Path) -> float:
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

    def _concat_audio_with_gaps(
        self, script, audio_paths: list[Path], output_path: Path
    ) -> None:
        """Concatenate scene audio with natural silence gaps between scenes."""
        # Write concat list in the project directory (avoids Windows temp path encoding issues)
        list_file = audio_paths[0].parent / "_concat_list.txt"

        with open(list_file, "w", encoding="utf-8") as f:
            for i, p in enumerate(audio_paths):
                f.write(f"file '{p.resolve().as_posix()}'\n")
                # Add short silence between scenes (not after last)
                if i < len(audio_paths) - 1:
                    silence_path = p.parent / f"_silence_{i}.mp3"
                    self._create_silence(silence_path, 0.8)  # 0.8s gap
                    f.write(f"file '{silence_path.resolve().as_posix()}'\n")

        try:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", str(list_file),
                    "-c", "copy",
                    str(output_path),
                ],
                capture_output=True,
                check=True,
            )
        finally:
            list_file.unlink(missing_ok=True)
            # Clean up silence files
            for i in range(len(audio_paths) - 1):
                (audio_paths[0].parent / f"_silence_{i}.mp3").unlink(missing_ok=True)

    def _create_silence(self, output_path: Path, duration_sec: float) -> None:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", f"anullsrc=r=44100:cl=stereo",
                "-t", str(duration_sec),
                "-c:a", "libmp3lame",
                "-q:a", "2",
                str(output_path),
            ],
            capture_output=True,
            check=True,
        )


class _GTTSFallback:
    """Free gTTS fallback - uses normal speed (not slow) for natural pacing."""

    def synthesize(self, text: str, output_path: Path, **kwargs) -> float:
        from gtts import gTTS

        # slow=False is more natural; slow=True sounds robotic
        tts = gTTS(text=text, lang="ko", slow=False)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tts.save(str(output_path))
        return 0.0
