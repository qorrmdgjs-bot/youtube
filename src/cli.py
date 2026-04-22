"""CLI entry point for the YouTube automation pipeline."""

from __future__ import annotations

from pathlib import Path

import typer
from dotenv import load_dotenv

from src.models import EndingType, FamilyType, ProjectBrief, StageStatus
from src.project_manager import ALL_STAGES, create_project, list_projects, load_manifest
from src.orchestrator import PipelineOrchestrator
from src.utils.logging_setup import setup_logging

load_dotenv()

app = typer.Typer(
    name="yt",
    help="YouTube 장편 자동화 파이프라인",
    no_args_is_help=True,
)


def _build_orchestrator() -> PipelineOrchestrator:
    """Build orchestrator with all registered stages."""
    from src.pipeline.a_script_gen import ScriptGenStage
    from src.pipeline.b_scene_segment import SceneSegmentStage
    from src.pipeline.c_visual_prompt import VisualPromptStage
    from src.pipeline.d_tts_gen import TTSGenStage
    from src.pipeline.e_bgm_select import BGMSelectStage
    from src.pipeline.f_subtitle_split import SubtitleSplitStage
    from src.pipeline.g_image_gen import ImageGenStage
    # g2_image_to_video 제거 — Ken Burns 효과로 대체 (비용 절감)
    from src.pipeline.h_video_compose import VideoComposeStage
    from src.pipeline.i_thumbnail_gen import ThumbnailGenStage
    from src.pipeline.j_metadata_gen import MetadataGenStage
    from src.pipeline.k_monetization_desc import MonetizationDescStage
    from src.pipeline.l_shorts_teaser import ShortsTeaserStage
    from src.pipeline.m_export_package import ExportPackageStage

    orchestrator = PipelineOrchestrator()
    for stage_cls in [
        ScriptGenStage, SceneSegmentStage, VisualPromptStage,
        TTSGenStage, BGMSelectStage, SubtitleSplitStage,
        ImageGenStage, VideoComposeStage,
        ThumbnailGenStage, MetadataGenStage, MonetizationDescStage,
        ShortsTeaserStage, ExportPackageStage,
    ]:
        orchestrator.register_stage(stage_cls())
    return orchestrator


@app.command()
def new(
    title: str = typer.Option(..., "--title", "-t", help="영상 제목"),
    synopsis: str = typer.Option(..., "--synopsis", "-s", help="줄거리 요약"),
    family_type: FamilyType = typer.Option(
        FamilyType.PARENT_SACRIFICE, "--type", "-T", help="가족 유형"
    ),
    emotional_arc: str = typer.Option("parent_sacrifice", "--arc", "-a", help="감정 아크 키"),
    ending: EndingType = typer.Option(EndingType.HEALING, "--ending", "-e", help="엔딩 유형"),
    duration: int = typer.Option(300, "--duration", "-d", help="목표 길이(초)"),
    voice: str = typer.Option("male", "--voice", "-v", help="음성 성별 (female/male)"),
    base_dir: str = typer.Option("projects", "--dir", help="프로젝트 베이스 디렉토리"),
) -> None:
    """새 영상 프로젝트 생성."""
    setup_logging()

    brief = ProjectBrief(
        title=title,
        synopsis=synopsis,
        family_type=family_type,
        emotional_arc=emotional_arc,
        ending_type=ending,
        target_duration_sec=duration,
        voice_gender=voice,
    )

    project_dir, manifest = create_project(base_dir, brief)
    typer.echo(f"프로젝트 생성 완료: {project_dir}")
    typer.echo(f"  ID: {manifest.project_id}")
    typer.echo(f"  제목: {brief.title}")
    typer.echo(f"  유형: {brief.family_type.value}")
    typer.echo(f"  길이: {brief.target_duration_sec}초")


@app.command()
def run(
    project_dir: str = typer.Argument(..., help="프로젝트 디렉토리 경로"),
    stage: str = typer.Option(None, "--stage", "-s", help="특정 스테이지만 실행"),
) -> None:
    """프로젝트 파이프라인 실행."""
    setup_logging()

    path = Path(project_dir)
    if not path.exists():
        typer.echo(f"프로젝트를 찾을 수 없습니다: {path}", err=True)
        raise typer.Exit(1)

    orchestrator = _build_orchestrator()
    stages_to_run = [stage] if stage else None
    manifest = orchestrator.run(path, stages_to_run)

    typer.echo(f"파이프라인 완료. 총 비용: ${manifest.total_cost_usd:.2f}")


