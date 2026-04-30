"""Stage G: Image generation for each scene using visual prompts.

Uses engine_factory to pick the image client (Gemini Nano Banana 2 → FLUX → placeholder).
Reference images come from manifest.character_refs (populated by stage C2).
Sub-scenes that share an image_key share a single generated image; stage H then
varies them via Ken Burns to create movement instead of cuts.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from src.engines.engine_factory import get_image_client
from src.engines.llm_client import PROJECT_ROOT
from src.models import ProjectManifest, Script
from src.pipeline.base_stage import BaseStage


class ImageGenStage(BaseStage):
    name = "g_image_gen"
    dependencies = ["c_visual_prompt", "c2_character_sheet"]

    def execute(self, project_dir: Path, manifest: ProjectManifest) -> float:
        script = Script.model_validate_json(
            (project_dir / "script.json").read_text(encoding="utf-8")
        )

        with open(PROJECT_ROOT / "config" / "settings.yaml", encoding="utf-8") as f:
            settings = yaml.safe_load(f)

        client = get_image_client(settings)
        total_cost = 0.0

        ref_image_paths: list[Path] = []
        for paths in manifest.character_refs.values():
            ref_image_paths.extend(Path(p) for p in paths)

        for scene in script.scenes:
            key = scene.image_key if scene.image_key is not None else scene.index
            output_path = project_dir / "scenes" / f"scene_{key:03d}.png"

            if output_path.exists():
                self.log.info("image_exists_skip", scene=scene.index, image_key=key)
                continue

            prompt = scene.visual_prompt or scene.visual_description or scene.dialogue
            cost = client.generate(
                prompt=prompt,
                output_path=output_path,
                ref_images=ref_image_paths or None,
                seed=key * 1000,
            )
            total_cost += cost

            self.log.info("image_generated", scene=scene.index, image_key=key, cost=cost)

        self.log.info("image_gen_complete", scenes=len(script.scenes), cost=total_cost)
        return total_cost
