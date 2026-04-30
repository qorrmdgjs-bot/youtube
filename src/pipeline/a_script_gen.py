"""Stage A: Script generation using LLM."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from src.engines.llm_client import LLMClient, render_template, PROJECT_ROOT
from src.models import ProjectManifest, Script
from src.pipeline.base_stage import BaseStage


class ScriptGenStage(BaseStage):
    name = "a_script_gen"
    dependencies = []

    def execute(self, project_dir: Path, manifest: ProjectManifest) -> float:
        brief = manifest.brief

        # Load emotional arc structure from config
        with open(PROJECT_ROOT / "config" / "emotional_arcs.yaml", encoding="utf-8") as f:
            arcs_config = yaml.safe_load(f)

        arc_key = brief.emotional_arc
        arc_data = arcs_config["arcs"].get(arc_key)
        if not arc_data or "structure" not in arc_data:
            raise ValueError(f"감정 아크를 찾을 수 없거나 구조가 없습니다: {arc_key}")

        # Load settings for LLM config
        with open(PROJECT_ROOT / "config" / "settings.yaml", encoding="utf-8") as f:
            settings = yaml.safe_load(f)

        llm_config = settings.get("llm", {})

        # Render prompts
        system_prompt = render_template("script_gen_system.txt")
        user_prompt = render_template(
            "script_gen_user.txt",
            title=brief.title,
            synopsis=brief.synopsis,
            family_type=brief.family_type.value,
            emotional_arc=arc_key,
            ending_type=brief.ending_type.value,
            target_duration_sec=brief.target_duration_sec,
            custom_keywords=brief.custom_keywords,
            arc_structure=arc_data["structure"],
            # Series mode fields (None/empty unless built via build_episode_brief)
            series_context_md=brief.series_context_md,
            series_overview_md=brief.series_overview_md,
            episode_number=brief.episode_number,
            event_idx=brief.event_idx,
            perspective=brief.perspective,
            characters_in_episode=brief.characters_in_episode,
        )

        # Call LLM
        client = LLMClient(
            model=llm_config.get("model", "claude-sonnet-4-20250514"),
            cache_dir=project_dir / ".cache",
        )

        response_text, cost = client.generate(
            system=system_prompt,
            user=user_prompt,
            max_tokens=llm_config.get("max_tokens", 4096),
            temperature=llm_config.get("temperature", 0.8),
        )

        # Parse JSON from response (handle markdown code blocks)
        json_text = self._extract_json(response_text)
        script_data = json.loads(json_text)

        # Validate with Pydantic
        script = Script.model_validate(script_data)

        # Save script
        (project_dir / "script.json").write_text(
            script.model_dump_json(indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        self.log.info(
            "script_generated",
            title=script.title,
            scenes=len(script.scenes),
            total_duration=script.total_duration_sec,
        )

        return cost

    def _extract_json(self, text: str) -> str:
        """Extract JSON from LLM response, handling markdown code blocks."""
        # Try to find JSON in code blocks
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Try to find raw JSON object
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return match.group(0)

        return text.strip()
