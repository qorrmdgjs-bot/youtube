"""Pydantic data models for the YouTube automation pipeline."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class FamilyType(str, Enum):
    PARENT_SACRIFICE = "parent_sacrifice"
    SIBLING = "sibling_reconciliation"
    GRANDPARENT = "grandparent_memory"
    FATHER_DAUGHTER = "father_daughter_wedding"
    LATE_REALIZATION = "late_realization"
    REMARRIAGE = "remarriage_parent"
    INLAW = "inlaw_relationship"
    GRANDCHILD = "grandchild_love"
    HOLIDAY = "holiday_reunion"
    CAREER_PARENT = "career_sacrifice_parent"
    IMMIGRANT = "immigrant_parent"
    COUPLE = "couple_growing_old"
    MODERN_THREE_GEN = "modern_three_gen"  # 현대 3세대 가족 (조부모+부모+자녀)


class EndingType(str, Enum):
    HEALING = "healing"
    BITTERSWEET = "bittersweet"
    HOPEFUL = "hopeful"
    CATHARTIC = "cathartic"


class TransitionType(str, Enum):
    CROSSFADE = "crossfade"
    FADE_BLACK = "fade_black"
    CUT = "cut"
    SLOW_ZOOM = "slow_zoom"


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# --- Input Models ---


class ProjectBrief(BaseModel):
    """Input brief for a new video project."""

    title: str = Field(min_length=1, max_length=100)
    synopsis: str = Field(min_length=10, max_length=1000)
    family_type: FamilyType
    emotional_arc: str = Field(description="Key from emotional_arcs.yaml")
    ending_type: EndingType = EndingType.HEALING
    target_duration_sec: int = Field(default=480, ge=60, le=720)
    voice_gender: Literal["female", "male"] = "female"
    custom_keywords: list[str] = Field(default_factory=list)


# --- Script Models ---


class Scene(BaseModel):
    """A single scene within the video script."""

    index: int = Field(ge=0)
    phase: str  # hook, conflict, layering, reveal, climax, healing, afterglow
    dialogue: str
    emotion: str
    duration_sec: float = Field(ge=3.0)
    visual_prompt: str | None = None
    visual_description: str | None = None
    transition: TransitionType = TransitionType.CROSSFADE
    has_silence_before: bool = False
    silence_duration_sec: float = 0.0
    use_ai_video: bool = False  # If True, G2 stage generates AI video clip (Veo)
    motion_prompt: str | None = None  # Optional explicit motion hint for image-to-video


class Script(BaseModel):
    """Complete script for a video."""

    title: str
    scenes: list[Scene]
    total_duration_sec: float = 0.0
    narration_text: str = ""

    def model_post_init(self, __context: object) -> None:
        if not self.total_duration_sec and self.scenes:
            self.total_duration_sec = sum(s.duration_sec for s in self.scenes)
        if not self.narration_text and self.scenes:
            self.narration_text = "\n\n".join(s.dialogue for s in self.scenes)


# --- Pipeline State Models ---


class StageInfo(BaseModel):
    """Status info for a single pipeline stage."""

    status: StageStatus = StageStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    cost_usd: float = 0.0


class ProjectManifest(BaseModel):
    """Tracks overall project state and pipeline progress."""

    project_id: str
    created_at: datetime = Field(default_factory=datetime.now)
    brief: ProjectBrief
    stages: dict[str, StageInfo] = Field(default_factory=dict)
    total_cost_usd: float = 0.0
    # role → ordered list of character sheet image paths (front/profile/fullbody)
    character_refs: dict[str, list[str]] = Field(default_factory=dict)

    def get_stage(self, name: str) -> StageInfo:
        if name not in self.stages:
            self.stages[name] = StageInfo()
        return self.stages[name]

    def mark_stage_running(self, name: str) -> None:
        stage = self.get_stage(name)
        stage.status = StageStatus.RUNNING
        stage.started_at = datetime.now()

    def mark_stage_completed(self, name: str, cost_usd: float = 0.0) -> None:
        stage = self.get_stage(name)
        stage.status = StageStatus.COMPLETED
        stage.completed_at = datetime.now()
        stage.cost_usd = cost_usd
        self.total_cost_usd = sum(s.cost_usd for s in self.stages.values())

    def mark_stage_failed(self, name: str, error: str) -> None:
        stage = self.get_stage(name)
        stage.status = StageStatus.FAILED
        stage.error = error

    def is_stage_completed(self, name: str) -> bool:
        return self.stages.get(name, StageInfo()).status == StageStatus.COMPLETED

    @property
    def is_complete(self) -> bool:
        if not self.stages:
            return False
        return all(
            s.status in (StageStatus.COMPLETED, StageStatus.SKIPPED)
            for s in self.stages.values()
        )


# --- Export Models ---


class VideoMetadata(BaseModel):
    """YouTube upload metadata."""

    title: str = Field(max_length=150)
    description: str
    tags: list[str] = Field(default_factory=list, max_length=25)
    category_id: str = "22"  # People & Blogs
    language: str = "ko"
    privacy_status: Literal["public", "unlisted", "private"] = "private"


class ExportManifest(BaseModel):
    """Final export package manifest."""

    project_id: str
    video_path: Path
    shorts_path: Path | None = None
    thumbnail_path: Path
    metadata: VideoMetadata
    description_path: Path
    total_cost_usd: float
    created_at: datetime = Field(default_factory=datetime.now)
