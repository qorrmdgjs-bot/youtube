"""YouTube 자동화 파이프라인 대시보드."""

import json
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from src.models import EndingType, FamilyType, ProjectBrief, StageStatus
from src.project_manager import ALL_STAGES, create_project, list_projects, load_manifest, save_manifest
from src.orchestrator import PipelineOrchestrator, STAGE_DEPS
from src.utils.logging_setup import setup_logging

setup_logging()

# --- Page Config ---
st.set_page_config(
    page_title="가족이야기 - YouTube 자동화",
    page_icon="🎬",
    layout="wide",
)

# --- Constants ---
FAMILY_TYPE_LABELS = {
    FamilyType.PARENT_SACRIFICE: "👨‍👧 부모의 희생",
    FamilyType.SIBLING: "👫 형제 화해",
    FamilyType.GRANDPARENT: "👵 할머니의 기억",
    FamilyType.FATHER_DAUGHTER: "👰 아버지와 딸의 결혼식",
    FamilyType.LATE_REALIZATION: "💭 늦은 깨달음",
    FamilyType.REMARRIAGE: "💑 재혼 부모의 사랑",
    FamilyType.INLAW: "🏠 며느리와 시어머니",
    FamilyType.GRANDCHILD: "👴 손주와 할아버지",
    FamilyType.HOLIDAY: "🏮 명절의 재회",
    FamilyType.CAREER_PARENT: "💼 일하는 부모의 미안함",
    FamilyType.IMMIGRANT: "✈️ 이민 부모의 눈물",
    FamilyType.COUPLE: "💕 함께 늙어가는 부부",
}

ENDING_TYPE_LABELS = {
    EndingType.HEALING: "🌿 치유",
    EndingType.BITTERSWEET: "🌅 씁쓸달콤",
    EndingType.HOPEFUL: "🌈 희망",
    EndingType.CATHARTIC: "😭 카타르시스",
}

STAGE_LABELS = {
    "a_script_gen": "📝 스크립트 생성",
    "b_scene_segment": "🎬 장면 분할",
    "c_visual_prompt": "🖼️ 시각 프롬프트",
    "c2_character_sheet": "🧑‍🎨 캐릭터 시트",
    "d_tts_gen": "🔊 음성 생성",
    "f_subtitle_split": "💬 자막 생성",
    "g_image_gen": "🎨 이미지 생성",
    "h_video_compose": "🎥 영상 합성",
    "i_thumbnail_gen": "🖼️ 썸네일 생성",
    "j_metadata_gen": "📋 메타데이터",
    "k_monetization_desc": "💰 수익화 설명문",
    "l_shorts_teaser": "📱 쇼츠 생성",
    "m_export_package": "📦 최종 패키징",
}

# Family type to emotional arc key mapping
FAMILY_ARC_MAP = {
    FamilyType.PARENT_SACRIFICE: "parent_sacrifice",
    FamilyType.SIBLING: "sibling_reconciliation",
    FamilyType.GRANDPARENT: "grandparent_memory",
    FamilyType.FATHER_DAUGHTER: "father_daughter_wedding",
    FamilyType.LATE_REALIZATION: "late_realization",
    FamilyType.REMARRIAGE: "remarriage_parent",
    FamilyType.INLAW: "inlaw_relationship",
    FamilyType.GRANDCHILD: "grandchild_love",
    FamilyType.HOLIDAY: "holiday_reunion",
    FamilyType.CAREER_PARENT: "career_sacrifice_parent",
    FamilyType.IMMIGRANT: "immigrant_parent",
    FamilyType.COUPLE: "couple_growing_old",
}


def build_orchestrator() -> PipelineOrchestrator:
    from src.pipeline.a_script_gen import ScriptGenStage
    from src.pipeline.b_scene_segment import SceneSegmentStage
    from src.pipeline.c_visual_prompt import VisualPromptStage
    from src.pipeline.c2_character_sheet import CharacterSheetStage
    from src.pipeline.d_tts_gen import TTSGenStage
    from src.pipeline.f_subtitle_split import SubtitleSplitStage
    from src.pipeline.g_image_gen import ImageGenStage
    from src.pipeline.h_video_compose import VideoComposeStage
    from src.pipeline.i_thumbnail_gen import ThumbnailGenStage
    from src.pipeline.j_metadata_gen import MetadataGenStage
    from src.pipeline.k_monetization_desc import MonetizationDescStage
    from src.pipeline.l_shorts_teaser import ShortsTeaserStage
    from src.pipeline.m_export_package import ExportPackageStage

    orch = PipelineOrchestrator()
    for cls in [
        ScriptGenStage, SceneSegmentStage, VisualPromptStage, CharacterSheetStage,
        TTSGenStage, SubtitleSplitStage,
        ImageGenStage, VideoComposeStage,
        ThumbnailGenStage, MetadataGenStage, MonetizationDescStage,
        ShortsTeaserStage, ExportPackageStage,
    ]:
        orch.register_stage(cls())
    return orch


