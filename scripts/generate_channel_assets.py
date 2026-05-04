"""채널 메인 자산 생성 (배너 + 프로필 아이콘).

parent_sacrifice 캐릭터 시트를 ref로 첨부해 영상과 동일 인물 일관성 유지.
"""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from PIL import Image

load_dotenv()

from src.engines.gemini_image_client import GeminiImageClient

ROOT = Path(__file__).resolve().parents[1]
CHARS = ROOT / "assets" / "characters" / "parent_sacrifice"
OUT = ROOT / "assets" / "branding" / "v2"
OUT.mkdir(parents=True, exist_ok=True)

REFS_FAMILY = [
    CHARS / "father_middle_40s.png",
    CHARS / "mother_middle_40s.png",
    CHARS / "son_teen.png",
    CHARS / "older_sister_young_adult.png",
    CHARS / "younger_sister_child.png",
]
REFS_TRIO = [
    CHARS / "father_middle_40s.png",
    CHARS / "mother_middle_40s.png",
    CHARS / "son_teen.png",
]

BANNER_PROMPT = """Korean manhwa webtoon style illustration of a 1990s Korean family in a warm cozy living room.
A family of five gathered naturally: a 40s father reading a newspaper on a worn fabric sofa,
a 40s mother smiling softly while standing near the kitchen entrance,
a teenage son (around 16 years old) sitting on the floor by the low wooden tea table,
a young adult older sister (around 19) standing beside the mother,
a child younger sister sitting cross-legged near her father.
1990s Korean home interior with traditional furnishings - patterned wallpaper, wooden tea table,
small TV cabinet with framed family photographs, an old radio, soft sheer curtains with afternoon golden sunlight streaming in.
Warm earthy color palette with muted browns, soft creams, and golden hour lighting.
Nostalgic mood, gentle composition with the family arranged naturally across the wide horizontal frame.
Clean detailed line art, realistic proportions, faces clearly visible and warm.
Wide cinematic 16:9 composition, no text, no logos, no captions, just the scene.
The atmosphere should feel like a cherished family memory."""

ICON_PROMPT = """Korean manhwa webtoon style portrait of a Korean family of three in a warm intimate close-up.
Center composition: 40s father, 40s mother, and teenage son (around 16) sitting close together,
warmly looking forward with gentle expressions of love and quiet pride.
Square 1:1 composition with the three figures filling the frame from chest up.
1990s Korean style clothing - the father in a simple shirt, the mother in a soft warm cardigan, the son in a school uniform shirt.
Soft warm earthy color palette with muted browns, creams, and golden lighting from one side.
Clean detailed line art, realistic proportions, faces are the focal point and clearly recognizable.
Background is a softly blurred warm cream tone, no distracting elements.
No text, no logos, just the family portrait.
The mood is gentle, nostalgic, and full of quiet familial love."""


def main() -> None:
    client = GeminiImageClient()

    banner_raw = OUT / "channel_banner_raw.png"
    print(f"[1/2] Generating banner... (5 family refs)")
    cost1 = client.generate(BANNER_PROMPT, banner_raw, ref_images=REFS_FAMILY)
    print(f"   -> {banner_raw} (${cost1:.4f})")

    icon_raw = OUT / "channel_icon_raw.png"
    print(f"[2/2] Generating icon... (3 family refs)")
    cost2 = client.generate(ICON_PROMPT, icon_raw, ref_images=REFS_TRIO)
    print(f"   -> {icon_raw} (${cost2:.4f})")

    print(f"\nResize to YouTube spec...")
    banner = Image.open(banner_raw).convert("RGB")
    target_banner = (2560, 1440)
    bw, bh = banner.size
    scale = max(target_banner[0] / bw, target_banner[1] / bh)
    resized = banner.resize((int(bw * scale), int(bh * scale)), Image.LANCZOS)
    rw, rh = resized.size
    left = (rw - target_banner[0]) // 2
    top = (rh - target_banner[1]) // 2
    banner_final = resized.crop((left, top, left + target_banner[0], top + target_banner[1]))
    banner_out = OUT / "channel_banner.png"
    banner_final.save(banner_out, "PNG", optimize=True)
    print(f"   banner: {banner_out} ({banner_final.size})")

    icon = Image.open(icon_raw).convert("RGB")
    target_icon = (800, 800)
    iw, ih = icon.size
    side = min(iw, ih)
    left = (iw - side) // 2
    top = (ih - side) // 2
    icon_square = icon.crop((left, top, left + side, top + side))
    icon_final = icon_square.resize(target_icon, Image.LANCZOS)
    icon_out = OUT / "channel_icon.png"
    icon_final.save(icon_out, "PNG", optimize=True)
    print(f"   icon: {icon_out} ({icon_final.size})")

    print(f"\nTotal cost: ${cost1 + cost2:.4f}")


if __name__ == "__main__":
    main()
