"""Stage G2: Convert generated images to short video clips using AI.

Takes each scene image and generates a 3-5 second video clip with subtle
natural motion. Falls back to Ken Burns (handled in h_video_compose) if
the video generation API is unavailable.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from src.models import ProjectManifest, Script
from src.pipeline.base_stage import BaseStage


class ImageToVideoStage(BaseStage):
    name = "g2_image_to_video"
    dependencies = ["g_image_gen"]

    def execute(self, project_dir: Path, manifest: ProjectManifest) -> float:
        script = Script.model_validate_json(
            (project_dir / "script.json").read_text(encoding="utf-8")
        )

        client = self._get_client()
        if client is None:
            self.log.warning("image_to_video_skipped, will use Ken Burns fallback")
            return 0.0

        total_cost = 0.0
        video_clips_dir = project_dir / "video_clips"
        video_clips_dir.mkdir(exist_ok=True)

        for i, scene in enumerate(script.scenes):
            image_path = project_dir / "scenes" / f"scene_{scene.index:03d}.png"
            clip_path = video_clips_dir / f"clip_{scene.index:03d}.mp4"

            if not image_path.exists():
                self.log.warning("image_missing_for_video", scene=scene.index)
                continue

            if clip_path.exists():
                self.log.info("video_clip_exists_skip", scene=scene.index)
                continue

            # Rate limit: wait between requests to avoid 429
            if i > 0:
                time.sleep(12)

            # Use scene's visual prompt for motion guidance
            prompt = scene.visual_prompt or scene.visual_description or ""
            motion_prompt = f"gentle subtle motion, cinematic, {prompt[:200]}"

            try:
                cost = client.generate(
                    image_path=image_path,
                    output_path=clip_path,
                    prompt=motion_prompt,
                )
                total_cost += cost
                self.log.info(
                    "video_clip_generated",
                    scene=scene.index,
                    cost=cost,
                )
            except Exception as e:
                self.log.warning(
                    "video_clip_failed_will_use_kenburns",
                    scene=scene.index,
                    error=str(e),
                )

        self.log.info(
            "image_to_video_complete",
            scenes=len(script.scenes),
            cost=total_cost,
        )
        return total_cost

    def _get_client(self):
        """Get image-to-video client or None if unavailable."""
        if not os.environ.get("REPLICATE_API_TOKEN"):
            return None

        try:
            from src.engines.video_gen_client import ImageToVideoClient
            return ImageToVideoClient()
        except Exception as e:
            self.log.warning("image_to_video_client_init_failed", error=str(e))
            return None
