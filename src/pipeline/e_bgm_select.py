"""Stage E: BGM selection per scene emotion phase.

Selects different BGM tracks for each emotional phase of the video,
then stitches them together with crossfade transitions for a natural flow.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from src.engines.llm_client import PROJECT_ROOT
from src.models import ProjectManifest, Script
from src.pipeline.base_stage import BaseStage


class BGMSelectStage(BaseStage):
    name = "e_bgm_select"
    dependencies = ["b_scene_segment"]

    def execute(self, project_dir: Path, manifest: ProjectManifest) -> float:
        script = Script.model_validate_json(
            (project_dir / "script.json").read_text(encoding="utf-8")
        )

        with open(PROJECT_ROOT / "config" / "bgm_library.yaml", encoding="utf-8") as f:
            bgm_config = yaml.safe_load(f)

        tracks = bgm_config.get("tracks", {})
        emotion_map = bgm_config.get("emotion_mood_map", {})

        # Group scenes by emotional phase
        phases = self._group_by_phase(script.scenes)

        # Select BGM for each phase
        phase_bgms: list[dict] = []
        for phase_name, phase_scenes in phases:
            # Get dominant emotion for this phase
            emotion_counts: dict[str, int] = {}
            for s in phase_scenes:
                emotion_counts[s.emotion] = emotion_counts.get(s.emotion, 0) + 1
            dominant_emotion = max(emotion_counts, key=emotion_counts.get) if emotion_counts else "warmth_peace"

            target_moods = emotion_map.get(dominant_emotion, ["warm", "nostalgia"])
            track_id = self._select_track(tracks, target_moods)

            if not track_id:
                track_id = next(iter(tracks.keys())) if tracks else None

            phase_duration = sum(s.duration_sec + s.silence_duration_sec for s in phase_scenes)

            phase_bgms.append({
                "phase": phase_name,
                "track_id": track_id,
                "emotion": dominant_emotion,
                "duration": phase_duration,
            })

            self.log.info(
                "bgm_phase_selected",
                phase=phase_name,
                track=track_id,
                emotion=dominant_emotion,
                duration=round(phase_duration, 1),
            )

        # Build combined BGM audio
        output_path = project_dir / "audio" / "bgm.mp3"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not phase_bgms or not any(p["track_id"] for p in phase_bgms):
            self.log.warning("no_bgm_available")
            self._create_silence(output_path, script.total_duration_sec)
            return 0.0

        self._build_phased_bgm(tracks, phase_bgms, output_path)

        # Save BGM selection info
        import json
        bgm_info = {
            "phases": phase_bgms,
            "total_duration": script.total_duration_sec,
        }
        (project_dir / "audio" / "bgm_info.json").write_text(
            json.dumps(bgm_info, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        self.log.info("bgm_complete", phases=len(phase_bgms))
        return 0.0

    def _group_by_phase(self, scenes) -> list[tuple[str, list]]:
        """Group consecutive scenes by their emotional phase."""
        if not scenes:
            return []

        groups: list[tuple[str, list]] = []
        current_phase = scenes[0].phase
        current_group: list = [scenes[0]]

        for scene in scenes[1:]:
            if scene.phase == current_phase:
                current_group.append(scene)
            else:
                groups.append((current_phase, current_group))
                current_phase = scene.phase
                current_group = [scene]

        groups.append((current_phase, current_group))
        return groups

    def _select_track(self, tracks: dict, target_moods: list[str]) -> str | None:
        """Select best matching track based on mood overlap."""
        best_track = None
        best_score = -1

        for track_id, info in tracks.items():
            track_moods = set(info.get("mood", []))
            overlap = len(track_moods & set(target_moods))
            if overlap > best_score:
                best_score = overlap
                best_track = track_id

        return best_track

    def _build_phased_bgm(self, tracks: dict, phase_bgms: list[dict], output_path: Path) -> None:
        """Build BGM by stitching phase-specific tracks with crossfade."""
        import tempfile

        phase_clips: list[Path] = []
        crossfade_sec = 2.0

        for i, phase in enumerate(phase_bgms):
            track_id = phase["track_id"]
            if not track_id or track_id not in tracks:
                continue

            track_info = tracks[track_id]
            source_path = PROJECT_ROOT / "assets" / "bgm" / track_info["file"]

            if not source_path.exists():
                continue

            clip_path = output_path.parent / f"_bgm_phase_{i}.mp3"
            duration = phase["duration"]

            # Trim/loop track to phase duration with fade
            fade_in = 1.5 if i == 0 else crossfade_sec
            fade_out = 3.0 if i == len(phase_bgms) - 1 else crossfade_sec

            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-stream_loop", "-1",
                    "-i", str(source_path),
                    "-t", str(duration + crossfade_sec),  # Extra for crossfade overlap
                    "-af", f"afade=t=in:st=0:d={fade_in},afade=t=out:st={duration - fade_out + crossfade_sec}:d={fade_out}",
                    "-c:a", "libmp3lame",
                    "-q:a", "2",
                    str(clip_path),
                ],
                capture_output=True,
            )
            phase_clips.append(clip_path)

        if not phase_clips:
            self._create_silence(output_path, sum(p["duration"] for p in phase_bgms))
            return

        if len(phase_clips) == 1:
            import shutil
            shutil.move(str(phase_clips[0]), str(output_path))
            return

        # Concatenate phase clips
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            for p in phase_clips:
                f.write(f"file '{p.resolve()}'\n")
            list_file = f.name

        try:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", list_file,
                    "-c:a", "libmp3lame",
                    "-q:a", "2",
                    str(output_path),
                ],
                capture_output=True,
                check=True,
            )
        finally:
            Path(list_file).unlink(missing_ok=True)
            for p in phase_clips:
                p.unlink(missing_ok=True)

    def _create_silence(self, output: Path, duration_sec: float) -> None:
        """Create a silent audio file as placeholder."""
        output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", f"anullsrc=r=44100:cl=stereo",
                "-t", str(duration_sec),
                "-c:a", "libmp3lame",
                "-q:a", "2",
                str(output),
            ],
            capture_output=True,
            check=True,
        )
