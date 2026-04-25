"""
Generate consistent character reference images using Nano Banana 2.

One-time setup script (NOT part of the pipeline). Generated images go to
assets/characters/{family_type}/{role_with_stage}.png and are used as
image_input references for scene generation in stage G.

Two-pass generation:
  Pass 1 — anchors (reference: None): generated from prompt only
  Pass 2 — variants (reference: <other_role_key>): the anchor image is
           passed as image_input so Nano Banana 2 keeps the same identity.

Usage:
    python scripts/generate_characters.py --dry-run
    python scripts/generate_characters.py --family-type parent_sacrifice
    python scripts/generate_characters.py -t parent_sacrifice -r father_young_30s --force
"""

from __future__ import annotations

import os
import urllib.request
from pathlib import Path

import typer
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHARACTERS_DIR = PROJECT_ROOT / "assets" / "characters"

# Shared visual style — same as the rest of the channel
STYLE_PREFIX = (
    "Korean manhwa webtoon style character reference sheet. "
    "Upper body three-quarter front view, neutral calm expression, plain off-white background. "
    "Single character only, no other people, no text or watermarks. "
    "Detailed clean digital line art, warm earthy color palette with soft pastel tones and golden lighting, "
    "realistic body proportions, deeply expressive face showing genuine emotion."
)

