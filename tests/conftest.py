"""Shared test fixtures."""

from __future__ import annotations

import pytest
from pathlib import Path

from src.models import FamilyType, EndingType, ProjectBrief


@pytest.fixture
def sample_brief() -> ProjectBrief:
    return ProjectBrief(
        title="아버지의 낡은 도시락",
        synopsis="매일 새벽 도시락을 싸던 아버지, 그 도시락 안에 숨겨진 편지를 30년 만에 발견한 딸의 이야기",
        family_type=FamilyType.PARENT_SACRIFICE,
        emotional_arc="parent_sacrifice",
        ending_type=EndingType.HEALING,
        target_duration_sec=300,
    )


@pytest.fixture
def tmp_project_dir(tmp_path: Path) -> Path:
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    for subdir in ["scenes", "audio", "subtitles", "video", "thumbnail", "export", ".cache"]:
        (project_dir / subdir).mkdir()
    return project_dir
