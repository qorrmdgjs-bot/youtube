"""Stage G: Image generation for each scene using visual prompts."""

from __future__ import annotations

import os
from pathlib import Path

from src.models import ProjectManifest, Script
from src.pipeline.base_stage import BaseStage


class ImageGenStage(BaseStage):
    name = "g_image_gen"
    dependencies = ["c_visual_prompt"]

    def execute(self, project_dir: Path, manifest: ProjectManifest) -> float:
        script = Script.model_validate_json(
            (project_dir / "script.json").read_text(encoding="utf-8")
        )

        # Choose client based on API availability
        client = self._get_client()
        total_cost = 0.0

        for scene in script.scenes:
            output_path = project_dir / "scenes" / f"scene_{scene.index:03d}.png"

            # Skip if image already exists
            if output_path.exists():
                self.log.info("image_exists_skip", scene=scene.index)
                continue

            prompt = scene.visual_prompt or scene.visual_description or scene.dialogue
            cost = client.generate(
                prompt=prompt,
                output_path=output_path,
                seed=scene.index * 1000,  # Deterministic seed per scene
            )
            total_cost += cost

            self.log.info(
                "image_generated",
                scene=scene.index,
                cost=cost,
            )

        self.log.info("image_gen_complete", scenes=len(script.scenes), cost=total_cost)
        return total_cost

    def _get_client(self):
        """Get image client - real API or placeholder fallback."""
        if os.environ.get("REPLICATE_API_TOKEN"):
            from src.engines.image_client import ImageClient
            return ImageClient()

        self.log.warning("replicate_token_missing, using placeholder images")
        from src.engines.image_client import PlaceholderImageClient
        return PlaceholderImageClient()
