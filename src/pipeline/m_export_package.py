"""Stage M: Final export packaging and validation."""

from __future__ import annotations

import json
from pathlib import Path

from src.models import ExportManifest, ProjectManifest, VideoMetadata
from src.pipeline.base_stage import BaseStage
from src.pipeline.video_paths import resolve_video_dir


class ExportPackageStage(BaseStage):
    name = "m_export_package"
    dependencies = ["i_thumbnail_gen", "j_metadata_gen", "k_monetization_desc", "l_shorts_teaser"]

    def execute(self, project_dir: Path, manifest: ProjectManifest) -> float:
        export_dir = project_dir / "export"
        export_dir.mkdir(exist_ok=True)

        video_dir = resolve_video_dir(project_dir, manifest)

        # Validate required files
        video_path = video_dir / "final.mp4"
        thumb_path = project_dir / "thumbnail" / "thumb_1080.png"
        metadata_path = export_dir / "metadata.json"
        description_path = export_dir / "description.txt"
        shorts_path = video_dir / "shorts_teaser.mp4"

        errors: list[str] = []
        if not video_path.exists():
            errors.append("final.mp4 없음")
        if not thumb_path.exists():
            errors.append("thumb_1080.png 없음")
        if not metadata_path.exists():
            errors.append("metadata.json 없음")
        if not description_path.exists():
            errors.append("description.txt 없음")

        if errors:
            raise RuntimeError(f"필수 파일 누락: {', '.join(errors)}")

        # Load metadata
        metadata = VideoMetadata.model_validate_json(
            metadata_path.read_text(encoding="utf-8")
        )

        # Merge description from monetization block into metadata
        full_description = description_path.read_text(encoding="utf-8")
        metadata.description = full_description

        # Save updated metadata
        metadata_path.write_text(
            metadata.model_dump_json(indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Create export manifest
        export_manifest = ExportManifest(
            project_id=manifest.project_id,
            video_path=video_path,
            shorts_path=shorts_path if shorts_path.exists() else None,
            thumbnail_path=thumb_path,
            metadata=metadata,
            description_path=description_path,
            total_cost_usd=manifest.total_cost_usd,
        )

        (export_dir / "upload_manifest.json").write_text(
            export_manifest.model_dump_json(indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # 메모장용 업로드 텍스트 — 영상 폴더에 함께 두어 업로드 시 복붙
        # UTF-8 BOM(utf-8-sig)을 써야 윈도우 메모장이 한글을 깨지 않게 연다.
        upload_txt = video_dir / "유튜브_업로드.txt"
        tags_line = ", ".join(metadata.tags) if metadata.tags else ""
        upload_txt.write_text(
            f"[제목]\n{metadata.title}\n\n"
            f"[태그]\n{tags_line}\n\n"
            f"[설명]\n{full_description}\n",
            encoding="utf-8-sig",
        )

        # Print summary
        self.log.info(
            "export_complete",
            project_id=manifest.project_id,
            title=metadata.title,
            video=str(video_path),
            shorts=str(shorts_path) if shorts_path.exists() else "없음",
            thumbnail=str(thumb_path),
            cost=manifest.total_cost_usd,
        )

        return 0.0
