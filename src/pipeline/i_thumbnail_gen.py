"""Stage I: Thumbnail generation optimized for Korean senior audience CTR."""

from __future__ import annotations

from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from src.engines.llm_client import PROJECT_ROOT
from src.models import ProjectManifest, Script
from src.pipeline.base_stage import BaseStage


class ThumbnailGenStage(BaseStage):
    name = "i_thumbnail_gen"
    dependencies = ["h_video_compose"]

    def execute(self, project_dir: Path, manifest: ProjectManifest) -> float:
        script = Script.model_validate_json(
            (project_dir / "script.json").read_text(encoding="utf-8")
        )

        with open(PROJECT_ROOT / "config" / "settings.yaml", encoding="utf-8") as f:
            settings = yaml.safe_load(f)

        thumb_cfg = settings.get("thumbnail", {})
        width = thumb_cfg.get("width", 1280)
        height = thumb_cfg.get("height", 720)

        # Select pre-climax scene (anticipation > resolution)
        best_scene = self._select_pre_climax_scene(script)
        source_image_path = project_dir / "scenes" / f"scene_{best_scene.index:03d}.png"

        thumb_dir = project_dir / "thumbnail"
        thumb_dir.mkdir(exist_ok=True)
        output_path = thumb_dir / "thumb_1080.png"

        if source_image_path.exists():
            img = Image.open(source_image_path)
            img = img.resize((width, height), Image.LANCZOS)
        else:
            img = Image.new("RGB", (width, height), color=(30, 30, 50))

        # Apply warm color grading (orange/red tones for senior appeal)
        img = self._apply_warm_grading(img)

        # Apply cinematic gradient overlay
        img = self._apply_gradient(img)

        # Add title text with emoji and warm colors
        draw = ImageDraw.Draw(img)
        title = manifest.brief.title
        emotion_emoji = self._get_emotion_emoji(best_scene.emotion)
        self._draw_title_with_emoji(draw, title, emotion_emoji, width, height)

        img.save(str(output_path), quality=95)
        self.log.info("thumbnail_generated", path=str(output_path))
        return 0.0

    def _select_pre_climax_scene(self, script: Script):
        """Select scene just BEFORE climax for anticipation effect."""
        # Find climax index, then pick one before it
        climax_idx = 0
        for scene in script.scenes:
            if scene.phase == "climax":
                climax_idx = scene.index
                break

        # Pick the scene right before climax (reveal or layering)
        pre_climax = [s for s in script.scenes if s.index == climax_idx - 1]
        if pre_climax:
            return pre_climax[0]

        # Fallback priority
        for phase in ["reveal", "climax", "layering", "hook"]:
            for scene in script.scenes:
                if scene.phase == phase:
                    return scene
        return script.scenes[0]

    def _apply_warm_grading(self, img: Image.Image) -> Image.Image:
        """Apply warm orange/red color grading for emotional appeal."""
        # Enhance warmth by boosting red channel slightly
        r, g, b = img.split()
        from PIL import ImageEnhance

        # Increase saturation
        img = ImageEnhance.Color(img).enhance(1.2)
        # Increase warmth
        img = ImageEnhance.Brightness(img).enhance(1.05)

        # Add warm overlay
        warm_overlay = Image.new("RGBA", img.size, (255, 140, 50, 30))
        img = img.convert("RGBA")
        img = Image.alpha_composite(img, warm_overlay)
        return img.convert("RGB")

    def _apply_gradient(self, img: Image.Image) -> Image.Image:
        """Apply dark gradient from bottom + top vignette for text readability."""
        img = img.convert("RGBA")
        gradient = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(gradient)

        for y in range(img.size[1]):
            progress = y / img.size[1]
            # Top vignette (subtle)
            if progress < 0.15:
                alpha = int((1 - progress / 0.15) * 60)
                draw.line([(0, y), (img.size[0], y)], fill=(0, 0, 0, alpha))
            # Bottom gradient (strong for text)
            if progress > 0.4:
                alpha = int((progress - 0.4) / 0.6 * 200)
                draw.line([(0, y), (img.size[0], y)], fill=(0, 0, 0, alpha))

        img = Image.alpha_composite(img, gradient)
        return img.convert("RGB")

    def _get_emotion_emoji(self, emotion: str) -> str:
        """Map scene emotion to thumbnail emoji."""
        emoji_map = {
            "curiosity_sadness": "😢",
            "tension": "😨",
            "nostalgia_sadness": "💔",
            "shock_realization": "😱",
            "deep_sadness_gratitude": "😭",
            "warmth_peace": "❤️",
            "gentle_hope": "🙏",
            "longing": "💭",
            "anger_hurt": "😤",
            "tears_relief": "😭",
            "overwhelming_emotion": "😭",
            "vulnerability": "💔",
            "catharsis": "😭",
            "hidden_love": "❤️",
            "grief_love": "😢",
        }
        return emoji_map.get(emotion, "😢")

    def _draw_title_with_emoji(
        self, draw: ImageDraw.Draw, title: str, emoji: str, width: int, height: int
    ) -> None:
        """Draw large title with emoji, warm accent colors for senior audience."""
        font_path = PROJECT_ROOT / "assets" / "fonts" / "NanumMyeongjo.ttf"

        # Load font - try multiple fallbacks
        font_large = self._load_font(font_path, 96)
        font_emoji = self._load_font(font_path, 72)

        # Shorten title if too long (max 2 lines, ~12 chars each)
        display_title = self._format_title_for_thumb(title)

        # Position: bottom third, centered
        y_base = height - 220

        # Draw each line
        lines = display_title.split("\n")
        for i, line in enumerate(lines):
            y = y_base + i * 100
            bbox = draw.textbbox((0, 0), line, font=font_large)
            text_width = bbox[2] - bbox[0]
            x = (width - text_width) // 2

            # Black outline (thick for readability)
            for dx in range(-4, 5):
                for dy in range(-4, 5):
                    draw.text((x + dx, y + dy), line, font=font_large, fill=(0, 0, 0))

            # Main text in warm white-yellow
            draw.text((x, y), line, font=font_large, fill=(255, 250, 230))

        # Draw emoji at top-right corner
        draw.text((width - 120, 30), emoji, font=font_emoji, fill=(255, 255, 255))

    def _format_title_for_thumb(self, title: str) -> str:
        """Format title for thumbnail: max 2 lines, ~12 chars each."""
        if len(title) <= 12:
            return title

        # Try to split at natural break points
        mid = len(title) // 2
        # Look for space near middle
        best_split = mid
        for offset in range(min(6, mid)):
            if mid + offset < len(title) and title[mid + offset] == " ":
                best_split = mid + offset
                break
            if mid - offset >= 0 and title[mid - offset] == " ":
                best_split = mid - offset
                break

        line1 = title[:best_split].strip()
        line2 = title[best_split:].strip()

        # Truncate if still too long
        if len(line1) > 14:
            line1 = line1[:14]
        if len(line2) > 14:
            line2 = line2[:13] + "..."

        return f"{line1}\n{line2}"

    def _load_font(self, font_path: Path, size: int) -> ImageFont.FreeTypeFont:
        """Load font with fallback chain."""
        try:
            return ImageFont.truetype(str(font_path), size)
        except (OSError, IOError):
            pass
        try:
            return ImageFont.truetype("/System/Library/Fonts/AppleSDGothicNeo.ttc", size)
        except (OSError, IOError):
            pass
        return ImageFont.load_default()
