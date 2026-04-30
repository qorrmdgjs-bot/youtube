"""Stage G2: Convert selected scene images to short AI video clips (Veo 3.1).

Only scenes flagged ``use_ai_video=True`` are converted. Others remain as stills
and are animated with Ken Burns in stage H. If no video engine is available,
the stage becomes a no-op (H falls back to Ken Burns for every scene).
"""

from __future__ import annotations

import time
from pathlib import Path

import yaml

from src.engines.engine_factory import get_video_client
from src.engines.llm_client import PROJECT_ROOT
from src.models import ProjectManifest, Script
from src.pipeline.base_stage import BaseStage


class ImageToVideoStage(BaseStage):
    name = "g2_image_to_video"
    dependencies = ["g_image_gen"]

    def execute(self, project_dir: Path, manifest: ProjectManifest) -> float:
        with open(PROJECT_ROOT / "config" / "settings.yaml", encoding="utf-8") as f:
            settings = yaml.safe_load(f)

        video_cfg = settings.get("video_engine", {})
        engine = video_cfg.get("engine", "ken_burns")
        duration_sec = int(video_cfg.get("veo_duration_sec", 6))

        if engine == "ken_burns":
            self.log.info("video_engine_ken_burns, skipping g2")
            return 0.0

        client = get_video_client(settings)
        if client is None:
            self.log.warning("no_video_client_available, skipping g2 (ken burns fallback)")
            return 0.0

        script = Script.model_validate_json(
            (project_dir / "script.json").read_text(encoding="utf-8")
        )

        video_clips_dir = project_dir / "video_clips"
        video_clips_dir.mkdir(exist_ok=True)

        if engine == "veo_all":
            target_scenes = list(script.scenes)
        else:
            target_scenes = [s for s in script.scenes if s.use_ai_video]

        self.log.info(
            "g2_targets",
            engine=engine,
            total_scenes=len(script.scenes),
            ai_video_scenes=len(target_scenes),
        )

        total_cost = 0.0

        for i, scene in enumerate(target_scenes):
            image_path = project_dir / "scenes" / f"scene_{scene.index:03d}.png"
            clip_path = video_clips_dir / f"clip_{scene.index:03d}.mp4"

            if not image_path.exists():
                self.log.warning("image_missing_for_video", scene=scene.index)
                continue

            if clip_path.exists():
                self.log.info("video_clip_exists_skip", scene=scene.index)
                continue

            if i > 0:
                time.sleep(12)

            motion_hint = scene.motion_prompt or "gentle subtle motion, cinematic, emotional"
            base_prompt = scene.visual_prompt or scene.visual_description or ""
            motion_prompt = f"{motion_hint}. {base_prompt[:200]}"

            try:
                cost = client.generate(
                    image_path=image_path,
                    output_path=clip_path,
                    prompt=motion_prompt,
                    duration_sec=duration_sec,
                )
                total_cost += cost
                self.log.info("video_clip_generated", scene=scene.index, cost=cost)
            except Exception as e:
                self.log.warning(
                    "video_clip_failed_will_use_kenburns",
                    scene=scene.index,
                    error=str(e),
                )

        self.log.info(
            "image_to_video_complete",
            targets=len(target_scenes),
            cost=total_cost,
        )
        return total_cost
