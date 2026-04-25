"""Stage G: Image generation for each scene using visual prompts.

Two operating modes:
  - **Series mode**: when manifest.brief has series_id set, use Nano Banana 2
    with character reference images from config/character_templates.yaml so the
    same person stays consistent across every scene.
  - **Single-episode mode**: fall back to FLUX.1 Pro (text-only).

If REPLICATE_API_TOKEN is missing, both modes fall through to the placeholder.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from src.models import ProjectManifest, Script
from src.pipeline.base_stage import BaseStage

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class ImageGenStage(BaseStage):
    name = "g_image_gen"
    dependencies = ["c_visual_prompt"]

    def execute(self, project_dir: Path, manifest: ProjectManifest) -> float:
        script = Script.model_validate_json(
            (project_dir / "script.json").read_text(encoding="utf-8")
        )

        is_series_mode = manifest.brief.series_id is not None
        reference_images: list[Path] = []
        if is_series_mode:
            reference_images = self._resolve_character_refs(manifest)
            self.log.info(
                "series_mode_refs",
                episode=manifest.brief.episode_number,
                refs=len(reference_images),
            )

        client = self._get_client(use_nano_banana=is_series_mode)
        # Only NanoBananaClient accepts reference_images; FLUX/placeholder don't.
        client_accepts_refs = client.__class__.__name__ == "NanoBananaClient"
        total_cost = 0.0

        # Generate ONE image per unique image_key (sibling sub-scenes share an image,
        # which Stage H then varies via Ken Burns to create movement instead of cuts).
        # If image_key is None (legacy projects, pre-2026-04-26), fall back to scene.index.
        for scene in script.scenes:
            key = scene.image_key if scene.image_key is not None else scene.index
            output_path = project_dir / "scenes" / f"scene_{key:03d}.png"
            if output_path.exists():
                self.log.info("image_exists_skip", scene=scene.index, image_key=key)
                continue

            prompt = scene.visual_prompt or scene.visual_description or scene.dialogue

            kwargs: dict = {"prompt": prompt, "output_path": output_path, "seed": key * 1000}
            if client_accepts_refs and reference_images:
                kwargs["reference_images"] = reference_images

            cost = client.generate(**kwargs)
            total_cost += cost

            self.log.info("image_generated", scene=scene.index, image_key=key, cost=cost)

        self.log.info("image_gen_complete", scenes=len(script.scenes), cost=total_cost)
        return total_cost

    def _resolve_character_refs(self, manifest: ProjectManifest) -> list[Path]:
        """Look up image paths for every character in the episode.

        manifest.brief.characters_in_episode = {role: stage} (e.g., {'son': 'teen'}).
        config/character_templates.yaml stores the actual image path per (role, stage).
        """
        chars = manifest.brief.characters_in_episode or {}
        if not chars:
            return []

        templates_path = PROJECT_ROOT / "config" / "character_templates.yaml"
        with open(templates_path, encoding="utf-8") as f:
            templates = yaml.safe_load(f)

        family_type = manifest.brief.family_type.value
        family_data = templates.get(family_type, {})
        character_block = family_data.get("characters", {})

        refs: list[Path] = []
        for role, stage in chars.items():
            entry = character_block.get(role)
            if not entry:
                self.log.warning("character_role_missing", role=role, family_type=family_type)
                continue

            # Multi-stage form: entry has 'stages' dict
            if "stages" in entry:
                stage_entry = entry["stages"].get(stage)
                if not stage_entry:
                    self.log.warning("character_stage_missing", role=role, stage=stage)
                    continue
                image_path = PROJECT_ROOT / stage_entry["image"]
            # Single-stage form: entry has 'image' directly
            else:
                image_path = PROJECT_ROOT / entry["image"]

            if image_path.exists():
                refs.append(image_path)
            else:
                self.log.warning("character_image_missing_on_disk", path=str(image_path))

        return refs

    def _get_client(self, use_nano_banana: bool):
        """Pick the image client. Returns placeholder if no Replicate token."""
        if not os.environ.get("REPLICATE_API_TOKEN"):
            self.log.warning("replicate_token_missing, using placeholder images")
            from src.engines.image_client import PlaceholderImageClient
            return PlaceholderImageClient()

        if use_nano_banana:
            from src.engines.image_client import NanoBananaClient
            return NanoBananaClient()

        from src.engines.image_client import ImageClient
        return ImageClient()
