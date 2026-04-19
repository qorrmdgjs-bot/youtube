"""Stage H: Video composition - combines images, audio, subtitles into final video."""

from __future__ import annotations

from pathlib import Path

import yaml

from src.engines.ffmpeg_wrapper import (
    burn_subtitles,
    compose_final_video,
    concat_videos_with_transitions,
    ken_burns_scene,
    mix_audio,
)
from src.engines.llm_client import PROJECT_ROOT
from src.models import ProjectManifest, Script
from src.pipeline.base_stage import BaseStage


class VideoComposeStage(BaseStage):
    name = "h_video_compose"
    dependencies = ["d_tts_gen", "e_bgm_select", "f_subtitle_split", "g_image_gen"]

    def execute(self, project_dir: Path, manifest: ProjectManifest) -> float:
        script = Script.model_validate_json(
            (project_dir / "script.json").read_text(encoding="utf-8")
        )

        with open(PROJECT_ROOT / "config" / "settings.yaml", encoding="utf-8") as f:
            settings = yaml.safe_load(f)

        scene_config = settings.get("scene", {})
        video_config = settings.get("video", {})
        subtitle_cfg = settings.get("subtitle", {})
        audio_cfg = settings.get("audio", {})

        video_dir = project_dir / "video"
        video_dir.mkdir(exist_ok=True)
        scenes_dir = project_dir / "scenes"

        # Step 1: Create video clips for each scene
        # Use AI-generated video clips if available, fall back to Ken Burns
        self.log.info("step_video_clips_start")
        scene_clips: list[Path] = []
        video_clips_dir = project_dir / "video_clips"

        for scene in script.scenes:
            ai_clip_path = video_clips_dir / f"clip_{scene.index:03d}.mp4"
            image_path = scenes_dir / f"scene_{scene.index:03d}.png"
            clip_path = video_dir / f"clip_{scene.index:03d}.mp4"

            total_duration = scene.duration_sec
            if scene.has_silence_before:
                total_duration += scene.silence_duration_sec

            if ai_clip_path.exists():
                # AI video clip exists - loop/extend it to match scene duration
                self._extend_clip_to_duration(
                    ai_clip_path, clip_path, total_duration,
                    video_config.get("fps", 24),
                )
                self.log.info("ai_clip_used", scene=scene.index, duration=total_duration)
            elif image_path.exists():
                # Fallback to Ken Burns
                ken_burns_scene(
                    image_path=image_path,
                    output_path=clip_path,
                    duration_sec=total_duration,
                    fps=video_config.get("fps", 24),
                    zoom_speed=scene_config.get("ken_burns_zoom_speed", 0.0005),
                    max_zoom=scene_config.get("ken_burns_max_zoom", 1.3),
                    scene_index=scene.index,
                )
                self.log.info("ken_burns_fallback", scene=scene.index, duration=total_duration)
            else:
                self.log.warning("no_visual_source", scene=scene.index)
                continue

            scene_clips.append(clip_path)

        if not scene_clips:
            raise RuntimeError("생성된 장면 클립이 없습니다.")

        # Step 2: Concatenate all scene clips
        self.log.info("step_concat_start")
        raw_video_path = video_dir / "raw.mp4"
        concat_videos_with_transitions(
            video_paths=scene_clips,
            output_path=raw_video_path,
            transition_duration=scene_config.get("transition_duration_sec", 0.5),
        )

        # Step 3: Mix audio (narration + BGM)
        self.log.info("step_audio_mix_start")
        narration_path = project_dir / "audio" / "narration_full.mp3"
        bgm_path = project_dir / "audio" / "bgm.mp3"
        mixed_audio_path = project_dir / "audio" / "mixed.mp3"

        if not narration_path.exists():
            raise RuntimeError(f"내레이션 오디오 파일이 없습니다: {narration_path}")

        if bgm_path.exists():
            mix_audio(
                narration_path=narration_path,
                bgm_path=bgm_path,
                output_path=mixed_audio_path,
                narration_db=audio_cfg.get("narration_db", -3),
                bgm_db=audio_cfg.get("bgm_db", -15),
                fade_out_sec=audio_cfg.get("fade_out_sec", 3.0),
            )
        else:
            # No BGM, use narration only
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
        composed_path.unlink(missing_ok=True)

        self.log.info("video_compose_complete", final=str(final_path))
        return 0.0  # No API cost for video composition

    def _extend_clip_to_duration(
        self, clip_path: Path, output_path: Path, target_duration: float, fps: int
    ) -> None:
        """Extend a short AI clip to match the scene duration.

        Uses slow-motion + loop + scale to 1920x1080 to fill the target duration.
        """
        import subprocess

        # Get original clip duration
        from src.engines.ffmpeg_wrapper import _get_duration
        original_dur = _get_duration(clip_path)
        if original_dur <= 0:
            original_dur = 4.0

        # Calculate slowdown factor to stretch the clip
        # If clip is 4s and we need 12s, slow down by 3x (minimum 0.25x speed)
        slowdown = min(target_duration / original_dur, 4.0)

        # Use setpts to slow down + scale to 1920x1080
        pts_factor = slowdown
        filter_str = (
            f"setpts={pts_factor}*PTS,"
            f"scale=1920:1080:force_original_aspect_ratio=decrease,"
            f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"
            f"fps={fps}"
        )

        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-stream_loop", "-1",  # Loop if still too short
                "-i", str(clip_path),
                "-vf", filter_str,
                "-t", str(target_duration),
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-an",  # No audio from clip
                str(output_path),
            ],
            capture_output=True,
        )

        if result.returncode != 0:
            self.log.warning("clip_extend_failed_using_kenburns", scene=str(clip_path))
            # Fallback to Ken Burns on the original image
            from src.engines.ffmpeg_wrapper import ken_burns_scene
            image_path = clip_path.parent.parent / "scenes" / clip_path.name.replace("clip_", "scene_").replace(".mp4", ".png")
            if image_path.exists():
                ken_burns_scene(
                    image_path=image_path,
                    output_path=output_path,
                    duration_sec=target_duration,
                    fps=fps,
                )
