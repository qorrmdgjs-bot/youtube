"""Pipeline orchestrator - runs stages in DAG order with resume support."""

from __future__ import annotations

from pathlib import Path

from src.models import ProjectManifest, StageStatus
from src.pipeline.base_stage import BaseStage
from src.project_manager import load_manifest, save_manifest
from src.utils.logging_setup import get_logger

log = get_logger(__name__)

# Stage dependency graph
STAGE_DEPS: dict[str, list[str]] = {
    "a_script_gen": [],
    "b_scene_segment": ["a_script_gen"],
    "c_visual_prompt": ["b_scene_segment"],
    "c2_character_sheet": ["b_scene_segment"],
    "d_tts_gen": ["b_scene_segment"],
    "e_bgm_select": ["b_scene_segment"],
    "f_subtitle_split": ["b_scene_segment"],
    "g_image_gen": ["c_visual_prompt", "c2_character_sheet"],
    # g2_image_to_video 재활성화 — Veo 3.1 핵심 장면만, Ken Burns 혼합 (2026-04-24)
    "g2_image_to_video": ["g_image_gen"],
    "h_video_compose": [
        "d_tts_gen",
        "e_bgm_select",
        "f_subtitle_split",
        "g_image_gen",
        "g2_image_to_video",
    ],
    "i_thumbnail_gen": ["h_video_compose"],
    "j_metadata_gen": ["h_video_compose"],
    "k_monetization_desc": ["h_video_compose"],
    "l_shorts_teaser": ["h_video_compose"],
    "m_export_package": ["i_thumbnail_gen", "j_metadata_gen", "k_monetization_desc", "l_shorts_teaser"],
}


class PipelineOrchestrator:
    """Executes pipeline stages respecting the dependency DAG."""

    def __init__(self) -> None:
        self.stages: dict[str, BaseStage] = {}

    def register_stage(self, stage: BaseStage) -> None:
        """Register a stage implementation."""
        self.stages[stage.name] = stage

    def get_runnable_stages(self, manifest: ProjectManifest) -> list[str]:
        """Get stages that are ready to run (dependencies met, not yet completed)."""
        runnable = []
        for stage_name, deps in STAGE_DEPS.items():
            stage_info = manifest.get_stage(stage_name)
            if stage_info.status in (StageStatus.COMPLETED, StageStatus.RUNNING):
                continue
            if all(manifest.is_stage_completed(d) for d in deps):
                runnable.append(stage_name)
        return runnable

    def run(self, project_dir: Path, stages_to_run: list[str] | None = None) -> ProjectManifest:
        """Run the pipeline for a project.

        Args:
            project_dir: Path to the project directory.
            stages_to_run: Optional list of specific stages to run.
                          If None, runs all pending stages.
        """
        manifest = load_manifest(project_dir)
        log.info("pipeline_start", project_id=manifest.project_id)

        while True:
            runnable = self.get_runnable_stages(manifest)

            if stages_to_run:
                runnable = [s for s in runnable if s in stages_to_run]

            if not runnable:
                break

            # Filter to only registered stages
            runnable = [s for s in runnable if s in self.stages]
            if not runnable:
                break

            # Run stages sequentially (memory safety on 8GB)
            for stage_name in runnable:

                stage = self.stages[stage_name]
                log.info("stage_start", stage=stage_name)
                manifest.mark_stage_running(stage_name)
                save_manifest(project_dir, manifest)

                try:
                    cost = stage.execute(project_dir, manifest)
                    manifest.mark_stage_completed(stage_name, cost_usd=cost)
                    log.info("stage_completed", stage=stage_name, cost_usd=cost)
                except Exception as e:
                    manifest.mark_stage_failed(stage_name, str(e))
                    log.error("stage_failed", stage=stage_name, error=str(e))
                    save_manifest(project_dir, manifest)
                    raise

                save_manifest(project_dir, manifest)

        log.info(
            "pipeline_done",
            project_id=manifest.project_id,
            total_cost=manifest.total_cost_usd,
            complete=manifest.is_complete,
        )
        return manifest
