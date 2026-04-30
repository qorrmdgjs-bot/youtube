"""Helpers for resolving video output paths.

Series mode episodes write video deliverables to <project>/video/ep<N>/ so each
episode is grouped in its own folder. Single-episode (non-series) projects
keep using the flat <project>/video/ layout.
"""

from __future__ import annotations

from pathlib import Path

from src.models import ProjectManifest


def resolve_video_dir(project_dir: Path, manifest: ProjectManifest) -> Path:
    """Return the directory where stage H/L should write video files."""
    ep_num = manifest.brief.episode_number
    if ep_num is not None:
        return project_dir / "video" / f"ep{ep_num}"
    return project_dir / "video"
