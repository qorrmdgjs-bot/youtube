"""Stage C: Extract visual prompts from scenes for image generation.

Generates Korean webtoon (manhwa) style prompts with character consistency.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from src.engines.llm_client import LLMClient, PROJECT_ROOT
from src.models import ProjectManifest, Script
from src.pipeline.base_stage import BaseStage

# Style prefix for all images - Korean webtoon style (시니어 친화)
STYLE_PREFIX = (
    "Korean manhwa webtoon style illustration, "
    "detailed clean line art, warm earthy color palette with soft browns beiges and creams, "
    "realistic proportions, deeply expressive character faces showing genuine emotion, "
    "detailed authentic Korean background setting, "
    "soft golden warm lighting, nostalgic sentimental atmosphere, "
    "gentle color gradation, muted pastel tones, "
    "heartwarming family scene, emotionally touching mood, "
    "high quality digital illustration, "
)

VISUAL_PROMPT_TEMPLATE = """다음 장면의 visual_description을 바탕으로 이미지 생성용 영어 프롬프트를 만들어주세요.

## 장면 정보
- 장면 번호: {{ index }}
- 감정: {{ emotion }}
- 시각 설명: {{ visual_description }}
- 대사: {{ dialogue }}

## 캐릭터 설명 (모든 장면에서 일관되게 유지)
{{ character_description }}

## 스타일 규칙
- 영어로 작성
- 한국 웹툰(만화) 스타일 (Korean manhwa webtoon style)
- 깔끔한 라인 아트 + 따뜻한 어스톤 색감 (warm earthy tones: 브라운, 베이지, 크림)
- 사실적 비율의 인물 (애니메이션이 아닌 웹툰 비율)
- 인물의 표정과 감정을 섬세하고 풍부하게 묘사 (눈가의 주름, 떨리는 입술, 젖은 눈 등)
- 한국적 배경을 상세히 묘사 (한국 가정집, 시장, 학교, 식당, 시골집, 병원 등)
- 부드러운 황금빛 조명과 노스탤지어 분위기
- 색감은 채도를 낮추고 파스텔 톤으로 따뜻하게
- 50-70세 시니어가 공감할 수 있는 한국적 정서와 풍경
- 캐릭터 외모 설명을 반드시 포함하여 일관성 유지
- 부정적 프롬프트 없이 긍정 묘사만

JSON 형식으로 응답하세요:
{"visual_prompt": "영어 프롬프트 텍스트"}
"""

# Default character descriptions by family type
CHARACTER_TEMPLATES = {
    "parent_sacrifice": {
        "father": "a Korean father born 1949, in his late 40s (1990s setting), short neat black hair with gray temples, square jaw, strong but weary eyes from years of hard work, formerly wore neat suits as a finance worker, now wears a simple worn jacket as a taxi driver, stoic but loving expression, weathered face showing sacrifice",
        "mother": "a Korean mother born 1957, in her late 30s to early 40s (1990s setting), short permed dark brown hair, warm gentle eyes, wearing a simple apron over modest clothes, slightly weathered hands from housework, kind and enduring facial expression, devoted housewife",
        "son": "a Korean young man born 1975, teenager to early 20s (1990s setting), neat dark hair parted to the side, wearing school uniform or casual 90s Korean fashion, handsome face with emotional sensitive eyes, the middle child between two sisters",
        "older_sister": "a Korean young woman born early 1970s, the eldest sibling, long dark hair often tied back neatly, mature and responsible expression, wearing modest practical clothes, motherly caring demeanor toward younger siblings",
        "younger_sister": "a Korean girl born late 1970s, the youngest sibling, shoulder-length hair with bangs, bright curious eyes, playful carefree expression, wearing colorful youthful 90s Korean fashion, innocent and spirited",
    },
    "default": {
        "mother": "a Korean mother in her 50s, short permed dark brown hair, warm gentle eyes, wearing modest traditional clothes",
        "father": "a Korean father in his 50s, short neat black hair with some gray, wearing a simple shirt",
        "son": "a Korean young man in his late 20s, neat dark hair, wearing a casual sweater",
        "daughter": "a Korean young woman in her late 20s, long dark hair, wearing a simple blouse",
    },
}


class VisualPromptStage(BaseStage):
    name = "c_visual_prompt"
    dependencies = ["b_scene_segment"]

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

        # Get character descriptions for this family type
        family_type = manifest.brief.family_type.value
        characters = CHARACTER_TEMPLATES.get(family_type, CHARACTER_TEMPLATES["default"])
        char_desc = "\n".join(f"- {role}: {desc}" for role, desc in characters.items())

        total_cost = 0.0

        for scene in script.scenes:
            if scene.visual_prompt:
                continue

            description = scene.visual_description or scene.dialogue

            from jinja2 import Template
            user_prompt = Template(VISUAL_PROMPT_TEMPLATE).render(
                index=scene.index,
                emotion=scene.emotion,
                visual_description=description,
                dialogue=scene.dialogue,
                character_description=char_desc,
            )

            response, cost = client.generate(
                system=(
                    "You are an expert at writing image generation prompts for Korean manhwa webtoon style illustrations. "
                    "The style must be consistent: clean detailed line art, warm earthy color palette, realistic proportions, "
                    "expressive faces, detailed Korean backgrounds. Characters must match the provided descriptions exactly "
                    "for visual consistency across all scenes. Respond only in JSON."
                ),
                user=user_prompt,
                max_tokens=512,
                temperature=0.5,
            )
            total_cost += cost

            # Parse response and prepend style prefix
            try:
                json_match = re.search(r"\{.*\}", response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(0))
                    prompt = data.get("visual_prompt", description)
                    # Ensure style prefix is included
                    if not prompt.lower().startswith("korean manhwa"):
                        prompt = STYLE_PREFIX + prompt
                    scene.visual_prompt = prompt
                else:
                    scene.visual_prompt = STYLE_PREFIX + response.strip()
            except (json.JSONDecodeError, KeyError):
                scene.visual_prompt = STYLE_PREFIX + f"{scene.emotion}, {description}"

            self.log.info(
                "visual_prompt_extracted",
                scene=scene.index,
                prompt_len=len(scene.visual_prompt),
            )

        # Save updated script
        (project_dir / "script.json").write_text(
            script.model_dump_json(indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Also update individual scene files
        scenes_dir = project_dir / "scenes"
        for scene in script.scenes:
            scene_file = scenes_dir / f"scene_{scene.index:03d}.json"
            scene_file.write_text(
                scene.model_dump_json(indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        self.log.info("visual_prompts_complete", scenes=len(script.scenes), cost=total_cost)
        return total_cost