# Definitions: each role is {"description": str, "reference": str|None}.
#   reference=None    → anchor (generated from prompt only)
#   reference="<key>" → variant (anchor image passed as image_input)
#
# parent_sacrifice has 4 life-stage variants per role; other family types stay single-stage.
CHARACTER_DEFINITIONS: dict[str, dict[str, dict]] = {
    "parent_sacrifice": {
        # ── FATHER (1949 born) — 4 stages ──
        "father_middle_40s": {  # ANCHOR (existing)
            "description": (
                "A Korean father born in 1949, late 40s in 1990s Seoul. "
                "Short neat black hair with gray temples, square jaw, weathered face, "
                "strong but weary eyes from years of hard work. "
                "Wearing a simple worn jacket — formerly a finance worker, now a taxi driver after the IMF crisis. "
                "Stoic but loving expression, quiet dignity."
            ),
            "reference": None,
        },
        "father_young_30s": {
            "description": (
                "A Korean father in his early to mid 30s in mid-1980s Seoul. "
                "Short neat black hair, square jaw, cleaner less-weathered face still relatively youthful, "
                "alert dignified eyes full of determination and quiet hope. "
                "Wearing a clean white collared shirt with a simple necktie or modest 1980s business attire — "
                "a young finance worker. Composed proud expression of a young father building his career."
            ),
            "reference": "father_middle_40s",
        },
        "father_elder_60s": {
            "description": (
                "A Korean man in his early 60s, around 2010s. "
                "Short hair mostly silver-white now with a few darker strands, deeper wrinkles around the eyes, "
                "weathered face but with quiet acceptance, eyes that have seen the family weather every storm. "
                "Wearing a simple modern cardigan over a soft button-up shirt, modest slacks. "
                "Slightly stooped posture but still composed and dignified, hands marked by decades of work."
            ),
            "reference": "father_middle_40s",
        },
        "father_elder_70s": {
            "description": (
                "A Korean elderly man in his early 70s, contemporary 2020s. "
                "Thinning white hair neatly combed, deeply lined face, slower gentler eyes that carry the weight of a lifetime, "
                "slightly stooped shoulders. Wearing a simple worn cardigan over a soft collared shirt, dark loose slacks. "
                "The dignified father grown old — the same square jaw, same quiet strength, now mellowed into tender wisdom."
            ),
            "reference": "father_middle_40s",
        },
        # ── MOTHER (1957 born) — 4 stages ──
        "mother_middle_40s": {  # ANCHOR (existing)
            "description": (
                "A Korean mother born in 1957, late 30s to early 40s in 1990s Seoul. "
                "Short permed dark brown hair, warm gentle eyes, slightly weathered hands. "
                "Wearing a simple apron over modest house clothes. "
                "Devoted housewife who rises before dawn for her family. "
                "Kind enduring expression, quiet strength."
            ),
            "reference": None,
        },
        "mother_young_20s": {
            "description": (
                "A young Korean mother in her mid to late 20s in mid-1980s Seoul. "
                "Shoulder-length softly-curled dark brown hair, fresh hopeful face with bright kind eyes, "
                "youthful glow but with the maturity of a new mother. "
                "Wearing a simple housewife's apron over a modest 1980s blouse, hair tied back from work. "
                "Warm gentle expression of a young woman dedicated to her growing family."
            ),
            "reference": "mother_middle_40s",
        },
        "mother_elder_60s": {
            "description": (
                "A Korean woman in her late 50s to early 60s, around 2015s. "
                "Short permed hair mostly silver with traces of dark brown, soft wrinkles around the smile lines, "
                "warm forgiving eyes that have weathered every family storm. "
                "Wearing a modest house cardigan over a floral blouse, comfortable modern slacks. "
                "Aging hands still want to feed and tend, gentle stooped posture, the matriarch grown softer."
            ),
            "reference": "mother_middle_40s",
        },
        "mother_elder_70s": {
            "description": (
                "A Korean elderly woman in her early 70s, contemporary 2020s. "
                "Short permed white hair, deeply lined tender face, eyes that smile even in stillness, "
                "slightly stooped frame. Wearing a simple soft cardigan over a modest blouse, "
                "comfortable slacks. The same warm kind eyes, now mellowed with decades of love and small sacrifices."
            ),
            "reference": "mother_middle_40s",
        },
        # ── SON (1975 born, narrator) — 4 stages ──
        "son_teen": {  # ANCHOR (existing)
            "description": (
                "A Korean young man born in 1975, teenager to early 20s in 1990s Seoul. "
                "Neat dark hair parted to the side, handsome face with emotionally sensitive eyes. "
                "Wearing a school uniform or casual 1990s Korean fashion such as a simple sweater and slacks. "
                "The middle child between two sisters, the storyteller of the family."
            ),
            "reference": None,
        },
        "son_child": {
            "description": (
                "A Korean boy around 7-10 years old in mid-to-late 1980s Seoul. "
                "Short bowl-cut dark hair, round innocent face with bright wide curious eyes full of trust, "
                "chubby cheeks of a well-fed child. "
                "Wearing a colorful 1980s elementary school outfit — a simple t-shirt with shorts, perhaps a school nametag. "
                "Warm carefree expression, the cherished middle child between two sisters."
            ),
            "reference": "son_teen",
        },
        "son_young_adult": {
            "description": (
                "A Korean man in his late 20s to early 30s, around 2000s-2010s. "
                "Short neat dark hair, mature handsome face with thoughtful sensitive eyes carrying quiet weight, "
                "clean-shaven. Wearing modern early-2000s business casual — a simple button-up shirt with slacks, "
                "or a clean knit sweater. Composed working-professional posture, the son grown up but still carrying the family's stories."
            ),
            "reference": "son_teen",
        },
        "son_middle_40s": {
            "description": (
                "A Korean man in his mid 40s, contemporary 2020s. "
                "Short neat dark hair starting to gray slightly at the temples, mature face showing burdens of work and life, "
                "eyes that carry both responsibility and unspoken regret about his parents. "
                "Wearing modern business casual — a clean dark blazer over a soft collared shirt or knit sweater. "
                "The son grown into a middle-aged man, the storyteller now reflecting back on his family."
            ),
            "reference": "son_teen",
        },
        # ── OLDER SISTER (1972 born, eldest) — 4 stages ──
        "older_sister_young_adult": {  # ANCHOR (existing)
            "description": (
                "A Korean young woman born in the early 1970s, the eldest sibling. "
                "Long dark hair often tied back neatly, mature responsible expression. "
                "Wearing modest practical clothes — gave up college during the IMF crisis to work. "
                "Motherly caring demeanor, gentle eyes that have seen too much too soon."
            ),
            "reference": None,
        },
        "older_sister_teen": {
            "description": (
                "A Korean girl around 12-15 years old in mid-1980s Seoul. "
                "Long dark hair often in a simple ponytail or low braid, fresh young face still innocent "
                "but with early signs of responsibility, serious gentle eyes. "
                "Wearing a 1980s Korean school uniform or a modest plain blouse and skirt. "
                "The eldest sibling beginning to help her mother with household tasks, mature beyond her years."
            ),
            "reference": "older_sister_young_adult",
        },
        "older_sister_middle_30s": {
            "description": (
                "A Korean woman in her early to mid 30s, around 2005. "
                "Shoulder-length dark hair pinned back simply, mature working-professional face with kind tired eyes, "
                "the steadiness of a woman who has been the family's quiet backbone for years. "
                "Wearing modest 2000s business attire — a simple blouse with practical slacks or skirt. "
                "Composed responsible expression, the eldest who carried more than her share."
            ),
            "reference": "older_sister_young_adult",
        },
        "older_sister_middle_50s": {
            "description": (
                "A Korean woman in her early 50s, contemporary 2020s. "
                "Short permed dark hair starting to gray, lined gentle face with kind weathered eyes "
                "that have seen the family through everything, the same caring demeanor mellowed by time. "
                "Wearing modern modest clothes — a soft cardigan over a simple blouse, comfortable slacks. "
                "The eldest sister who never stopped looking after her siblings even as her own life passed."
            ),
            "reference": "older_sister_young_adult",
        },
        # ── YOUNGER SISTER (1978 born, youngest) — 4 stages ──
        "younger_sister_child": {  # ANCHOR (existing)
            "description": (
                "A Korean girl born in the late 1970s, the youngest sibling, around 10-15 years old in 1990s Seoul. "
                "Shoulder-length hair with bangs, bright curious eyes, playful carefree expression. "
                "Wearing colorful youthful 1990s Korean fashion. "
                "Innocent and spirited, the family's source of laughter."
            ),
            "reference": None,
        },
        "younger_sister_teen": {
            "description": (
                "A Korean girl in her late teens (around 17-19), late 1990s to early 2000s. "
                "Long straight dark hair, growing into a young woman with bright lively eyes still full of mischief, "
                "fresh face with early adult features. Wearing late-1990s/early-2000s Korean youth fashion — "
                "a fitted t-shirt or knit top with jeans, perhaps a hair clip. "
                "The lively youngest of the family entering the wider world."
            ),
            "reference": "younger_sister_child",
        },
        "younger_sister_young_adult": {
            "description": (
                "A Korean woman in her mid to late 20s, around 2005-2010. "
                "Long dark hair sometimes tied up, bright playful face beginning to show maturity, "
                "the family's spirited youngest growing into a confident woman. "
                "Wearing modern young-professional outfits — a soft blouse with skirt or jeans. "
                "Cheerful warm expression, the family's source of laughter as a grown woman."
            ),
            "reference": "younger_sister_child",
        },
        "younger_sister_middle_40s": {
            "description": (
                "A Korean woman in her early to mid 40s, contemporary 2020s. "
                "Shoulder-length dark hair with subtle highlights, mature warm face still carrying traces of her playful youth, "
                "kind crinkles around the smile lines. Wearing modern modest clothing — a soft sweater or blouse with slacks. "
                "The youngest grown into middle age, still the warmth of the family."
            ),
            "reference": "younger_sister_child",
        },
    },
    # ── Other family types — single-stage anchors only (no time variants yet) ──
    "grandparent_memory": {
        "grandmother": {
            "description": (
                "A Korean grandmother born around 1932, in her early 60s in 1990s Seoul. "
                "Short permed silver-gray hair softly waved, kind wrinkled face with deep laugh lines, "
                "gentle crinkled eyes that smile even in sadness. "
                "Wearing a simple dark cardigan over a modest floral blouse, or a soft hanbok-inspired top. "
                "Slightly stooped posture, weathered hands roughened by a lifetime of family work. "
                "Quiet wisdom, unconditional grandmotherly love."
            ),
            "reference": None,
        },
        "grandfather": {
            "description": (
                "A Korean grandfather born around 1928, in his mid to late 60s in 1990s Seoul. "
                "Short combed-back white hair, weathered face with deep wrinkles, "
                "warm reserved eyes behind classic 1990s wire-rimmed reading glasses. "
                "Wearing a worn knit cardigan over a button-up collared shirt, or a traditional vest. "
                "Calm dignified presence, hands of someone who worked the land. "
                "Reserved but quietly loving demeanor."
            ),
            "reference": None,
        },
        "grandchild": {
            "description": (
                "A Korean boy around 7-9 years old in 1990s Seoul. "
                "Short bowl-cut dark hair, round innocent face with bright wide eyes full of wonder. "
                "Wearing a colorful 1990s Korean elementary school outfit — a striped t-shirt with simple cotton shorts. "
                "Carefree warm expression, open-hearted curiosity, the cherished only grandchild."
            ),
            "reference": None,
        },
    },
    "couple_growing_old": {
        "elderly_husband": {
            "description": (
                "A contemporary Korean elderly man in his early 70s. "
                "Short white hair neatly combed, weathered face with gentle deep-set eyes that have seen a long life. "
                "Wearing a tidy modern cardigan over a soft collared shirt, simple slacks. "
                "Calm dignified posture, hands marked by decades of work but resting at ease. "
                "Quiet contentment, the patience of a lifelong companion."
            ),
            "reference": None,
        },
        "elderly_wife": {
            "description": (
                "A contemporary Korean elderly woman in her late 60s to early 70s. "
                "Short permed silver hair softly waved, warm smiling face with crinkles at the eyes, "
                "graceful aged beauty. "
                "Wearing a modern soft-toned blouse with a cardigan, or a simple knit top. "
                "Gentle posture, hands clasped softly, sometimes reaching for her husband's. "
                "Tender warmth, the depth of decades of shared love."
            ),
            "reference": None,
        },
    },
    "late_realization": {
        "elderly_father": {
            "description": (
                "A contemporary Korean elderly father in his late 70s. "
                "Short thinning white hair, weathered tired face with kind quiet eyes, slight stoop in his shoulders. "
                "Wearing a simple worn cardigan over a soft collared shirt, dark slacks. "
                "Hands trembling slightly with age but still steady, modest unassuming presence. "
                "Stoic patient love that never asked for thanks, a father who waited too long."
            ),
            "reference": None,
        },
        "elderly_mother": {
            "description": (
                "A contemporary Korean elderly mother in her mid 70s. "
                "Short permed gray hair, tender wrinkled face with warm forgiving eyes, soft slightly stooped posture. "
                "Wearing a simple house cardigan over a floral blouse, modest skirt or slacks. "
                "Hands worn from decades of caring for her family, still wanting to feed and tend. "
                "Endless quiet sacrifice, a mother who loved without conditions."
            ),
            "reference": None,
        },
        "adult_son": {
            "description": (
                "A contemporary Korean man in his mid 40s. "
                "Short neat dark hair starting to gray slightly at the temples, mature face showing burdens of work and life, "
                "tired but kind eyes carrying unspoken regret. "
                "Wearing a modern business casual outfit — a dark blazer over a collared shirt, or a clean knit sweater. "
                "Composed but emotionally weighed posture, the look of someone who realized too late how much his parents gave."
            ),
            "reference": None,
        },
    },
}

