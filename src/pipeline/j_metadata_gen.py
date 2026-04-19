"""Stage J: YouTube metadata generation (title, description, tags)."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from src.engines.llm_client import LLMClient, PROJECT_ROOT
from src.models import ProjectManifest, Script, VideoMetadata
from src.pipeline.base_stage import BaseStage


METADATA_SYSTEM_PROMPT = """당신은 한국 시니어(50-70세) 대상 감성 유튜브 채널의 메타데이터 전문가입니다.
조회수 100만 이상의 감동 사연 채널들의 패턴을 잘 알고 있습니다.

## 제목 규칙
- 60-90자 (검색 최적화를 위해 키워드 풍부하게)
- 감정 키워드 필수 포함: 눈물, 사랑, 용서, 후회, 감사, 그리움
- 숫자 활용: "30년 만에", "50년 숨겨온", "마지막 편지"
- 이모지 1-2개 포함 (😭, ❤️, 💔, 🙏)
- 클릭베이트 금지하되 궁금증 유발
- 예시 형식: "30년 숨겨온 아버지의 도시락 속 편지 😭 읽는 순간 눈물이 멈추지 않았습니다"

## 설명 규칙
- 첫 3줄은 이모지 + 감정 요약 (접힌 설명 위에 보이는 부분)
  예: "😭 아버지가 매일 새벽 싸주셨던 도시락 안에..."
- 그 다음 타임스탬프

## 태그 규칙
- 15-20개 한국어 태그
- 필수 포함: 가족이야기, 감동실화, 눈물, 효도
- 감정 키워드 + 관계 키워드 + 상황 키워드 조합

## 출력 형식 (JSON만)
{
  "title": "YouTube 제목 (이모지 포함, 60-90자)",
  "description": "이모지 + 감정 요약 3줄",
  "tags": ["태그1", "태그2", ...]
}
"""


class MetadataGenStage(BaseStage):
    name = "j_metadata_gen"
    dependencies = ["h_video_compose"]

    def execute(self, project_dir: Path, manifest: ProjectManifest) -> float:
        script = Script.model_validate_json(
            (project_dir / "script.json").read_text(encoding="utf-8")
        )

        with open(PROJECT_ROOT / "config" / "settings.yaml", encoding="utf-8") as f:
            settings = yaml.safe_load(f)

        llm_config = settings.get("llm", {})
        client = LLMClient(
            model=llm_config.get("model", "claude-sonnet-4-20250514"),
            cache_dir=project_dir / ".cache",
        )

        # Build timestamps from scenes
        timestamps = self._build_timestamps(script)

        user_prompt = (
            f"다음 영상의 YouTube 메타데이터를 생성해주세요.\n\n"
            f"제목: {manifest.brief.title}\n"
            f"줄거리: {manifest.brief.synopsis}\n"
            f"가족 유형: {manifest.brief.family_type.value}\n"
            f"장면 수: {len(script.scenes)}\n"
            f"총 길이: {script.total_duration_sec}초\n\n"
            f"타임스탬프:\n{timestamps}\n\n"
            f"JSON 형식으로만 응답해주세요."
        )

        response, cost = client.generate(
            system=METADATA_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=1024,
            temperature=0.5,
        )

        # Parse response
        import re
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
        else:
            data = {
                "title": manifest.brief.title,
                "description": manifest.brief.synopsis,
                "tags": ["가족", "감동", "부모", "사랑"],
            }

        metadata = VideoMetadata(
            title=data.get("title", manifest.brief.title),
            description=data.get("description", "") + "\n\n" + timestamps,
            tags=data.get("tags", []),
        )

        # Save metadata
        export_dir = project_dir / "export"
        export_dir.mkdir(exist_ok=True)
        (export_dir / "metadata.json").write_text(
            metadata.model_dump_json(indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        self.log.info("metadata_generated", title=metadata.title, tags_count=len(metadata.tags))
        return cost

    def _build_timestamps(self, script: Script) -> str:
        """Build YouTube timestamp string from scene breaks."""
        lines = []
        current_time = 0.0

        for scene in script.scenes:
            if scene.has_silence_before:
                current_time += scene.silence_duration_sec

            minutes = int(current_time // 60)
            seconds = int(current_time % 60)
            phase_names = {
                "hook": "시작",
                "conflict": "이야기",
                "layering": "기억",
                "reveal": "진실",
                "climax": "절정",
                "healing": "치유",
                "afterglow": "마무리",
            }
            label = phase_names.get(scene.phase, scene.phase)
            lines.append(f"{minutes:02d}:{seconds:02d} {label}")
            current_time += scene.duration_sec

        return "\n".join(lines)
