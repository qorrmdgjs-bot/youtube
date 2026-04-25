"""Stage B: Scene segmentation - enriches script scenes with detailed metadata.

Splits long scenes into sub-scenes (one image per ~12-15 seconds of narration)
so that the video has enough visual variety.
"""

from __future__ import annotations

import re
from pathlib import Path

from src.models import ProjectManifest, Script, Scene
from src.pipeline.base_stage import BaseStage
from src.utils.hangul_utils import estimate_reading_duration


# Maximum narration seconds before a scene should be split into sub-scenes
MAX_SCENE_DURATION_FOR_SINGLE_IMAGE = 15.0


class SceneSegmentStage(BaseStage):
    name = "b_scene_segment"
    dependencies = ["a_script_gen"]

    def execute(self, project_dir: Path, manifest: ProjectManifest) -> float:
        script_path = project_dir / "script.json"
        script = Script.model_validate_json(script_path.read_text(encoding="utf-8"))

        scenes_dir = project_dir / "scenes"
        scenes_dir.mkdir(exist_ok=True)

        expanded_scenes: list[Scene] = []
        new_index = 0

        for scene in script.scenes:
            reading_time = estimate_reading_duration(scene.dialogue)
            min_duration = max(reading_time + 1.0, 3.0)

            if scene.duration_sec < min_duration:
                self.log.info(
                    "duration_adjusted",
                    scene=scene.index,
                    original=scene.duration_sec,
                    adjusted=min_duration,
                )
                scene.duration_sec = round(min_duration, 1)

            # Split long scenes into sub-scenes for narration timing.
            # All sub-scenes share image_key (= first sub's index) so stage G generates
            # ONE image for the group; ken_burns then varies camera movement per sub-scene.
            if scene.duration_sec > MAX_SCENE_DURATION_FOR_SINGLE_IMAGE:
                sub_scenes = self._split_scene(scene, new_index)
                group_key = new_index  # parent group identifier
                for sub in sub_scenes:
                    sub.image_key = group_key
                    if sub.phase == "climax" and not sub.has_silence_before:
                        sub.has_silence_before = True
                        sub.silence_duration_sec = 1.5
                    expanded_scenes.append(sub)
                    new_index += 1
                self.log.info(
                    "scene_split",
                    original_index=scene.index,
                    sub_count=len(sub_scenes),
                    image_key=group_key,
                )
            else:
                scene.index = new_index
                scene.image_key = new_index  # standalone scene is its own group
                if scene.phase == "climax" and not scene.has_silence_before:
                    scene.has_silence_before = True
                    scene.silence_duration_sec = 1.5
                expanded_scenes.append(scene)
                new_index += 1

        # Save individual scene files
        for s in expanded_scenes:
            scene_file = scenes_dir / f"scene_{s.index:03d}.json"
            scene_file.write_text(
                s.model_dump_json(indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        script.scenes = expanded_scenes
        script.total_duration_sec = sum(
            s.duration_sec + s.silence_duration_sec for s in expanded_scenes
        )

        script_path.write_text(
            script.model_dump_json(indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        self.log.info(
            "scenes_segmented",
            count=len(expanded_scenes),
            total_duration=script.total_duration_sec,
        )

        return 0.0

    def _split_scene(self, scene: Scene, start_index: int) -> list[Scene]:
        """Split a long scene into sub-scenes by sentences."""
        sentences = re.split(r"(?<=[.!?])\s+", scene.dialogue.strip())
        sentences = [s for s in sentences if s.strip()]

        if len(sentences) <= 1:
            scene.index = start_index
            return [scene]

        # Group sentences so each sub-scene has ~12-15 seconds of narration
        groups: list[list[str]] = []
        current_group: list[str] = []
        current_duration = 0.0

        for sent in sentences:
            sent_duration = estimate_reading_duration(sent)
            if current_duration + sent_duration > MAX_SCENE_DURATION_FOR_SINGLE_IMAGE and current_group:
                groups.append(current_group)
                current_group = [sent]
                current_duration = sent_duration
            else:
                current_group.append(sent)
                current_duration += sent_duration

        if current_group:
            groups.append(current_group)

        sub_scenes: list[Scene] = []
        for i, group in enumerate(groups):
            text = " ".join(group)
            duration = estimate_reading_duration(text) + 1.0

            sub = Scene(
                index=start_index + i,
                phase=scene.phase,
                dialogue=text,
                emotion=scene.emotion,
                duration_sec=round(max(duration, 5.0), 1),
                visual_description=scene.visual_description,
                visual_prompt=None,  # Will be regenerated in stage C
                transition=scene.transition,
                has_silence_before=scene.has_silence_before if i == 0 else False,
                silence_duration_sec=scene.silence_duration_sec if i == 0 else 0.0,
            )
            sub_scenes.append(sub)

        return sub_scenes