# Nano Banana 2 settings
MODEL = "google/nano-banana-2"
ASPECT_RATIO = "2:3"
RESOLUTION = "1K"
OUTPUT_FORMAT = "png"
PRICE_PER_IMAGE = 0.039


def build_prompt(description: str, has_reference: bool) -> str:
    if has_reference:
        return (
            f"{STYLE_PREFIX}\n\n"
            "Maintain the EXACT same person identity (face structure, eye shape, ethnic features) "
            "as the reference image — only change age, hair, clothing as described below.\n\n"
            f"Character: {description}"
        )
    return f"{STYLE_PREFIX}\n\nCharacter: {description}"


def generate_one(
    replicate_module,
    prompt: str,
    output_path: Path,
    reference_image_path: Path | None,
) -> float:
    input_params: dict = {
        "prompt": prompt,
        "aspect_ratio": ASPECT_RATIO,
        "resolution": RESOLUTION,
        "output_format": OUTPUT_FORMAT,
    }

    file_handle = None
    if reference_image_path is not None:
        if not reference_image_path.exists():
            raise FileNotFoundError(f"Reference image missing: {reference_image_path}")
        file_handle = open(reference_image_path, "rb")
        input_params["image_input"] = [file_handle]

    try:
        output = replicate_module.run(MODEL, input=input_params)
    finally:
        if file_handle is not None:
            file_handle.close()

    image_url = str(output) if not isinstance(output, list) else str(output[0])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(image_url, str(output_path))
    return PRICE_PER_IMAGE