def _show_results(project_dir: Path, manifest, key_prefix: str = "new") -> None:
    """Show results with download buttons for all generated files."""
    video_path = project_dir / "video" / "final.mp4"
    thumb_path = project_dir / "thumbnail" / "thumb_1080.png"
    metadata_path = project_dir / "export" / "metadata.json"
    desc_path = project_dir / "export" / "description.txt"
    script_path = project_dir / "script.json"
    shorts_manifest_path = project_dir / "video" / "shorts_manifest.json"

    # Video + Thumbnail preview
    col_a, col_b = st.columns(2)
    with col_a:
        if video_path.exists():
            st.video(str(video_path))
    with col_b:
        if thumb_path.exists():
            st.image(str(thumb_path), caption="생성된 썸네일")

    # Download buttons
    st.markdown("### 다운로드")
    dl_cols = st.columns(4)

    with dl_cols[0]:
        if video_path.exists():
            st.download_button(
                "🎬 본편 다운로드",
                data=video_path.read_bytes(),
                file_name=f"{manifest.brief.title}_본편.mp4",
                mime="video/mp4",
                key=f"{key_prefix}_dl_video_{manifest.project_id}",
                use_container_width=True,
            )

    with dl_cols[1]:
        if thumb_path.exists():
            st.download_button(
                "🖼️ 썸네일 다운로드",
                data=thumb_path.read_bytes(),
                file_name=f"{manifest.brief.title}_썸네일.png",
                mime="image/png",
                key=f"{key_prefix}_dl_thumb_{manifest.project_id}",
                use_container_width=True,
            )

    with dl_cols[2]:
        if desc_path.exists():
            st.download_button(
                "📝 설명문 다운로드",
                data=desc_path.read_text(encoding="utf-8"),
                file_name=f"{manifest.brief.title}_설명문.txt",
                mime="text/plain",
                key=f"{key_prefix}_dl_desc_{manifest.project_id}",
                use_container_width=True,
            )

    with dl_cols[3]:
        if metadata_path.exists():
            st.download_button(
                "📋 메타데이터 다운로드",
                data=metadata_path.read_text(encoding="utf-8"),
                file_name=f"{manifest.brief.title}_메타데이터.json",
                mime="application/json",
                key=f"{key_prefix}_dl_meta_{manifest.project_id}",
                use_container_width=True,
            )

    # Shorts download buttons
    if shorts_manifest_path.exists():
        shorts = json.loads(shorts_manifest_path.read_text(encoding="utf-8"))
        if shorts:
            st.markdown("### 쇼츠 다운로드")
            shorts_cols = st.columns(min(len(shorts), 5))
            for i, s in enumerate(shorts):
                short_path = project_dir / "video" / s["file"]
                if short_path.exists():
                    with shorts_cols[i % len(shorts_cols)]:
                        label_map = {
                            "hook": "훅", "reveal": "반전",
                            "climax": "클라이맥스", "healing": "힐링",
                            "memory": "기억",
                        }
                        label = label_map.get(s["label"], s["label"])
                        st.download_button(
                            f"📱 쇼츠 #{i+1} ({label})",
                            data=short_path.read_bytes(),
                            file_name=f"{manifest.brief.title}_쇼츠_{i+1}_{label}.mp4",
                            mime="video/mp4",
                            key=f"{key_prefix}_dl_short_{i}_{manifest.project_id}",
                            use_container_width=True,
                        )

    # Metadata preview
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        st.markdown(f"**YouTube 제목:** {metadata.get('title', '')}")
        st.markdown(f"**태그:** {', '.join(metadata.get('tags', []))}")

    # Expandable sections
    if desc_path.exists():
        with st.expander("📝 YouTube 설명문 보기"):
            st.text(desc_path.read_text(encoding="utf-8"))

    if script_path.exists():
        with st.expander("📖 스크립트 보기"):
            script_data = json.loads(script_path.read_text(encoding="utf-8"))
            for scene in script_data.get("scenes", []):
                phase = scene.get("phase", "")
                st.markdown(f"**[{phase}]** {scene.get('dialogue', '')}")
                st.caption(f"감정: {scene.get('emotion', '')} | 길이: {scene.get('duration_sec', 0)}초")
                st.markdown("---")


