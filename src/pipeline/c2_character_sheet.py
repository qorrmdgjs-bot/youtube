"""Stage C2: Generate/load per-role character sheets for visual consistency.

Scans ``assets/character_sheets/{family_type}/{role}/`` for user-supplied
``ref_*.png``/``ref_*.jpg`` reference images. For each role missing a rendered
``sheet_front.png``/``sheet_profile.png``/``sheet_fullbody.png`` triad, generate
them once via Gemini using the user references as input. The resulting paths are
written into the project manifest's ``character_refs`` field so that downstream
stages (G, G2) can pass them as ``ref_images`` for consistent appearance.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from src.engines.llm_client import PROJECT_ROOT
from src.models import ProjectManifest
from src.pipeline.base_stage import BaseStage
from src.pipeline.c_visual_prompt import CHARACTER_TEMPLATES

SHEET_VIEWS = [
    ("sheet_front", "front-facing portrait, shoulders up, neutral expression, soft warm lighting"),
    ("sheet_profile", "side profile portrait, shoulders up, neutral expression, soft warm lighting"),
    ("sheet_fullbody", "full-body standing pose, facing camera, casual everyday outfit, plain neutral background"),
]


class CharacterSheetStage(BaseStage):
    name = "c2_character_sheet"
    dependencies = ["b_scene_segment"]

    def execute(self, project_dir: Path, manifest: ProjectManifest) -> float:
        family_type = manifest.brief.family_type.value
        sheet_root = PROJECT_ROOT / "assets" / "character_sheets" / family_type

        characters = CHARACTER_TEMPLATES.get(
            family_type, CHARACTER_TEMPLATES["default"]
        )

        import yaml
        with open(PROJECT_ROOT / "config" / "settings.yaml", encoding="utf-8") as f:
            settings = yaml.safe_load(f)

        generate_sheets = settings.get("character_sheet", {}).get(
            "generate_sheets", False
        )

        total_cost = 0.0
        character_refs: dict[str, list[str]] = {}
        client = None  # lazy init — only if we actually generate sheets

        for role, desc in characters.items():
            role_dir = sheet_root / role
            role_dir.mkdir(parents=True, exist_ok=True)

            user_refs = sorted(
                list(role_dir.glob("ref_*.png"))
                + list(role_dir.glob("ref_*.jpg"))
                + list(role_dir.glob("ref_*.jpeg"))
            )

            if not user_refs:
                self.log.warning(
                    "no_user_ref_images",
                    role=role,
                    hint=f"put ref_*.png in {role_dir}",
                )
                continue

            if not generate_sheets:
                # 시트 생성 스킵 — ref_*.png를 바로 참조 이미지로 등록
                character_refs[role] = [str(p) for p in user_refs]
                self.log.info("character_refs_registered", role=role, count=len(user_refs))
                continue

            # generate_sheets=true: webtoon 스타일 정면/측면/전신 3뷰 생성
            if client is None:
                from src.engines.engine_factory import get_image_client
                client = get_image_client(settings)

            sheet_paths: list[Path] = []
            for view_name, view_prompt in SHEET_VIEWS:
                sheet_path = role_dir / f"{view_name}.png"
                if not sheet_path.exists():
                    prompt = self._build_sheet_prompt(desc, view_prompt)
                    self.log.info("generating_sheet", role=role, view=view_name)
                    cost = client.generate(
                        prompt=prompt,
                        output_path=sheet_path,
                        ref_images=user_refs,
                        seed=hash(f"{family_type}:{role}:{view_name}") % (2**31),
                    )
                    total_cost += cost
                sheet_paths.append(sheet_path)

            if sheet_paths:
                meta_path = role_dir / "meta.json"
                if not meta_path.exists():
                    meta_path.write_text(
                        json.dumps(
                            {
                                "family_type": family_type,
                                "role": role,
                                "generated_at": datetime.now().isoformat(),
                                "source_refs": [p.name for p in user_refs],
                                "sheets": [p.name for p in sheet_paths],
                            },
                            ensure_ascii=False,
                            indent=2,
                        ),
                        encoding="utf-8",
                    )

                character_refs[role] = [str(p) for p in sheet_paths]

        manifest.character_refs = character_refs

        self.log.info(
            "character_sheet_complete",
            family_type=family_type,
            mode="sheets" if generate_sheets else "refs_only",
            roles=list(character_refs.keys()),
            cost=total_cost,
        )
        return total_cost

    @staticmethod
    def _build_sheet_prompt(character_desc: str, view_prompt: str) -> str:
        return (
            "Korean manhwa webtoon style illustration, clean line art, "
            "warm earthy palette, realistic proportions, consistent character design. "
            f"Character: {character_desc}. "
            f"Composition: {view_prompt}. "
            "Preserve the facial identity and outfit details from the reference images. "
            "Plain neutral background, no text, no logo."
        )