def main(
    family_type: str = typer.Option(None, "--family-type", "-t", help="Family type key (default: all defined)."),
    role: str = typer.Option(None, "--role", "-r", help="Single role within --family-type."),
    force: bool = typer.Option(False, "--force", help="Regenerate even if image exists."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print plan and first prompt without API calls."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
) -> None:
    load_dotenv(PROJECT_ROOT / ".env")

    if family_type and family_type not in CHARACTER_DEFINITIONS:
        typer.echo(f"❌ Unknown family_type: {family_type}", err=True)
        typer.echo(f"   Defined: {list(CHARACTER_DEFINITIONS.keys())}", err=True)
        raise typer.Exit(1)
    if role and not family_type:
        typer.echo("❌ --role requires --family-type", err=True)
        raise typer.Exit(1)

    # Build target list (family_type, role, definition)
    types_to_run = [family_type] if family_type else list(CHARACTER_DEFINITIONS.keys())
    targets: list[tuple[str, str, dict]] = []
    for ft in types_to_run:
        for r, defn in CHARACTER_DEFINITIONS[ft].items():
            if role and r != role:
                continue
            targets.append((ft, r, defn))

    if not targets:
        typer.echo(f"❌ No matching characters (family_type={family_type}, role={role})", err=True)
        raise typer.Exit(1)

    # Two-pass ordering: anchors first, then variants (so anchor exists when variant references it)
    anchors = [(ft, r, d) for ft, r, d in targets if d["reference"] is None]
    variants = [(ft, r, d) for ft, r, d in targets if d["reference"] is not None]
    targets_ordered = anchors + variants

    typer.echo(f"\n📋 Plan: {len(targets_ordered)} character sheet(s)")
    typer.echo(f"   Model: {MODEL}")
    typer.echo(f"   {ASPECT_RATIO} portrait, {RESOLUTION}, {OUTPUT_FORMAT}")
    typer.echo(f"   Anchors: {len(anchors)}, Variants (with image_input): {len(variants)}")
    typer.echo(f"   Estimated cost: ${len(targets_ordered) * PRICE_PER_IMAGE:.2f}\n")
    for ft, r, d in targets_ordered:
        ref = d["reference"]
        marker = "·" if ref is None else f"↳ {ref}"
        typer.echo(f"   {ft}/{r:30s}  {marker}")

    if dry_run:
        ft, r, d = targets_ordered[0]
        typer.echo("\n🔍 First prompt preview:")
        typer.echo("─" * 70)
        typer.echo(build_prompt(d["description"], d["reference"] is not None))
        typer.echo("─" * 70)
        return

    if not yes and not typer.confirm("\nProceed?"):
        typer.echo("Cancelled.")
        raise typer.Exit(0)

    if not os.environ.get("REPLICATE_API_TOKEN"):
        typer.echo("❌ REPLICATE_API_TOKEN not set (.env)", err=True)
        raise typer.Exit(1)

    try:
        import replicate
    except ImportError:
        typer.echo("❌ pip install replicate", err=True)
        raise typer.Exit(1)

    total_cost = 0.0
    skipped = 0
    generated = 0
    for i, (ft, r, d) in enumerate(targets_ordered, 1):
        output_path = CHARACTERS_DIR / ft / f"{r}.{OUTPUT_FORMAT}"
        if output_path.exists() and not force:
            typer.echo(f"  [{i}/{len(targets_ordered)}] {ft}/{r} — exists (use --force to regenerate)")
            skipped += 1
            continue

        ref_path: Path | None = None
        if d["reference"] is not None:
            ref_path = CHARACTERS_DIR / ft / f"{d['reference']}.{OUTPUT_FORMAT}"

        ref_note = f"  (ref: {d['reference']})" if d["reference"] else ""
        typer.echo(f"  [{i}/{len(targets_ordered)}] Generating {ft}/{r}...{ref_note}")
        try:
            cost = generate_one(replicate, build_prompt(d["description"], d["reference"] is not None), output_path, ref_path)
            total_cost += cost
            generated += 1
            typer.echo(f"      ✅ {output_path.relative_to(PROJECT_ROOT)}")
        except Exception as e:
            typer.echo(f"      ❌ failed: {e}", err=True)

    typer.echo(f"\n✨ Done. Cost: ${total_cost:.2f}  ({generated} generated, {skipped} skipped)")
    typer.echo(f"   Output dir: {CHARACTERS_DIR.relative_to(PROJECT_ROOT)}/")


if __name__ == "__main__":
    typer.run(main)