# --- Sidebar Navigation ---
st.sidebar.title("🎬 가족이야기")
st.sidebar.markdown("YouTube 자동화 파이프라인")
page = st.sidebar.radio(
    "메뉴",
    ["🎬 새 영상 만들기", "📊 프로젝트 현황", "💰 비용 리포트"],
)

# ============================================================
# PAGE 1: New Video Creation
# ============================================================
if page == "🎬 새 영상 만들기":
    st.title("🎬 새 영상 만들기")
    st.markdown("제목과 줄거리를 입력하면 자동으로 영상이 생성됩니다.")

    with st.form("new_project_form"):
        col1, col2 = st.columns([2, 1])

        with col1:
            title = st.text_input(
                "영상 제목",
                placeholder="예: 아버지의 낡은 도시락",
                max_chars=100,
            )
            synopsis = st.text_area(
                "줄거리 (간단한 설명)",
                placeholder="예: 매일 새벽 도시락을 싸던 아버지, 그 도시락 안에 숨겨진 편지를 30년 만에 발견한 딸의 이야기",
                height=120,
                max_chars=1000,
            )
            keywords = st.text_input(
                "키워드 (선택, 쉼표로 구분)",
                placeholder="예: 도시락, 편지, 새벽, 아버지",
            )

        with col2:
            family_type = st.selectbox(
                "가족 유형",
                options=list(FAMILY_TYPE_LABELS.keys()),
                format_func=lambda x: FAMILY_TYPE_LABELS[x],
            )
            ending_type = st.selectbox(
                "엔딩 유형",
                options=list(ENDING_TYPE_LABELS.keys()),
                format_func=lambda x: ENDING_TYPE_LABELS[x],
            )
            duration = st.slider(
                "영상 길이 (분)",
                min_value=4,
                max_value=12,
                value=8,
                step=1,
            )
            voice = st.radio("내레이션 음성", ["여성", "남성"], horizontal=True)

        submitted = st.form_submit_button("🚀 영상 생성 시작", use_container_width=True)

    if submitted:
        if not title or not synopsis:
            st.error("제목과 줄거리를 모두 입력해주세요.")
        elif len(synopsis) < 10:
            st.error("줄거리를 10자 이상 입력해주세요.")
        else:
            # Create project
            keyword_list = [k.strip() for k in keywords.split(",") if k.strip()] if keywords else []
            brief = ProjectBrief(
                title=title,
                synopsis=synopsis,
                family_type=family_type,
                emotional_arc=FAMILY_ARC_MAP[family_type],
                ending_type=ending_type,
                target_duration_sec=duration * 60,
                voice_gender="female" if voice == "여성" else "male",
                custom_keywords=keyword_list,
            )

            project_dir, manifest = create_project("projects", brief)
            st.success(f"프로젝트 생성 완료: `{manifest.project_id}`")

            # Run pipeline with progress
            st.markdown("---")
            st.subheader("파이프라인 실행 중...")

            progress_bar = st.progress(0)
            status_container = st.container()
            stage_statuses = {}

            orchestrator = build_orchestrator()
            total_stages = len(ALL_STAGES)

            # Run each stage manually for progress tracking
            for stage_idx, stage_name in enumerate(ALL_STAGES):
                if stage_name not in orchestrator.stages:
                    continue

                # Check dependencies
                deps = STAGE_DEPS.get(stage_name, [])
                deps_met = all(manifest.is_stage_completed(d) for d in deps)
                if not deps_met:
                    continue

                stage = orchestrator.stages[stage_name]
                label = STAGE_LABELS.get(stage_name, stage_name)

                with status_container:
                    stage_statuses[stage_name] = st.empty()
                    stage_statuses[stage_name].info(f"⏳ {label} 실행 중...")

                manifest.mark_stage_running(stage_name)
                save_manifest(project_dir, manifest)

                try:
                    cost = stage.execute(project_dir, manifest)
                    manifest.mark_stage_completed(stage_name, cost_usd=cost)
                    save_manifest(project_dir, manifest)
                    stage_statuses[stage_name].success(
                        f"✅ {label} 완료" + (f" (${cost:.4f})" if cost > 0 else "")
                    )
                except Exception as e:
                    manifest.mark_stage_failed(stage_name, str(e))
                    save_manifest(project_dir, manifest)
                    stage_statuses[stage_name].error(f"❌ {label} 실패: {e}")
                    st.error(f"파이프라인이 `{stage_name}`에서 중단되었습니다.")
                    break

                progress_bar.progress((stage_idx + 1) / total_stages)

            # Show results
            manifest = load_manifest(project_dir)
            if manifest.is_complete:
                progress_bar.progress(1.0)
                st.markdown("---")
                st.subheader("🎉 영상 생성 완료!")
                st.metric("총 API 비용", f"${manifest.total_cost_usd:.2f}")

                _show_results(project_dir, manifest)


