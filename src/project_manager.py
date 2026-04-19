"""Project directory management."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from src.models import ProjectBrief, ProjectManifest
from src.utils.logging_setup import get_logger

log = get_logger(__name__)

# Pipeline stages in execution order
ALL_STAGES = [
    "a_script_gen",
    "b_scene_segment",
    "c_visual_prompt",
    "d_tts_gen",
    "e_bgm_select",
    "f_subtitle_split",
    "g_image_gen",
    "g2_image_to_video",
    "h_video_compose",
    "i_thumbnail_gen",
    "j_metadata_gen",
    "k_monetization_desc",
    "l_shorts_teaser",
    "m_export_package",
]


def generate_project_id() -> str:
    """Generate a short unique project ID."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_uuid = uuid.uuid4().hex[:6]
    return f"{ts}_{short_uuid}"


def create_project(base_dir: str, brief: ProjectBrief) -> tuple[Path, ProjectManifest]:
    """Create a new project directory with initial manifest.

    Returns:
        Tuple of (project_dir, manifest).
    """
    project_id = generate_project_id()
    project_dir = Path(base_dir) / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectories
    for subdir in ["scenes", "audio", "subtitles", "video", "thumbnail", "export", ".cache"]:
        (project_dir / subdir).mkdir(exist_ok=True)

    # Create manifest
    manifest = ProjectManifest(
        project_id=project_id,
        brief=brief,
    )

    # Save input brief
    (project_dir / "input.json").write_text(
        brief.model_dump_json(indent=2),
        encoding="utf-8",
    )

    # Save manifest
    save_manifest(project_dir, manifest)

    log.info("project_created", project_id=project_id, title=brief.title)
    return project_dir, manifest


def load_manifest(project_dir: Path) -> ProjectManifest:
    """Load project manifest from directory."""
    manifest_path = project_dir / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return ProjectManifest.model_validate(data)


def save_manifest(project_dir: Path, manifest: ProjectManifest) -> None:
    """Save project manifest to directory."""
    manifest_path = project_dir / "manifest.json"
    manifest_path.write_text(
        manifest.model_dump_json(indent=2),
        encoding="utf-8",
    )


def list_projects(base_dir: str) -> list[tuple[Path, ProjectManifest]]:
    """List all projects with their manifests."""
    base = Path(base_dir)
    if not base.exists():
        return []

    projects = []
    for project_dir in sorted(base.iterdir()):
        if not project_dir.is_dir():
            continue
        manifest_path = project_dir / "manifest.json"
        if manifest_path.exists():
            manifest = load_manifest(project_dir)
            projects.append((project_dir, manifest))
    return projects
