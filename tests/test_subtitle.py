"""Tests for subtitle generation stage."""

from pathlib import Path

from src.models import ProjectManifest, Script, Scene, ProjectBrief, FamilyType
from src.pipeline.f_subtitle_split import SubtitleSplitStage


def _make_script() -> Script:
    return Script(
        title="테스트",
        scenes=[
            Scene(
                index=0,
                phase="hook",
                dialogue="그날 아버지의 낡은 서랍을 열었습니다.",
                emotion="curiosity",
                duration_sec=15.0,
            ),
            Scene(
                index=1,
                phase="climax",
                dialogue="아버지는 아무 말 없이 눈물을 흘리셨습니다.",
                emotion="deep_sadness",
                duration_sec=20.0,
                has_silence_before=True,
                silence_duration_sec=1.5,
            ),
        ],
    )


def test_srt_time_format():
    stage = SubtitleSplitStage()
    assert stage._format_srt_time(0.0) == "00:00:00,000"
    assert stage._format_srt_time(61.5) == "00:01:01,500"
    assert stage._format_srt_time(3661.123) == "01:01:01,123"


def test_subtitle_generation(tmp_project_dir):
    script = _make_script()
    (tmp_project_dir / "script.json").write_text(
        script.model_dump_json(indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    brief = ProjectBrief(
        title="test",
        synopsis="test synopsis text",
        family_type=FamilyType.PARENT_SACRIFICE,
        emotional_arc="parent_sacrifice",
    )
    manifest = ProjectManifest(project_id="test", brief=brief)

    stage = SubtitleSplitStage()
    cost = stage.execute(tmp_project_dir, manifest)

    assert cost == 0.0

    srt_path = tmp_project_dir / "subtitles" / "raw.srt"
    assert srt_path.exists()

    content = srt_path.read_text(encoding="utf-8")
    assert "00:00:00,000" in content
    assert len(content) > 0


def test_split_dialogue_to_chunks():
    stage = SubtitleSplitStage()
    chunks = stage._split_dialogue_to_chunks(
        "아버지는 매일 새벽 네 시에 일어나셨습니다. 도시락을 싸시는 소리가 들렸습니다.",
        max_chars=18,
    )
    assert len(chunks) >= 2