# ============================================================
# PAGE 2: Project Status
# ============================================================
elif page == "📊 프로젝트 현황":
    st.title("📊 프로젝트 현황")

    projects = list_projects("projects")

    if not projects:
        st.info("아직 생성된 프로젝트가 없습니다. '새 영상 만들기'에서 시작해보세요.")
    else:
        st.markdown(f"총 **{len(projects)}**개 프로젝트")

        for project_dir, manifest in reversed(projects):
            completed = sum(1 for s in manifest.stages.values() if s.status == StageStatus.COMPLETED)
            failed = sum(1 for s in manifest.stages.values() if s.status == StageStatus.FAILED)
            total = len(ALL_STAGES)

            if manifest.is_complete:
                icon = "✅"
            elif failed > 0:
                icon = "❌"
            else:
                icon = "⏳"

            with st.expander(
                f"{icon} **{manifest.brief.title}** | {completed}/{total} | ${manifest.total_cost_usd:.2f}",
                expanded=False,
            ):
                col1, col2, col3 = st.columns(3)
                col1.metric("진행률", f"{completed}/{total}")
                col2.metric("비용", f"${manifest.total_cost_usd:.2f}")
                col3.metric("유형", manifest.brief.family_type.value)

                # Stage progress
                st.markdown("**스테이지 현황:**")
                for stage_name in ALL_STAGES:
                    stage_info = manifest.stages.get(stage_name)
                    label = STAGE_LABELS.get(stage_name, stage_name)
                    if stage_info and stage_info.status == StageStatus.COMPLETED:
                        cost_str = f" (${stage_info.cost_usd:.4f})" if stage_info.cost_usd > 0 else ""
                        st.markdown(f"- ✅ {label}{cost_str}")
                    elif stage_info and stage_info.status == StageStatus.FAILED:
                        st.markdown(f"- ❌ {label}: {stage_info.error}")
                    else:
                        st.markdown(f"- ⬜ {label}")

                # Results if complete
                if manifest.is_complete:
                    _show_results(project_dir, manifest, key_prefix=f"status_{manifest.project_id}")

                # Resume button for failed projects
                if failed > 0:
                    if st.button(f"🔄 재시도", key=f"resume_{manifest.project_id}"):
                        for sn, si in manifest.stages.items():
                            if si.status == StageStatus.FAILED:
                                si.status = StageStatus.PENDING
                                si.error = None
                        save_manifest(project_dir, manifest)
                        st.rerun()


# ============================================================
# PAGE 3: Cost Report
# ============================================================
elif page == "💰 비용 리포트":
    st.title("💰 비용 리포트")

    projects = list_projects("projects")
    if not projects:
        st.info("프로젝트가 없습니다.")
    else:
        total_cost = sum(m.total_cost_usd for _, m in projects)
        completed_count = sum(1 for _, m in projects if m.is_complete)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("총 프로젝트", len(projects))
        col2.metric("완료", completed_count)
        col3.metric("총 비용", f"${total_cost:.2f}")
        col4.metric("월 예산 잔여", f"${1000 - total_cost:.2f}")

        # Budget progress
        st.progress(min(total_cost / 1000, 1.0))
        st.caption(f"월 예산 사용률: {total_cost / 1000 * 100:.1f}%")

        st.markdown("---")

        # Per-project cost breakdown
        st.subheader("프로젝트별 비용")
        for project_dir, manifest in reversed(projects):
            if manifest.total_cost_usd > 0:
                with st.expander(f"**{manifest.brief.title}** - ${manifest.total_cost_usd:.2f}"):
                    for stage_name, stage_info in manifest.stages.items():
                        if stage_info.cost_usd > 0:
                            label = STAGE_LABELS.get(stage_name, stage_name)
                            st.markdown(f"- {label}: **${stage_info.cost_usd:.4f}**")

        # Cost per video average
        if completed_count > 0:
            st.markdown("---")
            avg_cost = total_cost / completed_count
            st.metric("영상당 평균 비용", f"${avg_cost:.2f}")
            st.caption(f"월 100편 예상 비용: ${avg_cost * 100:.0f}")
