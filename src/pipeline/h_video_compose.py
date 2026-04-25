"""Stage H: Video composition - combines images, audio, subtitles into final video."""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from src.engines.ffmpeg_wrapper import (
    burn_subtitles,
    compose_final_video,
    concat_videos_with_transitions,
    ken_burns_scene,
)
from src.engines.llm_client import PROJECT_ROOT
from src.models import ProjectManifest, Script
from src.pipeline.base_stage import BaseStage


# 0.8s inter-scene silence is added by d_tts_gen between every adjacent pair of scene mp3s.
# We extend each (non-last) clip by this amount so the visual stays through that silence,
# keeping picture<->narration alignment.
INTER_SCENE_GAP_SEC = 0.8


def _ffprobe_duration(file_path: Path) -> float:
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


class VideoComposeStage(BaseStage):
    name = "h_video_compose"
    dependencies = ["d_tts_gen", "f_subtitle_split", "g_image_gen"]

    def execute(self, project_dir: Path, manifest: ProjectManifest) -> float:
        script = Script.model_validate_json(
            (project_dir / "script.json").read_text(encoding="utf-8")
        )

        with open(PROJECT_ROOT / "config" / "settings.yaml", encoding="utf-8") as f:
            settings = yaml.safe_load(f)

        scene_config = settings.get("scene", {})
        video_config = settings.get("video", {})
        subtitle_cfg = settings.get("subtitle", {})

        video_dir = project_dir / "video"
        video_dir.mkdir(exist_ok=True)
        scenes_dir = project_dir / "scenes"

        # Step 1: Create video clips from images using Ken Burns effect.
        # Use ACTUAL TTS audio durations (per-scene mp3) rather than planned scene.duration_sec
        # so the picture and narration stay in sync (LLM duration estimates are unreliable).
        self.log.info("step_video_clips_start")
        scene_clips: list[Path] = []
        audio_dir = project_dir / "audio"
        n_scenes = len(script.scenes)

        for i, scene in enumerate(script.scenes):
            # Image is shared across all sub-scenes that have the same image_key,
            # so look it up by the group key. Audio + clip stay per-scene.
            image_key = scene.image_key if scene.image_key is not None else scene.index
            image_path = scenes_dir / f"scene_{image_key:03d}.png"
            clip_path = video_dir / f"clip_{scene.index:03d}.mp4"
            audio_path = audio_dir / f"scene_{scene.index:03d}.mp3"

            # Per-scene audio duration (already includes silence_before for climax)
            actual_audio_dur = _ffprobe_duration(audio_path) if audio_path.exists() else 0.0
            if actual_audio_dur <= 0:
                # Fallback when audio missing — use planned values
                actual_audio_dur = scene.duration_sec
                if scene.has_silence_before:
                    actual_audio_dur += scene.silence_duration_sec

            # Hold the same image during the inter-scene silence (every clip but the last)
            inter_gap = INTER_SCENE_GAP_SEC if i < n_scenes - 1 else 0.0
            total_duration = actual_audio_dur + inter_gap

            if image_path.exists():
                ken_burns_scene(
                    image_path=image_path,
                    output_path=clip_path,
                    duration_sec=total_duration,
                    fps=video_config.get("fps", 24),
                    zoom_speed=scene_config.get("ken_burns_zoom_speed", 0.0005),
                    max_zoom=scene_config.get("ken_burns_max_zoom", 1.3),
                    scene_index=scene.index,
                )
                self.log.info(
                    "ken_burns_applied",
                    scene=scene.index,
                    audio_dur=round(actual_audio_dur, 2),
                    inter_gap=inter_gap,
                    total=round(total_duration, 2),
                )
            else:
                self.log.warning("no_visual_source", scene=scene.index)
                continue

            scene_clips.append(clip_path)

        if not scene_clips:
            raise RuntimeError("생성된 장면 클립이 없습니다.")

        # Step 2: Concatenate all scene clips.
        # For series mode (where clip durations are precisely tied to per-scene audio
        # durations), use simple concat to keep visuals in sync with narration.
        # xfade would overlap clips and shrink the video by ~0.5s per transition.
        self.log.info("step_concat_start")
        raw_video_path = video_dir / "raw.mp4"
        is_series_mode = manifest.brief.series_id is not None

        if is_series_mode:
            self._simple_concat(scene_clips, raw_video_path)
        else:
            concat_videos_with_transitions(
                video_paths=scene_clips,
                output_path=raw_video_path,
                transition_duration=scene_config.get("transition_duration_sec", 0.5),
            )

        # Step 3: Use narration as the audio track (BGM permanently disabled).
        self.log.info("step_audio_prep_start")
        narration_path = project_dir / "audio" / "narration_full.mp3"
        mixed_audio_path = project_dir / "audio" / "mixed.mp3"

        if not narration_path.exists():
            raise RuntimeError(f"내레이션 오디오 파일이 없습니다: {narration_path}")

        import shutil
        shutil.copy2(narration_path, mixed_audio_path)

        # Step 4: Combine video + audio
        self.log.info("step_compose_start")
        composed_path = video_dir / "composed.mp4"
        compose_final_video(
            video_path=raw_video_path,
            audio_path=mixed_audio_path,
            output_path=composed_path,
        )

        # Step 5: Burn subtitles
        self.log.info("step_subtitle_burn_start")
        srt_path = project_dir / "subtitles" / "raw.srt"
        final_path = video_dir / "final.mp4"

        if srt_path.exists():
            burn_subtitles(
                video_path=composed_path,
                subtitle_path=srt_path,
                output_path=final_path,
                font_name=subtitle_cfg.get("font", "NanumSquareRoundEB"),
                font_size=subtitle_cfg.get("font_size", 52),
            )
        else:
            # No subtitles - just rename composed as final
            import shutil
            shutil.copy2(composed_path, final_path)

        # Clean up intermediate clips
        for clip in scene_clips:
            clip.unlink(missing_ok=True)
        raw_video_path.unlink(missing_ok=True)
        # NOTE: composed.mp4 (subtitle 미적용 합본)는 삭제하지 않음 — Stage L(shorts)에서
        # 9:16 portrait용 큰 폰트 자막을 새로 burn 할 때 source로 사용함.

        self.log.info("video_compose_complete", final=str(final_path))
        return 0.0  # No API cost for video composition

    def _simple_concat(self, video_paths: list[Path], output_path: Path) -> None:
        """Concatenate clips with no transitions (preserves exact total duration).

        Used in series mode where per-scene clip durations are derived from actual
        audio durations and any xfade overlap would break narration↔picture sync.
        """
        list_file = output_path.parent / "_concat_list.txt"
        list_file.write_text(
            "\n".join(f"file '{p.resolve().as_posix()}'" for p in video_paths) + "\n",
            encoding="utf-8",
        )
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
