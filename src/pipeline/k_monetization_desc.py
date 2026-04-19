"""Stage K: Monetization description block generation."""

from __future__ import annotations

import random
from pathlib import Path

import yaml

from src.engines.llm_client import PROJECT_ROOT
from src.models import ProjectManifest, Script
from src.pipeline.base_stage import BaseStage


class MonetizationDescStage(BaseStage):
    name = "k_monetization_desc"
    dependencies = ["h_video_compose"]

    def execute(self, project_dir: Path, manifest: ProjectManifest) -> float:
        script = Script.model_validate_json(
            (project_dir / "script.json").read_text(encoding="utf-8")
        )

        with open(PROJECT_ROOT / "config" / "cta_templates.yaml", encoding="utf-8") as f:
            cta_config = yaml.safe_load(f)

        with open(PROJECT_ROOT / "config" / "monetization_blocks.yaml", encoding="utf-8") as f:
            blocks_config = yaml.safe_load(f)

        separator = blocks_config.get("separator", "───────────────")

        # Build description parts
        parts: list[str] = []

        # Story summary
        parts.append(manifest.brief.synopsis)
        parts.append("")

        # Timestamps
        parts.append(self._build_timestamps(script))
        parts.append("")
        parts.append(separator)
        parts.append("")

        # Subscribe + Comment CTA (context-specific by family type)
        subscribe = random.choice(cta_config.get("subscribe_cta", [""]))
        comment_ctas = cta_config.get("comment_cta", {})
        family_key = manifest.brief.family_type.value.split("_")[0]  # e.g. "parent"
        family_comments = comment_ctas.get(family_key, comment_ctas.get("default", [""]))
        if isinstance(family_comments, list):
            comment = random.choice(family_comments)
        else:
            comment = random.choice(comment_ctas.get("default", [""]))

        # Engagement CTA
        engagement = random.choice(cta_config.get("engagement_cta", [""]))
        parts.append(f"💌 {subscribe}")
        parts.append(f"✍️ {comment}")
        if engagement:
            parts.append(f"👍 {engagement}")
        parts.append("")
        parts.append(separator)
        parts.append("")

        # Affiliate products (high-conversion for seniors)
        affiliate = cta_config.get("affiliate", {})
        for key, info in affiliate.items():
            if isinstance(info, dict) and "text" in info:
                parts.append(f"  {info['text']}")
                if "description" in info:
                    parts.append(f"    {info['description']}")
                parts.append(f"    👉 {info['url_placeholder']}")
        parts.append("")

        # CPA products
        cpa = cta_config.get("cpa", {})
        for key, info in cpa.items():
            if isinstance(info, dict) and "text" in info:
                parts.append(f"  {info['text']}")
                parts.append(f"    👉 {info['url_placeholder']}")
                parts.append(f"    {info.get('disclaimer', '')}")
        parts.append("")
        parts.append(separator)
        parts.append("")

        # Membership tiers
        membership_data = cta_config.get("membership_cta", {})
        if isinstance(membership_data, dict):
            cta_text = membership_data.get("cta_text", [""])
            if isinstance(cta_text, list) and cta_text:
                parts.append(random.choice(cta_text))
            for tier_key in ["tier1", "tier2", "tier3"]:
                tier = membership_data.get(tier_key, {})
                if tier:
                    parts.append(f"  {tier.get('name', '')} ({tier.get('price', '')}) - {tier.get('benefit', '')}")
            parts.append("")
        elif isinstance(membership_data, list):
            parts.append(f"⭐ {random.choice(membership_data)}")
            parts.append("")

        # Story submission
        submission = random.choice(cta_config.get("story_submission_cta", [""]))
        if submission:
            parts.append(f"📮 {submission}")
            parts.append("")

        # Kakao
        kakao = random.choice(cta_config.get("kakao_cta", [""]))
        if kakao:
            parts.append(f"💬 {kakao}")
            parts.append("")

        parts.append(separator)
        parts.append("")

        # Hashtags
        hashtags = blocks_config.get("hashtags", [])
        parts.append(" ".join(hashtags))

        # Write full description
        description = "\n".join(parts)
        export_dir = project_dir / "export"
        export_dir.mkdir(exist_ok=True)
        (export_dir / "description.txt").write_text(description, encoding="utf-8")

        self.log.info("monetization_desc_generated", length=len(description))
        return 0.0

    def _build_timestamps(self, script: Script) -> str:
        lines = []
        current_time = 0.0
        phase_names = {
            "hook": "시작",
            "conflict": "이야기",
            "layering": "기억",
            "reveal": "진실",
            "climax": "절정",
            "healing": "치유",
            "afterglow": "마무리",
        }
        for scene in script.scenes:
            if scene.has_silence_before:
                current_time += scene.silence_duration_sec
            minutes = int(current_time // 60)
            seconds = int(current_time % 60)
            label = phase_names.get(scene.phase, scene.phase)
            lines.append(f"{minutes:02d}:{seconds:02d} {label}")
            current_time += scene.duration_sec
        return "\n".join(lines)