@app.command()
def status(
    base_dir: str = typer.Option("projects", "--dir", help="프로젝트 베이스 디렉토리"),
) -> None:
    """모든 프로젝트 상태 조회."""
    setup_logging()

    projects = list_projects(base_dir)
    if not projects:
        typer.echo("프로젝트가 없습니다.")
        return

    for project_dir, manifest in projects:
        completed = sum(1 for s in manifest.stages.values() if s.status == StageStatus.COMPLETED)
        total = len(ALL_STAGES)
        failed = sum(1 for s in manifest.stages.values() if s.status == StageStatus.FAILED)

        status_icon = "✅" if manifest.is_complete else ("❌" if failed > 0 else "⏳")
        typer.echo(f"{status_icon} {manifest.project_id} | {manifest.brief.title}")
        typer.echo(f"   진행: {completed}/{total} | 비용: ${manifest.total_cost_usd:.2f}")
        if failed > 0:
            failed_stages = [n for n, s in manifest.stages.items() if s.status == StageStatus.FAILED]
            typer.echo(f"   실패: {', '.join(failed_stages)}")
        typer.echo()


@app.command()
def resume(
    project_dir: str = typer.Argument(..., help="프로젝트 디렉토리 경로"),
) -> None:
    """실패한 스테이지부터 파이프라인 재개."""
    setup_logging()

    path = Path(project_dir)
    if not path.exists():
        typer.echo(f"프로젝트를 찾을 수 없습니다: {path}", err=True)
        raise typer.Exit(1)

    manifest = load_manifest(path)

    # Reset failed stages to pending
    for stage_name, stage_info in manifest.stages.items():
        if stage_info.status == StageStatus.FAILED:
            stage_info.status = StageStatus.PENDING
            stage_info.error = None

    from src.project_manager import save_manifest
    save_manifest(path, manifest)

    orchestrator = _build_orchestrator()
    manifest = orchestrator.run(path)
    typer.echo(f"파이프라인 재개 완료. 총 비용: ${manifest.total_cost_usd:.2f}")


@app.command()
def batch(
    queue_file: str = typer.Argument("batch/queue.json", help="배치 큐 JSON 파일 경로"),
    base_dir: str = typer.Option("projects", "--dir", help="프로젝트 베이스 디렉토리"),
) -> None:
    """배치 큐 파일에서 여러 프로젝트를 순차 처리."""
    import json

    setup_logging()

    queue_path = Path(queue_file)
    if not queue_path.exists():
        typer.echo(f"큐 파일을 찾을 수 없습니다: {queue_path}", err=True)
        raise typer.Exit(1)

    briefs_data = json.loads(queue_path.read_text(encoding="utf-8"))
    if not isinstance(briefs_data, list):
        typer.echo("큐 파일은 브리프 배열이어야 합니다.", err=True)
        raise typer.Exit(1)

    typer.echo(f"배치 처리 시작: {len(briefs_data)}개 프로젝트")
    orchestrator = _build_orchestrator()

    results: list[dict] = []
    for i, brief_data in enumerate(briefs_data):
        typer.echo(f"\n[{i + 1}/{len(briefs_data)}] {brief_data.get('title', '제목 없음')}")
        try:
            brief = ProjectBrief.model_validate(brief_data)
            project_dir, manifest = create_project(base_dir, brief)
            manifest = orchestrator.run(project_dir)
            results.append({
                "project_id": manifest.project_id,
                "title": brief.title,
                "status": "completed" if manifest.is_complete else "partial",
                "cost": manifest.total_cost_usd,
            })
            typer.echo(f"  완료: ${manifest.total_cost_usd:.2f}")
        except Exception as e:
            results.append({
                "title": brief_data.get("title", "?"),
                "status": "failed",
                "error": str(e),
            })
            typer.echo(f"  실패: {e}", err=True)

    # Summary
    completed = sum(1 for r in results if r["status"] == "completed")
    total_cost = sum(r.get("cost", 0) for r in results)
    typer.echo(f"\n배치 완료: {completed}/{len(results)} 성공, 총 비용: ${total_cost:.2f}")


@app.command()
def cost(
    base_dir: str = typer.Option("projects", "--dir", help="프로젝트 베이스 디렉토리"),
) -> None:
    """전체 프로젝트 비용 리포트."""
    setup_logging()

    projects = list_projects(base_dir)
    if not projects:
        typer.echo("프로젝트가 없습니다.")
        return

    total_cost = 0.0
    typer.echo("프로젝트별 비용 리포트:")
    typer.echo("-" * 60)

    for project_dir, manifest in projects:
        typer.echo(f"{manifest.project_id} | {manifest.brief.title}")
        for stage_name, stage_info in manifest.stages.items():
            if stage_info.cost_usd > 0:
                typer.echo(f"  {stage_name}: ${stage_info.cost_usd:.4f}")
        typer.echo(f"  합계: ${manifest.total_cost_usd:.2f}")
        total_cost += manifest.total_cost_usd

    typer.echo("-" * 60)
    typer.echo(f"전체 합계: ${total_cost:.2f}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
