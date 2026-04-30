"""Stage H: Video composition - combines images, audio, subtitles into final video.

Supports mixed clip sources per scene: AI-generated clips from stage G2 (Veo 3.1)
when available, Ken Burns from static images otherwise.
"""

from __future__ import annotations

import subprocess
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


def _prepare_ai_clip(
    src_clip: Path,
    output_path: Path,
    duration_sec: float,
    fps: int,
    resolution: tuple[int, int] = (1920, 1080),
) -> None:
    """Normalize an AI-generated clip to target duration/resolution/fps.

    Loops the source clip if shorter than the target, trims if longer.
    """
    w, h = resolution
    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"setsar=1,fps={fps}"
    )
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-stream_loop", "-1",
            "-i", str(src_clip),
            "-t", f"{duration_sec:.3f}",
            "-vf", vf,
            "-an",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )


class VideoComposeStage(BaseStage):
    name = "h_video_compose"
    dependencies = [
        "d_tts_gen",
        "e_bgm_select",
        "f_subtitle_split",
        "g_image_gen",
        "g2_image_to_video",
    ]

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
        ai_clips_dir = project_dir / "video_clips"

        # Step 1: Create per-scene clips — prefer AI clip (Veo) if present, else Ken Burns
        self.log.info("step_video_clips_start")
        scene_clips: list[Path] = []
        fps = video_config.get("fps", 24)
        resolution = tuple(video_config.get("resolution", [1920, 1080]))

        for scene in script.scenes:
            image_path = scenes_dir / f"scene_{scene.index:03d}.png"
            ai_clip_path = ai_clips_dir / f"clip_{scene.index:03d}.mp4"
            clip_path = video_dir / f"clip_{scene.index:03d}.mp4"

            total_duration = scene.duration_sec
            if scene.has_silence_before:
                total_duration += scene.silence_duration_sec

            if ai_clip_path.exists():
                try:
                    _prepare_ai_clip(
                        src_clip=ai_clip_path,
                        output_path=clip_path,
                        duration_sec=total_duration,
                        fps=fps,
                        resolution=resolution,
                    )
                    self.log.info(
                        "ai_clip_applied", scene=scene.index, duration=total_duration
                    )
                    scene_clips.append(clip_path)
                    continue
                except subprocess.CalledProcessError as e:
                    self.log.warning(
                        "ai_clip_prepare_failed_falling_back_kenburns",
                        scene=scene.index,
                        error=str(e),
                    )

            if image_path.exists():
                ken_burns_scene(
                    image_path=image_path,
                    output_path=clip_path,
                    duration_sec=total_duration,
                    fps=fps,
                    zoom_speed=scene_config.get("ken_burns_zoom_speed", 0.0005),
                    max_zoom=scene_config.get("ken_burns_max_zoom", 1.3),
                    scene_index=scene.index,
                )
                self.log.info("ken_burns_applied", scene=scene.index, duration=total_duration)
                scene_clips.append(clip_path)
            else:
                self.log.warning("no_visual_source", scene=scene.index)
                continue

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

        # Clean up intermediate scene clips and raw concat
        for clip in scene_clips:
            clip.unlink(missing_ok=True)
        raw_video_path.unlink(missing_ok=True)
        # composed.mp4(자막 이전)는 쇼츠에서 재사용 — 삭제하지 않음

        self.log.info("video_compose_complete", final=str(final_path))
        return 0.0  # No API cost for video composition
