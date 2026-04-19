"""Tests for Pydantic data models."""

import pytest
from src.models import (
    EndingType,
    FamilyType,
    ProjectBrief,
    ProjectManifest,
    Scene,
    Script,
    StageStatus,
    TransitionType,
)


def test_project_brief_valid(sample_brief):
    assert sample_brief.title == "아버지의 낡은 도시락"
    assert sample_brief.family_type == FamilyType.PARENT_SACRIFICE
    assert sample_brief.target_duration_sec == 300


def test_project_brief_duration_limits():
    with pytest.raises(Exception):
        ProjectBrief(
            title="test",
            synopsis="test synopsis here",
            family_type=FamilyType.PARENT_SACRIFICE,
            emotional_arc="parent_sacrifice",
            target_duration_sec=100,  # too short
        )


def test_scene_model():
    scene = Scene(
        index=0,
        phase="hook",
        dialogue="그날 아버지의 서랍을 열었습니다.",
        emotion="curiosity",
        duration_sec=15.0,
        transition=TransitionType.FADE_BLACK,
    )
    assert scene.has_silence_before is False
    assert scene.visual_prompt is None


def test_script_auto_duration():
    script = Script(
        title="테스트",
        scenes=[
            Scene(index=0, phase="hook", dialogue="첫 장면", emotion="sad", duration_sec=15.0),
            Scene(index=1, phase="conflict", dialogue="두번째", emotion="tense", duration_sec=30.0),
        ],
    )
    assert script.total_duration_sec == 45.0
    assert "첫 장면" in script.narration_text


def test_manifest_stage_tracking(sample_brief):
    manifest = ProjectManifest(project_id="test_001", brief=sample_brief)

    manifest.mark_stage_running("a_script_gen")
    assert manifest.get_stage("a_script_gen").status == StageStatus.RUNNING

    manifest.mark_stage_completed("a_script_gen", cost_usd=0.15)
    assert manifest.is_stage_completed("a_script_gen")
    assert manifest.total_cost_usd == 0.15

    manifest.mark_stage_failed("b_scene_segment", "test error")
    assert manifest.get_stage("b_scene_segment").status == StageStatus.FAILED
    assert not manifest.is_complete
